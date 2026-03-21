"""Field extraction from natural language messages.

Extracts structured fields (name, ip_address, vendor, etc.) from
free-text user messages for POST/PUT API calls.
"""
import re
from typing import Any, Dict


def extract_fields(intent_def: Dict, message: str) -> Dict[str, Any]:
    """Extract structured fields from a natural language message."""
    body: Dict[str, Any] = {}
    msg_lower = message.lower()
    fields = intent_def.get("extract_fields", [])

    for field in fields:
        extractor = _EXTRACTORS.get(field)
        if extractor:
            value = extractor(message, msg_lower, intent_def)
            if value is not None:
                body[field] = value

    return body


def _extract_name(message: str, msg_lower: str, intent_def: Dict) -> str:
    m = re.search(r'(?:named?|called?)\s+"?([^"]+)"?', message, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    m = re.search(r'"([^"]+)"', message)
    if m:
        return m.group(1)
    return f"AI-Created-{intent_def['intent']}"


def _extract_ip(message: str, msg_lower: str, _: Dict):
    m = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', message)
    return m.group(1) if m else None


def _extract_subnet(message: str, msg_lower: str, _: Dict):
    m = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/\d{1,2})', message)
    return m.group(1) if m else None


def _extract_device_type(message: str, msg_lower: str, _: Dict) -> str:
    for dt in ["switch", "router", "wireless", "firewall", "ap"]:
        if dt in msg_lower:
            return dt
    return "switch"


def _extract_vendor(message: str, msg_lower: str, _: Dict) -> str:
    for v in ["cisco", "aruba", "juniper", "fortinet", "dell", "ruckus", "extreme"]:
        if v in msg_lower:
            return v
    return "cisco"


def _extract_shared_secret(message: str, msg_lower: str, _: Dict) -> str:
    m = re.search(r'(?:secret|key)\s+"?([^\s"]+)"?', message, re.IGNORECASE)
    return m.group(1) if m else "NeuraNACDefault123!"


def _extract_description(message: str, msg_lower: str, _: Dict) -> str:
    return message[:200]


def _extract_match_type(message: str, msg_lower: str, _: Dict) -> str:
    return "all"


def _extract_tag_value(message: str, msg_lower: str, _: Dict):
    m = re.search(r'(?:tag|value)\s+(\d+)', message, re.IGNORECASE)
    return int(m.group(1)) if m else None


def _extract_service_type(message: str, msg_lower: str, _: Dict) -> str:
    for svc in ["openai", "anthropic", "google", "copilot", "huggingface", "cohere"]:
        if svc in msg_lower:
            return svc
    return "all"


def _extract_action(message: str, msg_lower: str, _: Dict) -> str:
    if "block" in msg_lower:
        return "block"
    if "monitor" in msg_lower:
        return "monitor"
    return "allow"


def _extract_target(message: str, msg_lower: str, _: Dict) -> str:
    m = re.search(r'([A-Fa-f0-9]{2}:[A-Fa-f0-9]{2}:[A-Fa-f0-9]{2}:[A-Fa-f0-9]{2}:[A-Fa-f0-9]{2}:[A-Fa-f0-9]{2})', message)
    return m.group(1) if m else "unknown"


def _extract_issue_type(message: str, msg_lower: str, _: Dict) -> str:
    if "auth" in msg_lower or "fail" in msg_lower:
        return "auth_failure"
    if "vlan" in msg_lower:
        return "vlan_assignment"
    if "slow" in msg_lower or "latency" in msg_lower:
        return "performance"
    return "general"


def _extract_id(message: str, msg_lower: str, _: Dict):
    m = re.search(r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})', message, re.IGNORECASE)
    return m.group(1) if m else None


_EXTRACTORS = {
    "name": _extract_name,
    "ip_address": _extract_ip,
    "subnet": _extract_subnet,
    "device_type": _extract_device_type,
    "vendor": _extract_vendor,
    "shared_secret": _extract_shared_secret,
    "description": _extract_description,
    "match_type": _extract_match_type,
    "tag_value": _extract_tag_value,
    "service_type": _extract_service_type,
    "action": _extract_action,
    "target": _extract_target,
    "issue_type": _extract_issue_type,
    "id": _extract_id,
}
