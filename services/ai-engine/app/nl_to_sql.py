"""
Natural Language to SQL — translates user questions into safe, read-only SQL queries
against the NeuraNAC PostgreSQL schema. Uses pattern matching with optional LLM fallback.
"""
import os
import re
import json
import structlog
import httpx
from typing import Dict, Any, Optional, List

logger = structlog.get_logger()

LLM_API_URL = os.getenv("AI_LLM_API_URL", "http://localhost:11434/api/generate")
LLM_MODEL = os.getenv("AI_LLM_MODEL", "llama3.1:8b")
PG_DSN = os.getenv("AI_PG_DSN", "postgresql://neuranac:neuranac@localhost:5432/neuranac")

# ─── Schema summary for LLM context ──────────────────────────────────────────

SCHEMA_SUMMARY = """
Tables:
- admin_users (id UUID, username TEXT, email TEXT, role TEXT, status TEXT, failed_attempts INT, created_at TIMESTAMPTZ)
- auth_sessions (id UUID, session_id TEXT, username TEXT, endpoint_mac TEXT, nas_ip TEXT, auth_method TEXT, auth_result TEXT, vlan TEXT, sgt TEXT, started_at TIMESTAMPTZ, ended_at TIMESTAMPTZ)
- network_devices (id UUID, tenant_id UUID, name TEXT, ip_address TEXT, device_type TEXT, vendor TEXT, model TEXT, location TEXT, status TEXT, created_at TIMESTAMPTZ)
- endpoints (id UUID, tenant_id UUID, mac_address TEXT, ip_address TEXT, hostname TEXT, device_type TEXT, vendor TEXT, os TEXT, status TEXT, first_seen TIMESTAMPTZ, last_seen TIMESTAMPTZ)
- policies (id UUID, tenant_id UUID, name TEXT, description TEXT, match_type TEXT, enabled BOOLEAN, priority INT, created_at TIMESTAMPTZ)
- policy_rules (id UUID, policy_id UUID, name TEXT, action TEXT, priority INT)
- identity_sources (id UUID, tenant_id UUID, name TEXT, source_type TEXT, status TEXT)
- certificates (id UUID, tenant_id UUID, subject TEXT, issuer TEXT, serial_number TEXT, not_before TIMESTAMPTZ, not_after TIMESTAMPTZ, cert_type TEXT)
- sgts (id UUID, tenant_id UUID, name TEXT, tag_value INT, description TEXT)
- guest_accounts (id UUID, tenant_id UUID, username TEXT, email TEXT, sponsor TEXT, status TEXT, valid_from TIMESTAMPTZ, valid_until TIMESTAMPTZ)
- ai_agents (id UUID, tenant_id UUID, agent_id TEXT, name TEXT, status TEXT, risk_level TEXT, registered_at TIMESTAMPTZ)
- ai_data_flow_detections (id UUID, tenant_id UUID, endpoint_mac TEXT, service_type TEXT, action TEXT, detected_at TIMESTAMPTZ)
- legacy_nac_connections (id UUID, tenant_id UUID, name TEXT, hostname TEXT, status TEXT, legacy_nac_version TEXT)
- audit_log (id UUID, tenant_id UUID, actor TEXT, action TEXT, resource_type TEXT, details JSONB, created_at TIMESTAMPTZ)
"""

# ─── Pattern-based query templates ────────────────────────────────────────────

QUERY_PATTERNS: List[Dict[str, Any]] = [
    {"patterns": ["how many session", "count session", "total session", "session count"],
     "sql": "SELECT COUNT(*) as total_sessions FROM auth_sessions",
     "description": "Count all authentication sessions"},
    {"patterns": ["active session", "current session"],
     "sql": "SELECT COUNT(*) as active_sessions FROM auth_sessions WHERE ended_at IS NULL",
     "description": "Count active (ongoing) sessions"},
    {"patterns": ["failed.*session", "failed.*auth", "reject", "denied"],
     "sql": "SELECT COUNT(*) as failed, endpoint_mac, username FROM auth_sessions WHERE auth_result='reject' GROUP BY endpoint_mac, username ORDER BY failed DESC LIMIT 20",
     "description": "Show endpoints/users with failed authentications"},
    {"patterns": ["how many endpoint", "count endpoint", "total endpoint"],
     "sql": "SELECT COUNT(*) as total_endpoints FROM endpoints",
     "description": "Count all endpoints"},
    {"patterns": ["how many device", "count device", "total device", "network device count"],
     "sql": "SELECT COUNT(*) as total_devices FROM network_devices",
     "description": "Count network devices"},
    {"patterns": ["how many polic", "count polic", "total polic"],
     "sql": "SELECT COUNT(*) as total_policies FROM policies",
     "description": "Count policies"},
    {"patterns": ["expired cert", "expiring cert", "cert.*expir"],
     "sql": "SELECT subject, issuer, not_after, cert_type FROM certificates WHERE not_after < NOW() + INTERVAL '30 days' ORDER BY not_after ASC LIMIT 20",
     "description": "Certificates expiring within 30 days"},
    {"patterns": ["top.*vendor", "vendor.*distribution", "vendor breakdown"],
     "sql": "SELECT vendor, COUNT(*) as count FROM endpoints GROUP BY vendor ORDER BY count DESC LIMIT 15",
     "description": "Endpoint vendor distribution"},
    {"patterns": ["top.*device.*type", "device.*type.*distribution"],
     "sql": "SELECT device_type, COUNT(*) as count FROM endpoints GROUP BY device_type ORDER BY count DESC LIMIT 15",
     "description": "Endpoint device type distribution"},
    {"patterns": ["auth.*method.*distribution", "eap.*distribution", "auth.*breakdown"],
     "sql": "SELECT auth_method, COUNT(*) as count FROM auth_sessions GROUP BY auth_method ORDER BY count DESC",
     "description": "Authentication method distribution"},
    {"patterns": ["recent.*session", "latest.*session", "last.*session"],
     "sql": "SELECT session_id, username, endpoint_mac, nas_ip, auth_method, auth_result, started_at FROM auth_sessions ORDER BY started_at DESC LIMIT 20",
     "description": "Most recent sessions"},
    {"patterns": ["recent.*audit", "latest.*audit", "last.*audit"],
     "sql": "SELECT actor, action, resource_type, details, created_at FROM audit_log ORDER BY created_at DESC LIMIT 20",
     "description": "Recent audit log entries"},
    {"patterns": ["shadow.*ai", "ai.*detection", "unauthorized.*ai"],
     "sql": "SELECT endpoint_mac, service_type, action, detected_at FROM ai_data_flow_detections ORDER BY detected_at DESC LIMIT 20",
     "description": "Recent shadow AI detections"},
    {"patterns": ["guest.*account", "active.*guest"],
     "sql": "SELECT username, email, sponsor, status, valid_until FROM guest_accounts WHERE status='active' ORDER BY valid_until ASC LIMIT 20",
     "description": "Active guest accounts"},
    {"patterns": ["legacy.*connection", "legacy.*status"],
     "sql": "SELECT name, hostname, status, legacy_nac_version FROM legacy_nac_connections ORDER BY name",
     "description": "legacy connection status"},
    {"patterns": ["sgt", "security.*group", "trustsec"],
     "sql": "SELECT name, tag_value, description FROM sgts ORDER BY tag_value",
     "description": "Security Group Tags"},
    {"patterns": ["identity.*source", "ldap", "active.*directory"],
     "sql": "SELECT name, source_type, status FROM identity_sources ORDER BY name",
     "description": "Identity sources"},
    {"patterns": ["user.*list", "admin.*user", "all.*user"],
     "sql": "SELECT username, email, role, status, created_at FROM admin_users ORDER BY created_at DESC LIMIT 20",
     "description": "Admin users"},
]

# SQL keywords that are NOT allowed (write operations)
FORBIDDEN_SQL = re.compile(
    r'\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|GRANT|REVOKE|EXEC|EXECUTE)\b',
    re.IGNORECASE
)


class NLToSQL:
    """Translates natural language questions into safe SQL queries."""

    def __init__(self):
        self._pg_pool = None
        self._llm_available = False

    async def initialize(self):
        """Initialize database connection and check LLM availability."""
        try:
            import asyncpg
            self._pg_pool = await asyncpg.create_pool(PG_DSN, min_size=1, max_size=3)
            logger.info("NL-to-SQL: DB connected")
        except Exception as e:
            logger.warning("NL-to-SQL: DB unavailable", error=str(e))

        try:
            async with httpx.AsyncClient(timeout=3) as client:
                resp = await client.get(LLM_API_URL.replace("/api/generate", "/api/tags"))
                self._llm_available = resp.status_code == 200
        except Exception:
            self._llm_available = False
        logger.info("NL-to-SQL initialized", db_available=self._pg_pool is not None, llm=self._llm_available)

    async def translate_and_execute(self, question: str) -> Dict[str, Any]:
        """Translate a natural language question to SQL, execute it, and return results."""
        # Step 1: Match against known patterns
        sql, description = self._pattern_match(question)

        # Step 2: If no pattern match, try LLM
        if sql is None and self._llm_available:
            sql, description = await self._llm_translate(question)

        if sql is None:
            return {
                "status": "no_match",
                "message": "I couldn't translate that question into a database query. Try asking about sessions, endpoints, devices, policies, certificates, or audit logs.",
                "suggestions": [
                    "How many active sessions?",
                    "Show failed authentications",
                    "Which certificates are expiring?",
                    "Top endpoint vendors",
                ],
            }

        # Step 3: Safety check
        if FORBIDDEN_SQL.search(sql):
            return {"status": "blocked", "message": "Write operations are not allowed through NL-to-SQL."}

        # Step 4: Execute with parameterized query when possible
        if self._pg_pool:
            try:
                sql, params = self._parameterize_query(sql)
                rows = await self._pg_pool.fetch(sql, *params)
                results = [dict(r) for r in rows]
                # Convert datetime objects to strings
                for row in results:
                    for k, v in row.items():
                        if hasattr(v, 'isoformat'):
                            row[k] = v.isoformat()
                return {
                    "status": "ok",
                    "sql": sql,
                    "description": description,
                    "results": results,
                    "row_count": len(results),
                }
            except Exception as e:
                return {"status": "error", "sql": sql, "message": f"Query execution failed: {str(e)}"}
        else:
            return {
                "status": "preview",
                "sql": sql,
                "description": description,
                "message": "Database not connected. Here is the generated SQL query.",
            }

    def _pattern_match(self, question: str) -> tuple:
        """Match question against known patterns."""
        q_lower = question.lower()
        for template in QUERY_PATTERNS:
            for pattern in template["patterns"]:
                if re.search(pattern, q_lower):
                    return template["sql"], template["description"]
        return None, None

    @staticmethod
    def _parameterize_query(sql: str) -> tuple:
        """Extract inline string literals and replace them with positional parameters.

        This adds defense-in-depth against SQL injection from LLM-generated
        queries by converting inline values into parameterized placeholders.
        Pattern-matched queries are already safe (no user input), but LLM
        fallback queries may contain injected literals.

        Returns (parameterized_sql, params_tuple).
        """
        params = []
        counter = [0]

        def replacer(match):
            counter[0] += 1
            value = match.group(1)
            params.append(value)
            return f"${counter[0]}"

        # Replace single-quoted string literals with positional params
        # Matches 'value' but not escaped quotes
        parameterized = re.sub(r"'([^']*)'", replacer, sql)
        return parameterized, tuple(params)

    async def _llm_translate(self, question: str) -> tuple:
        """Use LLM to generate SQL from natural language."""
        prompt = f"""You are a PostgreSQL query generator for NeuraNAC (NeuraNAC).
Given the schema below, translate the user's question into a single read-only SELECT query.

{SCHEMA_SUMMARY}

RULES:
- Only SELECT queries allowed. No INSERT, UPDATE, DELETE, DROP, ALTER.
- Always include LIMIT 50 for safety.
- Use standard PostgreSQL syntax.
- Return ONLY the SQL query, nothing else.

Question: {question}

SQL:"""

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(LLM_API_URL, json={
                    "model": LLM_MODEL, "prompt": prompt, "stream": False, "temperature": 0.1,
                })
                text = resp.json().get("response", "").strip()
                # Extract SQL from response
                sql_match = re.search(r'(SELECT\s.+?)(?:;|$)', text, re.IGNORECASE | re.DOTALL)
                if sql_match:
                    sql = sql_match.group(1).strip().rstrip(';')
                    # Safety check
                    if FORBIDDEN_SQL.search(sql):
                        return None, None
                    return sql, "LLM-generated query"
        except Exception as e:
            logger.error("LLM SQL generation failed", error=str(e))
        return None, None
