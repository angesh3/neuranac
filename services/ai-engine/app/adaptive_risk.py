"""
Adaptive Risk Thresholds — learns optimal risk score thresholds from historical
auth outcomes using simple online statistics. Adjusts quarantine/monitor/allow
boundaries per tenant based on false-positive and false-negative rates.
"""
import os
import json
import time
import math
import structlog
from collections import defaultdict
from typing import Dict, Any, Optional

logger = structlog.get_logger()

REDIS_URL = os.getenv("AI_REDIS_URL", "redis://localhost:6379/1")
DEFAULT_THRESHOLDS = {"quarantine": 70, "monitor": 40, "allow": 0}


class AdaptiveRiskEngine:
    """Learns and adjusts risk thresholds from feedback."""

    def __init__(self):
        self._thresholds: Dict[str, Dict[str, int]] = {}
        self._feedback: Dict[str, list] = defaultdict(list)
        self._max_feedback = 1000
        self._redis_prefix = "neuranac:risk:thresholds:"

    def get_thresholds(self, tenant_id: str = "default") -> Dict[str, int]:
        """Return current thresholds for a tenant."""
        return self._thresholds.get(tenant_id, DEFAULT_THRESHOLDS.copy())

    async def record_feedback(self, tenant_id: str, risk_score: int,
                                decision: str, was_correct: bool) -> Dict[str, Any]:
        """Record whether a risk-based decision was correct (operator feedback)."""
        self._feedback[tenant_id].append({
            "risk_score": risk_score,
            "decision": decision,
            "was_correct": was_correct,
            "timestamp": time.time(),
        })
        if len(self._feedback[tenant_id]) > self._max_feedback:
            self._feedback[tenant_id] = self._feedback[tenant_id][-self._max_feedback:]

        # Re-calibrate thresholds after every 10 feedback entries
        fb = self._feedback[tenant_id]
        if len(fb) % 10 == 0 and len(fb) >= 20:
            new_thresholds = self._calibrate(fb)
            self._thresholds[tenant_id] = new_thresholds
            logger.info("Risk thresholds recalibrated",
                        tenant=tenant_id, thresholds=new_thresholds, feedback_count=len(fb))
            await self._persist(tenant_id, new_thresholds)

        return {
            "status": "recorded",
            "feedback_count": len(fb),
            "current_thresholds": self.get_thresholds(tenant_id),
        }

    def _calibrate(self, feedback: list) -> Dict[str, int]:
        """Recalibrate thresholds to minimize false positives and false negatives."""
        # Separate correct vs incorrect decisions at various score ranges
        quarantine_scores = [f["risk_score"] for f in feedback if f["decision"] == "quarantine"]
        monitor_scores = [f["risk_score"] for f in feedback if f["decision"] == "monitor"]
        allow_scores = [f["risk_score"] for f in feedback if f["decision"] == "allow"]

        # False positives: quarantined but was_correct=False → threshold too low
        fp_quarantine = [f["risk_score"] for f in feedback
                         if f["decision"] == "quarantine" and not f["was_correct"]]
        # False negatives: allowed but was_correct=False → threshold too high
        fn_allow = [f["risk_score"] for f in feedback
                    if f["decision"] == "allow" and not f["was_correct"]]

        thresholds = DEFAULT_THRESHOLDS.copy()

        # Raise quarantine threshold if too many false positives
        if len(fp_quarantine) > 3 and quarantine_scores:
            avg_fp = sum(fp_quarantine) / len(fp_quarantine)
            thresholds["quarantine"] = min(90, int(avg_fp + 10))

        # Lower monitor threshold if too many false negatives in allow
        if len(fn_allow) > 3 and allow_scores:
            avg_fn = sum(fn_allow) / len(fn_allow)
            thresholds["monitor"] = max(20, int(avg_fn - 5))

        # Ensure quarantine > monitor
        if thresholds["quarantine"] <= thresholds["monitor"]:
            thresholds["quarantine"] = thresholds["monitor"] + 15

        return thresholds

    async def _persist(self, tenant_id: str, thresholds: Dict[str, int]):
        """Persist thresholds to Redis."""
        try:
            import redis.asyncio as aioredis
            r = aioredis.from_url(REDIS_URL, decode_responses=True)
            await r.setex(f"{self._redis_prefix}{tenant_id}", 86400 * 30, json.dumps(thresholds))
            await r.aclose()
        except Exception:
            pass

    async def load_thresholds(self, tenant_id: str = "default"):
        """Load persisted thresholds from Redis."""
        try:
            import redis.asyncio as aioredis
            r = aioredis.from_url(REDIS_URL, decode_responses=True)
            raw = await r.get(f"{self._redis_prefix}{tenant_id}")
            await r.aclose()
            if raw:
                self._thresholds[tenant_id] = json.loads(raw)
                logger.info("Loaded adaptive thresholds", tenant=tenant_id,
                            thresholds=self._thresholds[tenant_id])
        except Exception:
            pass

    async def get_stats(self, tenant_id: str = "default") -> Dict[str, Any]:
        """Return adaptive risk statistics."""
        fb = self._feedback.get(tenant_id, [])
        correct = sum(1 for f in fb if f["was_correct"])
        incorrect = len(fb) - correct
        return {
            "tenant_id": tenant_id,
            "thresholds": self.get_thresholds(tenant_id),
            "feedback_count": len(fb),
            "accuracy": round(correct / max(len(fb), 1), 4),
            "false_positive_count": sum(1 for f in fb if f["decision"] == "quarantine" and not f["was_correct"]),
            "false_negative_count": sum(1 for f in fb if f["decision"] == "allow" and not f["was_correct"]),
        }
