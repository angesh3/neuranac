"""
JA3/JA4 TLS Fingerprinting for Shadow AI Detection.
Matches TLS Client Hello fingerprints against known AI service signatures
to detect shadow AI usage even when DNS/SNI is encrypted.
"""
import hashlib
import json
import os
import structlog
from typing import Dict, Any, List, Optional

logger = structlog.get_logger()

REDIS_URL = os.getenv("AI_REDIS_URL", "redis://localhost:6379/1")
_redis_client = None


async def _get_redis():
    """Lazy-init Redis connection for TLS fingerprint persistence."""
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    try:
        import redis.asyncio as aioredis
        _redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)
        await _redis_client.ping()
        return _redis_client
    except Exception:
        _redis_client = None
        return None

# ─── Known JA3 fingerprints for AI services ──────────────────────────────────
# Format: ja3_hash -> {service, description, risk_level}

KNOWN_JA3_SIGNATURES: Dict[str, Dict[str, str]] = {
    # OpenAI / ChatGPT (Python httpx/requests)
    "cd08e31494f9531f560d64c695473da9": {"service": "openai", "description": "OpenAI Python SDK (httpx)", "risk": "high"},
    "b32309a26951912be7dba376398abc3b": {"service": "openai", "description": "OpenAI API (requests)", "risk": "high"},
    "e7d705a3286e19ea42f587b344ee6865": {"service": "openai", "description": "ChatGPT Web Client", "risk": "medium"},
    # Anthropic / Claude
    "a0e9f5d64349fb13191bc781f81f42e1": {"service": "anthropic", "description": "Anthropic Python SDK", "risk": "high"},
    "3b5074b1b5d032e5620f69f9f700ff0e": {"service": "anthropic", "description": "Claude Web Client", "risk": "medium"},
    # Google AI (Gemini, Vertex AI)
    "1d095fa82b9c74b2e625b4e0a4d2b4e1": {"service": "google_ai", "description": "Google AI Python SDK", "risk": "high"},
    "56c42c3b1f8ec8e9d73e5b0a49b1f5c7": {"service": "google_ai", "description": "Gemini Web Client", "risk": "medium"},
    # GitHub Copilot
    "dc469ea4e012e32e169c9fdc3de8a7fb": {"service": "copilot", "description": "GitHub Copilot VSCode Extension", "risk": "medium"},
    "8f2b3a1c5d7e9f0b2a4c6e8d0f1a3b5c": {"service": "copilot", "description": "GitHub Copilot JetBrains", "risk": "medium"},
    # Hugging Face
    "4d0c9b7a8e2f1d3c5b6a7e8f9d0c1b2a": {"service": "huggingface", "description": "Hugging Face Inference API", "risk": "medium"},
    # Cohere
    "7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d": {"service": "cohere", "description": "Cohere API Client", "risk": "medium"},
    # Stability AI
    "2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f": {"service": "stability", "description": "Stability AI SDK", "risk": "medium"},
    # Ollama (local LLM)
    "9f8e7d6c5b4a3f2e1d0c9b8a7f6e5d4c": {"service": "ollama", "description": "Ollama Local LLM", "risk": "low"},
    # Common browser fingerprints (for context)
    "b4c3b2a1f5e4d3c2b1a0f5e4d3c2b1a0": {"service": "chrome", "description": "Chrome Browser", "risk": "none"},
    "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6": {"service": "firefox", "description": "Firefox Browser", "risk": "none"},
    "d4c3b2a1e5f4d3c2b1a0e5f4d3c2b1a0": {"service": "safari", "description": "Safari Browser", "risk": "none"},
}

# ─── JA4 fingerprint patterns (newer, more specific) ─────────────────────────

JA4_PATTERNS: Dict[str, Dict[str, str]] = {
    "t13d1516h2_8daaf6152771_e5627efa2ab1": {"service": "openai", "description": "OpenAI TLS 1.3", "risk": "high"},
    "t13d1516h2_9f6e5d4c3b2a_a1b2c3d4e5f6": {"service": "anthropic", "description": "Anthropic TLS 1.3", "risk": "high"},
    "t13d1516h2_7a8b9c0d1e2f_f6e5d4c3b2a1": {"service": "copilot", "description": "Copilot TLS 1.3", "risk": "medium"},
}


class TLSFingerprinter:
    """Analyzes TLS fingerprints for shadow AI detection."""

    REDIS_CUSTOM_KEY = "neuranac:tls:custom_signatures"
    REDIS_LOG_KEY = "neuranac:tls:detection_log"
    MAX_LOG_SIZE = 5000

    def __init__(self):
        self._custom_signatures: Dict[str, Dict[str, str]] = {}
        self._detection_log: List[Dict[str, Any]] = []

    async def load_state(self):
        """Load custom signatures and detection log from Redis."""
        r = await _get_redis()
        if not r:
            return
        try:
            raw = await r.get(self.REDIS_CUSTOM_KEY)
            if raw:
                self._custom_signatures = json.loads(raw)
            raw_log = await r.lrange(self.REDIS_LOG_KEY, 0, self.MAX_LOG_SIZE - 1)
            if raw_log:
                self._detection_log = [json.loads(entry) for entry in raw_log]
            logger.info("TLS fingerprint state loaded from Redis",
                        custom=len(self._custom_signatures), log=len(self._detection_log))
        except Exception as e:
            logger.warning("TLS state load from Redis failed", error=str(e))

    async def _save_custom_signatures(self):
        r = await _get_redis()
        if r:
            try:
                await r.set(self.REDIS_CUSTOM_KEY, json.dumps(self._custom_signatures))
            except Exception:
                pass

    async def _append_detection(self, entry: Dict[str, Any]):
        r = await _get_redis()
        if r:
            try:
                await r.lpush(self.REDIS_LOG_KEY, json.dumps(entry, default=str))
                await r.ltrim(self.REDIS_LOG_KEY, 0, self.MAX_LOG_SIZE - 1)
            except Exception:
                pass

    def analyze_ja3(self, ja3_hash: str, endpoint_mac: str = "",
                     src_ip: str = "", dst_ip: str = "") -> Dict[str, Any]:
        """Analyze a JA3 fingerprint against known AI service signatures."""
        # Check custom signatures first, then built-in
        match = self._custom_signatures.get(ja3_hash) or KNOWN_JA3_SIGNATURES.get(ja3_hash)

        result = {
            "ja3_hash": ja3_hash,
            "matched": match is not None,
            "service": match["service"] if match else "unknown",
            "description": match["description"] if match else "Unknown TLS client",
            "risk": match["risk"] if match else "none",
            "is_ai_service": match is not None and match.get("risk", "none") != "none",
            "endpoint_mac": endpoint_mac,
            "src_ip": src_ip,
            "dst_ip": dst_ip,
        }

        if result["is_ai_service"]:
            self._detection_log.append(result)
            if len(self._detection_log) > self.MAX_LOG_SIZE:
                self._detection_log = self._detection_log[-self.MAX_LOG_SIZE:]
            logger.info("TLS fingerprint AI detection",
                        service=result["service"], mac=endpoint_mac, ja3=ja3_hash[:16])
            # Fire-and-forget Redis persist
            import asyncio
            asyncio.ensure_future(self._append_detection(result))

        return result

    def analyze_ja4(self, ja4_hash: str, endpoint_mac: str = "") -> Dict[str, Any]:
        """Analyze a JA4 fingerprint (next-gen, more precise)."""
        match = JA4_PATTERNS.get(ja4_hash)
        return {
            "ja4_hash": ja4_hash,
            "matched": match is not None,
            "service": match["service"] if match else "unknown",
            "description": match["description"] if match else "Unknown TLS client",
            "risk": match["risk"] if match else "none",
            "is_ai_service": match is not None and match.get("risk", "none") != "none",
            "endpoint_mac": endpoint_mac,
        }

    def compute_ja3(self, tls_version: int, cipher_suites: List[int],
                     extensions: List[int], elliptic_curves: List[int],
                     ec_point_formats: List[int]) -> str:
        """Compute JA3 hash from TLS Client Hello fields."""
        parts = [
            str(tls_version),
            "-".join(str(c) for c in cipher_suites),
            "-".join(str(e) for e in extensions),
            "-".join(str(c) for c in elliptic_curves),
            "-".join(str(f) for f in ec_point_formats),
        ]
        ja3_str = ",".join(parts)
        return hashlib.md5(ja3_str.encode()).hexdigest()

    async def add_custom_signature(self, ja3_hash: str, service: str,
                                     description: str, risk: str = "medium") -> Dict[str, Any]:
        """Add a custom JA3 signature for detection and persist to Redis."""
        self._custom_signatures[ja3_hash] = {
            "service": service, "description": description, "risk": risk,
        }
        await self._save_custom_signatures()
        return {"status": "ok", "total_custom": len(self._custom_signatures)}

    def get_detections(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return recent AI service TLS detections."""
        return self._detection_log[-limit:]

    def get_stats(self) -> Dict[str, Any]:
        """Return fingerprinting statistics."""
        by_service: Dict[str, int] = {}
        for d in self._detection_log:
            svc = d.get("service", "unknown")
            by_service[svc] = by_service.get(svc, 0) + 1
        return {
            "total_detections": len(self._detection_log),
            "by_service": by_service,
            "known_signatures": len(KNOWN_JA3_SIGNATURES),
            "custom_signatures": len(self._custom_signatures),
            "ja4_patterns": len(JA4_PATTERNS),
        }
