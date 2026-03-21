"""Policy evaluation engine - core rule matching and authorization"""
import os
import time
from typing import Optional
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


class PolicyEvaluator:
    def __init__(self, site_id: str = "", site_type: str = "onprem", deployment_mode: str = "standalone"):
        self.policy_sets = []
        self.rules = []
        self.auth_profiles = {}
        self.policy_count = 0
        self.db_pool = None
        self.site_id = site_id
        self.site_type = site_type
        self.deployment_mode = deployment_mode

    async def load_policies(self):
        """Load all active policies from database into memory"""
        try:
            if self.db_pool is None:
                self.db_pool = await asyncpg.create_pool(POSTGRES_DSN, min_size=2, max_size=10)
                logger.info("DB pool created", min_size=2, max_size=10)
            async with self.db_pool.acquire() as conn:
                # Load policy sets
                rows = await conn.fetch(
                    "SELECT id, tenant_id, name, priority FROM policy_sets WHERE status='active' ORDER BY priority"
                )
                self.policy_sets = [dict(r) for r in rows]

                # Load rules
                rows = await conn.fetch(
                    """SELECT pr.id, pr.policy_set_id, pr.name, pr.priority, pr.conditions,
                              pr.auth_profile_id, pr.action
                       FROM policy_rules pr
                       JOIN policy_sets ps ON pr.policy_set_id = ps.id
                       WHERE pr.status='active' AND ps.status='active'
                       ORDER BY ps.priority, pr.priority"""
                )
                self.rules = [dict(r) for r in rows]

                # Load authorization profiles
                rows = await conn.fetch("SELECT * FROM authorization_profiles")
                self.auth_profiles = {str(r["id"]): dict(r) for r in rows}

                self.policy_count = len(self.rules)
                logger.info("Policies loaded", sets=len(self.policy_sets), rules=self.policy_count)
        except Exception as e:
            logger.error("Failed to load policies", error=str(e))
            self.policy_count = 0

    async def evaluate(self, request: dict) -> dict:
        """Evaluate a policy request against all rules, return authorization result"""
        start = time.monotonic()
        tenant_id = request.get("tenant_id", "")

        # Filter rules for this tenant
        tenant_rules = [r for r in self.rules if self._rule_matches_tenant(r, tenant_id)]

        # Evaluate each rule in priority order
        for rule in tenant_rules:
            if self._match_conditions(rule.get("conditions", []), request):
                auth_profile_id = str(rule.get("auth_profile_id", ""))
                profile = self.auth_profiles.get(auth_profile_id, {})
                elapsed_us = int((time.monotonic() - start) * 1_000_000)

                return {
                    "decision": {"type": rule.get("action", "permit"), "description": f"Matched rule: {rule['name']}"},
                    "matched_rule_id": str(rule["id"]),
                    "matched_rule_name": rule["name"],
                    "authorization": self._build_authorization(profile),
                    "evaluation_time_us": elapsed_us,
                    "site_id": self.site_id,
                    "site_type": self.site_type,
                }

        # Default deny
        elapsed_us = int((time.monotonic() - start) * 1_000_000)
        return {
            "decision": {"type": "deny", "description": "No matching rule found"},
            "matched_rule_id": None,
            "matched_rule_name": None,
            "authorization": {},
            "evaluation_time_us": elapsed_us,
            "site_id": self.site_id,
            "site_type": self.site_type,
        }

    def _rule_matches_tenant(self, rule: dict, tenant_id: str) -> bool:
        """Check if rule belongs to the requesting tenant (via policy set)"""
        for ps in self.policy_sets:
            if str(ps["id"]) == str(rule.get("policy_set_id")):
                return str(ps.get("tenant_id", "")) == tenant_id or tenant_id == ""
        return False

    def _match_conditions(self, conditions: list, request: dict) -> bool:
        """Evaluate all conditions against the request context"""
        if not conditions:
            return True

        for cond in conditions:
            attr = cond.get("attribute", "")
            operator = cond.get("operator", "equals")
            expected = cond.get("value", "")

            actual = self._resolve_attribute(attr, request)
            if actual is None:
                return False

            if not self._compare(actual, operator, expected):
                return False

        return True

    def _resolve_attribute(self, attr_path: str, request: dict) -> Optional[str]:
        """Resolve a dotted attribute path from the request context"""
        parts = attr_path.split(".")
        current = request
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
            if current is None:
                return None
        return str(current) if current is not None else None

    def _compare(self, actual: str, operator: str, expected: str) -> bool:
        """Compare actual value against expected using the given operator"""
        actual_lower = actual.lower()
        expected_lower = expected.lower()

        if operator == "equals":
            return actual_lower == expected_lower
        elif operator == "not_equals":
            return actual_lower != expected_lower
        elif operator == "contains":
            return expected_lower in actual_lower
        elif operator == "starts_with":
            return actual_lower.startswith(expected_lower)
        elif operator == "ends_with":
            return actual_lower.endswith(expected_lower)
        elif operator == "in":
            return actual_lower in [v.strip().lower() for v in expected.split(",")]
        elif operator == "not_in":
            return actual_lower not in [v.strip().lower() for v in expected.split(",")]
        elif operator == "matches":
            import re
            return bool(re.match(expected, actual, re.IGNORECASE))
        elif operator == "greater_than":
            try:
                return float(actual) > float(expected)
            except ValueError:
                return False
        elif operator == "less_than":
            try:
                return float(actual) < float(expected)
            except ValueError:
                return False
        elif operator == "between":
            try:
                parts = expected.split(",")
                if len(parts) == 2:
                    return float(parts[0]) <= float(actual) <= float(parts[1])
            except ValueError:
                pass
            return False
        elif operator == "is_true":
            return actual_lower in ("true", "1", "yes")
        elif operator == "is_false":
            return actual_lower in ("false", "0", "no")
        return False

    def _build_authorization(self, profile: dict) -> dict:
        """Build authorization result from an authorization profile"""
        if not profile:
            return {}
        return {
            "vlan_id": profile.get("vlan_id"),
            "vlan_name": profile.get("vlan_name"),
            "sgt_value": profile.get("sgt_value"),
            "dacl_id": str(profile.get("dacl_id", "")) if profile.get("dacl_id") else None,
            "ipsk": profile.get("ipsk"),
            "coa_action": profile.get("coa_action"),
            "group_policy": profile.get("group_policy"),
            "voice_domain": profile.get("voice_domain", False),
            "redirect_url": profile.get("redirect_url"),
            "session_timeout": profile.get("session_timeout"),
            "bandwidth_limit_mbps": profile.get("bandwidth_limit_mbps"),
            "destination_whitelist": profile.get("destination_whitelist", []),
            "vendor_attributes": profile.get("vendor_attributes", {}),
        }
