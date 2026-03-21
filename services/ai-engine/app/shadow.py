"""Shadow AI Detection - identifies unauthorized AI service usage"""
import os
import structlog
import asyncpg

logger = structlog.get_logger()

_pg_password = os.getenv("POSTGRES_PASSWORD", "")
if not _pg_password:
    logger.warning("POSTGRES_PASSWORD not set — using empty password (dev only)")

POSTGRES_DSN = (
    f"postgresql://{os.getenv('POSTGRES_USER', 'neuranac')}:{_pg_password}"
    f"@{os.getenv('POSTGRES_HOST', 'localhost')}:{os.getenv('POSTGRES_PORT', '5432')}/{os.getenv('POSTGRES_DB', 'neuranac')}"
)

# Built-in AI service signatures
BUILTIN_SIGNATURES = [
    {"name": "OpenAI ChatGPT", "category": "llm", "dns": ["api.openai.com", "chat.openai.com"], "risk": "high"},
    {"name": "Anthropic Claude", "category": "llm", "dns": ["api.anthropic.com", "claude.ai"], "risk": "high"},
    {"name": "Google Gemini", "category": "llm", "dns": ["generativelanguage.googleapis.com", "gemini.google.com"], "risk": "high"},
    {"name": "GitHub Copilot", "category": "coding", "dns": ["copilot.github.com", "api.githubcopilot.com"], "risk": "medium"},
    {"name": "Hugging Face", "category": "ml_platform", "dns": ["huggingface.co", "api-inference.huggingface.co"], "risk": "medium"},
    {"name": "Replicate", "category": "ml_platform", "dns": ["api.replicate.com", "replicate.com"], "risk": "medium"},
    {"name": "Midjourney", "category": "image_gen", "dns": ["midjourney.com", "cdn.midjourney.com"], "risk": "medium"},
    {"name": "DALL-E", "category": "image_gen", "dns": ["labs.openai.com"], "risk": "medium"},
    {"name": "Stability AI", "category": "image_gen", "dns": ["api.stability.ai", "stability.ai"], "risk": "medium"},
    {"name": "Cohere", "category": "llm", "dns": ["api.cohere.ai", "cohere.com"], "risk": "medium"},
    {"name": "AWS Bedrock", "category": "cloud_ai", "dns": ["bedrock-runtime.amazonaws.com"], "risk": "low"},
    {"name": "Azure OpenAI", "category": "cloud_ai", "dns": ["openai.azure.com"], "risk": "low"},
    {"name": "Ollama Local", "category": "local_llm", "dns": [], "risk": "medium", "ports": [11434]},
    {"name": "vLLM Local", "category": "local_llm", "dns": [], "risk": "medium", "ports": [8000]},
]


class ShadowAIDetector:
    def __init__(self):
        self.signatures = []
        self.approved_services = set()
        self.db_pool = None

    async def load_signatures(self):
        """Load AI service signatures from DB + built-in"""
        self.signatures = list(BUILTIN_SIGNATURES)
        try:
            self.db_pool = await asyncpg.create_pool(POSTGRES_DSN, min_size=1, max_size=5)
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch("SELECT name, category, dns_patterns, risk_level, is_approved FROM ai_services")
                for r in rows:
                    self.signatures.append({
                        "name": r["name"], "category": r["category"],
                        "dns": r["dns_patterns"] or [], "risk": r["risk_level"],
                    })
                    if r["is_approved"]:
                        self.approved_services.add(r["name"])
            logger.info("Shadow AI signatures loaded", count=len(self.signatures))
        except Exception as e:
            logger.warning("Failed to load DB signatures, using built-in only", error=str(e))

    async def detect(self, request: dict) -> dict:
        """Check if traffic matches a known AI service"""
        domain = request.get("destination_domain", "").lower()
        sni = request.get("sni", "").lower()
        http_path = request.get("http_path", "").lower()

        target = domain or sni

        for sig in self.signatures:
            for dns in sig.get("dns", []):
                if dns.lower() in target or target.endswith(dns.lower()):
                    is_approved = sig["name"] in self.approved_services
                    risk = "low" if is_approved else sig.get("risk", "medium")
                    action = "allow" if is_approved else ("block" if risk == "high" else "alert")

                    return {
                        "is_ai_service": True,
                        "service_name": sig["name"],
                        "service_category": sig["category"],
                        "is_approved": is_approved,
                        "risk_level": risk,
                        "recommended_action": action,
                    }

        # Check for local LLM patterns
        if "/v1/chat/completions" in http_path or "/api/generate" in http_path:
            return {
                "is_ai_service": True,
                "service_name": "Unknown LLM API",
                "service_category": "local_llm",
                "is_approved": False,
                "risk_level": "medium",
                "recommended_action": "alert",
            }

        return {
            "is_ai_service": False,
            "service_name": None,
            "service_category": None,
            "is_approved": False,
            "risk_level": "none",
            "recommended_action": "allow",
        }
