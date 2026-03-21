"""NLP Policy Assistant - translates natural language to policy rules"""
import os
import httpx
import structlog

logger = structlog.get_logger()

LLM_API_URL = os.getenv("AI_LLM_API_URL", "http://localhost:11434/api/generate")
LLM_MODEL = os.getenv("AI_LLM_MODEL", "llama3.1:8b")

SYSTEM_PROMPT = """You are an NeuraNAC policy assistant. Convert natural language network access requirements into structured policy rules.

Output JSON with this structure:
{
  "rules": [
    {
      "name": "rule name",
      "priority": 1,
      "conditions": [{"attribute": "identity.groups", "operator": "contains", "value": "Engineering"}],
      "authorization_profile": "Full_Access",
      "action": "permit"
    }
  ],
  "explanation": "Brief explanation of what these rules do"
}

Available attributes:
- identity.username, identity.groups, identity.domain, identity.source
- network.nas_ip, network.device_vendor, network.site_id
- endpoint.mac_address, endpoint.device_type, endpoint.posture_status, endpoint.vendor
- auth.eap_type, auth.auth_type
- ai.agent_type, ai.risk_score, ai.shadow_ai_detected, ai.delegation_depth

Available operators: equals, not_equals, contains, starts_with, ends_with, in, matches, greater_than, less_than

Available actions: permit, deny, quarantine, redirect"""


class NLPolicyAssistant:
    async def translate(self, natural_language: str, context: str = "") -> dict:
        """Translate natural language to structured policy rules"""
        if not natural_language:
            return {"success": False, "rules": [], "explanation": "No input provided"}

        prompt = f"{SYSTEM_PROMPT}\n\nContext: {context}\n\nUser request: {natural_language}\n\nGenerate the policy rules JSON:"

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    LLM_API_URL,
                    json={"model": LLM_MODEL, "prompt": prompt, "stream": False, "format": "json"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    response_text = data.get("response", "")
                    import json
                    try:
                        parsed = json.loads(response_text)
                        return {
                            "success": True,
                            "rules": parsed.get("rules", []),
                            "explanation": parsed.get("explanation", ""),
                            "confidence": "high" if len(parsed.get("rules", [])) > 0 else "low",
                        }
                    except json.JSONDecodeError:
                        return {"success": False, "rules": [], "explanation": "Failed to parse LLM response"}
                else:
                    logger.warning("LLM API error", status=resp.status_code)
        except Exception as e:
            logger.warning("LLM unavailable, using template matching", error=str(e))

        # Fallback: template-based matching
        return self._template_match(natural_language)

    def _template_match(self, text: str) -> dict:
        """Simple template matching when LLM is unavailable"""
        text_lower = text.lower()
        rules = []

        if "block" in text_lower and "ai" in text_lower:
            rules.append({
                "name": "Block AI Traffic",
                "priority": 1,
                "conditions": [{"attribute": "ai.shadow_ai_detected", "operator": "equals", "value": "true"}],
                "authorization_profile": "Deny_Access",
                "action": "deny",
            })
        elif "allow" in text_lower and "employee" in text_lower:
            rules.append({
                "name": "Allow Employees",
                "priority": 1,
                "conditions": [{"attribute": "identity.groups", "operator": "contains", "value": "Employees"}],
                "authorization_profile": "Full_Access",
                "action": "permit",
            })
        elif "guest" in text_lower:
            rules.append({
                "name": "Guest Access",
                "priority": 10,
                "conditions": [{"attribute": "auth.auth_type", "operator": "equals", "value": "guest"}],
                "authorization_profile": "Guest_Limited",
                "action": "permit",
            })
        elif "quarantine" in text_lower and "noncompliant" in text_lower:
            rules.append({
                "name": "Quarantine Noncompliant",
                "priority": 5,
                "conditions": [{"attribute": "endpoint.posture_status", "operator": "equals", "value": "noncompliant"}],
                "authorization_profile": "Quarantine_VLAN",
                "action": "quarantine",
            })

        return {
            "success": len(rules) > 0,
            "rules": rules,
            "explanation": f"Template-matched {len(rules)} rule(s) from input",
            "confidence": "medium" if rules else "low",
        }
