"""AI Action Router — LLM-powered intent classifier + function dispatcher.

Maps natural language prompts to NeuraNAC API calls and returns structured responses.

Decomposed structure:
  app/intents/           — domain-specific intent definitions
  app/intents/field_extractor.py — NLP field extraction from messages
  app/action_router.py   — orchestrator (this file)
"""
import os
import re
import json
import httpx
import structlog
from typing import Any, Dict, List, Optional

from app.intents import ALL_INTENTS, NAVIGATION_INTENTS
from app.intents.field_extractor import extract_fields
from app.intents.nac_knowledge import find_best_article

logger = structlog.get_logger()

LLM_API_URL = os.getenv("AI_LLM_API_URL", "http://localhost:11434/api/generate")
LLM_MODEL = os.getenv("AI_LLM_MODEL", "llama3.1:8b")
API_GATEWAY_URL = os.getenv("API_GATEWAY_URL", "http://localhost:8080")
INTERNAL_SERVICE_KEY = os.getenv("INTERNAL_SERVICE_KEY", "neuranac_internal_dev_key_change_in_production")


class ActionRouter:
    """Routes natural language to API actions using pattern matching + optional LLM."""

    def __init__(self):
        self.intents = ALL_INTENTS
        self.nav_intents = NAVIGATION_INTENTS
        self._llm_available = False

    async def check_llm(self):
        """Check if LLM is available."""
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                resp = await client.get(LLM_API_URL.replace("/api/generate", "/api/tags"))
                self._llm_available = resp.status_code == 200
        except Exception:
            self._llm_available = False
        logger.info("LLM availability", available=self._llm_available)

    # Patterns that signal an informational/explanatory query (not an action)
    _INFORMATIONAL_SIGNALS = re.compile(
        r"^(what is|what are|what does|what about|what'?s|explain|describe|tell me|"
        r"how does|how do|how is|how are|how can|can you explain|"
        r"teach me|help me understand|walk me through|give me|"
        r"why is|why does|why do|why are|"
        r"define|meaning of|difference between|"
        r"when (should|do|is|would)|where (do|is|can)|"
        r"overview|introduction|concept|info about|details about|"
        r"learn about|understand|curious about|"
        r"how .+ work)\b",
        re.IGNORECASE,
    )

    def _is_informational(self, msg_lower: str) -> bool:
        """Detect if a query is asking for information/explanation vs requesting an action."""
        if self._INFORMATIONAL_SIGNALS.search(msg_lower):
            return True
        # Also treat queries ending with '?' as likely informational
        if msg_lower.rstrip().endswith("?"):
            return True
        return False

    def _try_nac_knowledge(self, message: str) -> Optional[Dict[str, Any]]:
        """Try to find a matching NAC knowledge article."""
        article, score = find_best_article(message)
        if article:
            logger.info("NAC knowledge match", article=article["id"], score=score, query=message)
            return {
                "type": "text",
                "message": article["content"],
                "intent": f"nac_kb:{article['id']}",
            }
        return None

    async def route(self, message: str, context: Optional[Dict] = None, token: Optional[str] = None) -> Dict[str, Any]:
        """Route a natural language message to the appropriate action and execute it."""
        msg_lower = message.lower().strip()
        is_info_query = self._is_informational(msg_lower)

        # 1. Check navigation intents first
        for nav_id, nav in self.nav_intents.items():
            for pattern in nav["patterns"]:
                if re.search(pattern, msg_lower):
                    return {
                        "type": "navigation",
                        "route": nav["route"],
                        "message": f"Navigating to {nav['route']}",
                        "intent": nav_id,
                    }

        # 2. Match action/knowledge intents via pattern matching
        best_match = None
        best_score = 0
        for intent_def in self.intents:
            for pattern in intent_def["patterns"]:
                if re.search(pattern, msg_lower):
                    score = len(pattern)
                    if score > best_score:
                        best_score = score
                        best_match = intent_def

        # 3. If NLP policy passthrough, route the whole message
        if best_match and best_match.get("passthrough"):
            return await self._execute_nlp_translate(message, token)

        # 4. Handle knowledge intents (product questions — no API call needed)
        if best_match and "knowledge" in best_match:
            return {
                "type": "text",
                "message": best_match["knowledge"],
                "intent": best_match["intent"],
            }

        # 5. For INFORMATIONAL queries WITHOUT a matched action intent,
        #    try NAC knowledge base. This prevents "What about posture?" from
        #    calling the list_posture API, but lets "How many sessions?" execute.
        if is_info_query and not best_match:
            nac_resp = self._try_nac_knowledge(message)
            if nac_resp:
                return nac_resp

        # 6. Execute matched action intent
        if best_match:
            return await self._execute_intent(best_match, message, token)

        # 7. Try fuzzy product knowledge match (before LLM — cheaper and faster)
        knowledge_resp = self._fuzzy_knowledge_match(msg_lower)
        if knowledge_resp:
            return knowledge_resp

        # 8. Try NAC knowledge base scoring (for queries that had no match)
        nac_resp = self._try_nac_knowledge(message)
        if nac_resp:
            return nac_resp

        # 9. Try LLM for unrecognized intents
        if self._llm_available:
            return await self._llm_route(message, token)

        return {
            "type": "text",
            "message": self._fallback_response(message),
            "intent": "unknown",
        }

    async def _execute_intent(self, intent_def: Dict, original_msg: str, token: Optional[str] = None) -> Dict[str, Any]:
        """Execute an API call for a matched intent."""
        path = intent_def["path"]
        method = intent_def["method"]

        # Extract fields from message if needed
        body = None
        if "extract_fields" in intent_def and method in ("POST", "PUT"):
            body = await self._extract_fields(intent_def, original_msg)

        # Make the API call
        headers = {
            "Content-Type": "application/json",
            "X-Internal-Service-Key": INTERNAL_SERVICE_KEY,
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                url = f"{API_GATEWAY_URL}{path}"
                if method == "GET":
                    resp = await client.get(url, headers=headers)
                elif method == "POST":
                    resp = await client.post(url, json=body or {}, headers=headers)
                elif method == "PUT":
                    resp = await client.put(url, json=body or {}, headers=headers)
                elif method == "DELETE":
                    resp = await client.delete(url, headers=headers)
                else:
                    resp = await client.get(url, headers=headers)

                data = None
                try:
                    data = resp.json()
                except Exception:
                    pass

                return {
                    "type": "api_result",
                    "intent": intent_def["intent"],
                    "description": intent_def["description"],
                    "method": method,
                    "path": path,
                    "status_code": resp.status_code,
                    "data": data,
                    "message": self._format_response(intent_def, data, resp.status_code),
                }
        except Exception as e:
            logger.error("Action router API call failed", error=str(e), intent=intent_def["intent"])
            return {
                "type": "error",
                "intent": intent_def["intent"],
                "message": f"Failed to execute {intent_def['description']}: {str(e)}",
            }

    async def _execute_nlp_translate(self, message: str, token: Optional[str] = None) -> Dict[str, Any]:
        """Forward to NLP policy translation endpoint."""
        headers = {
            "Content-Type": "application/json",
            "X-Internal-Service-Key": INTERNAL_SERVICE_KEY,
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{API_GATEWAY_URL}/api/v1/ai/nlp/translate",
                    json={"natural_language": message, "context": ""},
                    headers=headers,
                )
                data = resp.json()
                return {
                    "type": "policy_translation",
                    "intent": "translate_policy",
                    "data": data,
                    "message": data.get("explanation", "Policy rules generated from your request."),
                }
        except Exception as e:
            return {"type": "error", "intent": "translate_policy", "message": f"NLP translation failed: {e}"}

    async def _extract_fields(self, intent_def: Dict, message: str) -> Dict[str, Any]:
        """Extract structured fields from natural language using the field_extractor module."""
        return extract_fields(intent_def, message)

    async def _llm_route(self, message: str, token: Optional[str] = None) -> Dict[str, Any]:
        """Use LLM to classify intent when pattern matching fails."""
        intent_list = "\n".join(f"- {i['intent']}: {i['description']}" for i in self.intents[:20])
        prompt = f"""You are NeuraNAC AI assistant. Classify the user's message into one of these intents:
{intent_list}

If none match, respond with intent "general_help" and provide a helpful answer about NeuraNAC (NeuraNAC).

User message: "{message}"

Respond ONLY with JSON: {{"intent": "...", "message": "your helpful response"}}"""

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(LLM_API_URL, json={
                    "model": LLM_MODEL, "prompt": prompt, "stream": False, "temperature": 0.1,
                })
                text = resp.json().get("response", "")
                # Try to parse JSON from response
                m = re.search(r'\{[^}]+\}', text, re.DOTALL)
                if m:
                    parsed = json.loads(m.group())
                    matched_intent = parsed.get("intent", "general_help")
                    # If matched a known intent, execute it
                    for intent_def in self.intents:
                        if intent_def["intent"] == matched_intent:
                            return await self._execute_intent(intent_def, message, token)
                    return {"type": "text", "intent": matched_intent, "message": parsed.get("message", text)}
                return {"type": "text", "intent": "general_help", "message": text}
        except Exception as e:
            logger.error("LLM routing failed", error=str(e))
            return {"type": "text", "intent": "unknown", "message": self._fallback_response(message)}

    def _format_response(self, intent_def: Dict, data: Any, status_code: int) -> str:
        """Format API response into a human-readable message."""
        if status_code >= 400:
            error_msg = ""
            if isinstance(data, dict):
                error_msg = data.get("error", data.get("detail", str(data)))
            return f"Request failed (HTTP {status_code}): {error_msg}"

        intent = intent_def["intent"]

        if data is None:
            return f"Action completed successfully (HTTP {status_code})."

        # Format list responses
        if isinstance(data, dict):
            items = data.get("items", data.get("results", []))
            total = data.get("total", len(items) if isinstance(items, list) else 0)

            if isinstance(items, list) and len(items) > 0:
                return f"Found {total} result(s). Showing the data below."

            if "status" in data:
                return f"Status: {data['status']}"

            if total == 0 and isinstance(items, list):
                return f"No results found for {intent_def['description'].lower()}."

        return f"{intent_def['description']} completed successfully."

    def _fuzzy_knowledge_match(self, msg_lower: str) -> Optional[Dict[str, Any]]:
        """Try to match product-related keywords when pattern matching fails."""
        keyword_map = {
            "product": "product_overview",
            "neuranac": "product_overview",
            "platform": "product_overview",
            "application": "product_overview",
            "tool": "product_overview",
            "feature": "product_features",
            "capabilit": "product_features",
            "functionalit": "product_features",
            "architect": "product_architecture",
            "tech stack": "product_architecture",
            "microservice": "product_architecture",
            "start": "product_howto",
            "begin": "product_howto",
            "onboard": "product_howto",
            "tutorial": "product_howto",
            "migrat": "legacy_nac_migration_info",
            "secur": "security_features",
            "zero trust": "security_features",
            "threat": "security_features",
            "twin": "twin_node_info",
            "replicat": "twin_node_info",
            "high availab": "twin_node_info",
            "failover": "twin_node_info",
            "competitor": "legacy_nac_comparison",
            "competiti": "legacy_nac_comparison",
            "alternativ": "legacy_nac_comparison",
            "different": "legacy_nac_comparison",
            "compar": "legacy_nac_comparison",
            "vs": "legacy_nac_comparison",
            "better": "legacy_nac_comparison",
            "unique": "legacy_nac_comparison",
            "stand out": "legacy_nac_comparison",
            "advantage": "legacy_nac_comparison",
            "policy": "policy_howto",
            "rule": "policy_howto",
            "configure": "policy_howto",
            "troubleshoot": "troubleshooting_howto",
            "debug": "troubleshooting_howto",
            "diagnos": "troubleshooting_howto",
            "not working": "troubleshooting_howto",
            "failing": "troubleshooting_howto",
            "broken": "troubleshooting_howto",
            "endpoint": "endpoint_howto",
            "device": "device_howto",
            "switch": "device_howto",
            "router": "device_howto",
        }
        for keyword, intent_id in keyword_map.items():
            if keyword in msg_lower:
                for intent_def in self.intents:
                    if intent_def.get("intent") == intent_id and "knowledge" in intent_def:
                        return {
                            "type": "text",
                            "message": intent_def["knowledge"],
                            "intent": intent_id,
                        }
        return None

    def _fallback_response(self, message: str) -> str:
        """Generate a fallback response when no intent matches."""
        return (
            "I'm not sure how to help with that specific request. Here's what I can do:\n\n"
            "**💬 Ask me about NeuraNAC:**\n"
            "- *\"What is this product?\"* — product overview\n"
            "- *\"What can you do?\"* — full list of AI Agent capabilities\n"
            "- *\"How do I get started?\"* — onboarding guide\n\n"
            "**🔍 View & Manage:**\n"
            "- *\"Show all endpoints\"* / *\"List network devices\"* / *\"Show sessions\"*\n"
            "- *\"Show system status\"* / *\"Show audit log\"*\n\n"
            "**⚙️ Create & Configure:**\n"
            "- *\"Create a policy named Corporate Access\"*\n"
            "- *\"Add switch 10.0.0.1 with secret Cisco123\"*\n"
            "- *\"Block all traffic to OpenAI\"*\n\n"
            "**🤖 AI & Analytics:**\n"
            "- *\"Show shadow AI detections\"* / *\"Check anomalies\"*\n"
            "- *\"Compute risk score\"* / *\"Analyze policy drift\"*\n\n"
            "**🔧 Troubleshoot:**\n"
            "- *\"Why is user jdoe failing auth?\"* / *\"Check RADIUS log\"*\n\n"
            "**🧭 Navigate:**\n"
            "- *\"Go to policies\"* / *\"Open NeuraNAC integration\"* / *\"Open settings\"*\n\n"
            "Try asking about a specific feature or action!"
        )
