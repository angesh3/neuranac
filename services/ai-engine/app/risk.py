"""AI Risk Scoring Engine - computes composite risk scores for sessions"""
import structlog

logger = structlog.get_logger()


class RiskScorer:
    async def compute(self, request: dict) -> dict:
        """Compute a multi-dimensional risk score (0-100)"""
        behavioral = self._behavioral_score(request)
        identity = self._identity_score(request)
        endpoint = self._endpoint_score(request)
        ai_activity = self._ai_activity_score(request)

        total = min(100, behavioral + identity + endpoint + ai_activity)
        risk_level = "low" if total < 30 else "medium" if total < 60 else "high" if total < 80 else "critical"

        factors = []
        if behavioral > 10:
            factors.append({"category": "behavioral", "description": "Unusual auth pattern", "score_contribution": behavioral})
        if identity > 10:
            factors.append({"category": "identity", "description": "Identity risk factors", "score_contribution": identity})
        if endpoint > 10:
            factors.append({"category": "endpoint", "description": "Endpoint posture concerns", "score_contribution": endpoint})
        if ai_activity > 10:
            factors.append({"category": "ai_activity", "description": "AI activity risk", "score_contribution": ai_activity})

        return {
            "total_score": total,
            "risk_level": risk_level,
            "behavioral_score": behavioral,
            "identity_score": identity,
            "endpoint_score": endpoint,
            "ai_activity_score": ai_activity,
            "factors": factors,
        }

    def _behavioral_score(self, req: dict) -> int:
        score = 0
        failed = req.get("failed_auth_count_24h", 0)
        if failed > 10:
            score += 25
        elif failed > 5:
            score += 15
        elif failed > 2:
            score += 5
        return min(25, score)

    def _identity_score(self, req: dict) -> int:
        score = 0
        if not req.get("username"):
            score += 10
        groups = req.get("user_groups", [])
        if not groups:
            score += 5
        if req.get("identity_source") == "internal":
            score += 2
        return min(25, score)

    def _endpoint_score(self, req: dict) -> int:
        score = 0
        posture = req.get("posture_status", "unknown")
        if posture == "noncompliant":
            score += 20
        elif posture == "unknown":
            score += 10
        if req.get("running_local_llm"):
            score += 5
        return min(25, score)

    def _ai_activity_score(self, req: dict) -> int:
        score = 0
        if req.get("shadow_ai_detected"):
            score += 30
        depth = req.get("ai_delegation_depth", 0)
        if depth > 2:
            score += 15
        elif depth > 0:
            score += 5
        upload_mb = req.get("ai_data_upload_mb", 0)
        if upload_mb > 100:
            score += 20
        elif upload_mb > 10:
            score += 5
        return score
