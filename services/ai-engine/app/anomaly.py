"""Anomaly Detection & Policy Drift module for AI Engine"""
import os
import json
import time
import math
from collections import defaultdict
from typing import List, Optional
import structlog

logger = structlog.get_logger()

REDIS_URL = os.getenv("AI_REDIS_URL", "redis://localhost:6379/1")
BASELINE_TTL = int(os.getenv("AI_BASELINE_TTL", "604800"))  # 7 days default

_redis_client = None


async def _get_redis():
    """Lazy-init Redis connection."""
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    try:
        import redis.asyncio as aioredis
        _redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)
        await _redis_client.ping()
        logger.info("Anomaly Redis connected", url=REDIS_URL)
        return _redis_client
    except Exception as e:
        logger.warning("Redis unavailable for anomaly baselines, using in-memory", error=str(e))
        _redis_client = None
        return None


class AnomalyDetector:
    """Detects behavioral anomalies in authentication patterns using statistical methods."""

    def __init__(self):
        # In-memory fallback: sliding window of observations per entity
        self._baselines: dict[str, list] = defaultdict(list)
        self._max_window = 1000  # Keep last N observations
        self._redis_prefix = "neuranac:anomaly:baseline:"

    async def _load_baseline(self, entity_key: str) -> list:
        """Load baseline from Redis, fall back to in-memory."""
        r = await _get_redis()
        if r:
            try:
                raw = await r.get(f"{self._redis_prefix}{entity_key}")
                if raw:
                    return json.loads(raw)
            except Exception as e:
                logger.warning("Redis baseline load failed", entity=entity_key, error=str(e))
        return self._baselines.get(entity_key, [])

    async def _save_baseline(self, entity_key: str, baseline: list):
        """Save baseline to Redis and in-memory."""
        self._baselines[entity_key] = baseline
        r = await _get_redis()
        if r:
            try:
                await r.setex(f"{self._redis_prefix}{entity_key}", BASELINE_TTL, json.dumps(baseline))
            except Exception as e:
                logger.warning("Redis baseline save failed", entity=entity_key, error=str(e))

    async def analyze(self, request: dict) -> dict:
        """Analyze a session event for anomalies.
        Input: {endpoint_mac, username, nas_ip, eap_type, auth_time_hour, day_of_week, ...}
        Output: {is_anomalous, anomaly_score, anomalies: [...], recommendation}
        """
        mac = request.get("endpoint_mac", "unknown")
        username = request.get("username", "")
        entity_key = username or mac

        features = self._extract_features(request)
        baseline = await self._load_baseline(entity_key)

        anomalies = []
        score = 0.0

        if len(baseline) >= 5:
            # Time-of-day anomaly
            hours = [b.get("hour", 12) for b in baseline]
            avg_hour = sum(hours) / len(hours)
            std_hour = max(1.0, _std_dev(hours))
            current_hour = features.get("hour", 12)
            z_hour = abs(current_hour - avg_hour) / std_hour
            if z_hour > 2.0:
                anomalies.append({
                    "type": "unusual_time",
                    "detail": f"Auth at hour {current_hour}, baseline avg {avg_hour:.1f} (z={z_hour:.2f})",
                    "severity": "medium" if z_hour < 3.0 else "high",
                })
                score += min(z_hour * 15, 40)

            # Location anomaly (NAS IP change)
            recent_nas = [b.get("nas_ip") for b in baseline[-10:] if b.get("nas_ip")]
            current_nas = features.get("nas_ip", "")
            if current_nas and recent_nas and current_nas not in recent_nas:
                anomalies.append({
                    "type": "new_location",
                    "detail": f"New NAS {current_nas}, previously seen: {set(recent_nas)}",
                    "severity": "medium",
                })
                score += 20

            # EAP type anomaly
            recent_eap = [b.get("eap_type") for b in baseline[-20:] if b.get("eap_type")]
            current_eap = features.get("eap_type", "")
            if current_eap and recent_eap and current_eap not in recent_eap:
                anomalies.append({
                    "type": "eap_type_change",
                    "detail": f"Changed to {current_eap}, previously: {set(recent_eap)}",
                    "severity": "low",
                })
                score += 10

            # Frequency anomaly (too many auths in short time)
            recent_times = [b.get("timestamp", 0) for b in baseline[-20:]]
            if len(recent_times) >= 3:
                intervals = [recent_times[i+1] - recent_times[i] for i in range(len(recent_times)-1) if recent_times[i+1] > recent_times[i]]
                if intervals:
                    avg_interval = sum(intervals) / len(intervals)
                    if avg_interval < 60 and len(intervals) > 5:  # More than 5 auths within 1 min avg
                        anomalies.append({
                            "type": "high_frequency",
                            "detail": f"Avg interval {avg_interval:.0f}s across {len(intervals)} auths",
                            "severity": "high",
                        })
                        score += 30

        # Update baseline (persist to Redis)
        features["timestamp"] = time.time()
        baseline.append(features)
        if len(baseline) > self._max_window:
            baseline = baseline[-self._max_window:]
        await self._save_baseline(entity_key, baseline)

        is_anomalous = score >= 25 or len(anomalies) >= 2
        recommendation = "allow"
        if score >= 50:
            recommendation = "quarantine"
        elif score >= 25:
            recommendation = "monitor"

        return {
            "is_anomalous": is_anomalous,
            "anomaly_score": min(round(score), 100),
            "anomalies": anomalies,
            "recommendation": recommendation,
            "baseline_size": len(baseline),
        }

    def _extract_features(self, request: dict) -> dict:
        auth_hour = request.get("auth_time_hour")
        if auth_hour is None:
            from datetime import datetime, timezone
            auth_hour = datetime.now(timezone.utc).hour
        return {
            "hour": auth_hour,
            "day_of_week": request.get("day_of_week", 0),
            "nas_ip": request.get("nas_ip", ""),
            "eap_type": request.get("eap_type", ""),
            "username": request.get("username", ""),
            "mac": request.get("endpoint_mac", ""),
        }


class PolicyDriftDetector:
    """Detects drift between intended policy behavior and actual auth outcomes."""

    def __init__(self):
        self._policy_outcomes: dict[str, list] = defaultdict(list)
        self._max_window = 500
        self._redis_prefix = "neuranac:drift:outcomes:"

    async def record_outcome(self, policy_id: str, expected_action: str, actual_action: str,
                              matched: bool, evaluation_time_us: int = 0):
        """Record a policy evaluation outcome for drift analysis."""
        outcome = {
            "expected": expected_action,
            "actual": actual_action,
            "matched": matched,
            "eval_time_us": evaluation_time_us,
            "timestamp": time.time(),
        }
        self._policy_outcomes[policy_id].append(outcome)
        if len(self._policy_outcomes[policy_id]) > self._max_window:
            self._policy_outcomes[policy_id] = self._policy_outcomes[policy_id][-self._max_window:]
        # Persist to Redis
        r = await _get_redis()
        if r:
            try:
                await r.setex(
                    f"{self._redis_prefix}{policy_id}",
                    BASELINE_TTL,
                    json.dumps(self._policy_outcomes[policy_id]),
                )
            except Exception:
                pass

    async def analyze_drift(self, policy_id: Optional[str] = None) -> dict:
        """Analyze policy drift for a specific policy or all policies."""
        if policy_id:
            policies = {policy_id: self._policy_outcomes.get(policy_id, [])}
        else:
            policies = dict(self._policy_outcomes)

        results = []
        for pid, outcomes in policies.items():
            if not outcomes:
                continue
            total = len(outcomes)
            mismatches = sum(1 for o in outcomes if o["expected"] != o["actual"])
            unmatched = sum(1 for o in outcomes if not o["matched"])
            avg_eval_time = sum(o["eval_time_us"] for o in outcomes) / total if total else 0

            drift_pct = (mismatches / total * 100) if total else 0
            unmatched_pct = (unmatched / total * 100) if total else 0

            drift_level = "none"
            if drift_pct > 20:
                drift_level = "critical"
            elif drift_pct > 10:
                drift_level = "high"
            elif drift_pct > 5:
                drift_level = "medium"
            elif drift_pct > 0:
                drift_level = "low"

            results.append({
                "policy_id": pid,
                "total_evaluations": total,
                "mismatches": mismatches,
                "drift_percentage": round(drift_pct, 2),
                "unmatched_percentage": round(unmatched_pct, 2),
                "drift_level": drift_level,
                "avg_evaluation_time_us": round(avg_eval_time),
            })

        overall_drift = "none"
        if results:
            max_drift = max(r["drift_percentage"] for r in results)
            if max_drift > 20:
                overall_drift = "critical"
            elif max_drift > 10:
                overall_drift = "high"
            elif max_drift > 5:
                overall_drift = "medium"
            elif max_drift > 0:
                overall_drift = "low"

        return {
            "overall_drift": overall_drift,
            "policies_analyzed": len(results),
            "results": results,
        }


def _std_dev(values: list) -> float:
    if len(values) < 2:
        return 0.0
    avg = sum(values) / len(values)
    variance = sum((v - avg) ** 2 for v in values) / (len(values) - 1)
    return math.sqrt(variance)
