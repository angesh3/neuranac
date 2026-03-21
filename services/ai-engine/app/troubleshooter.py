"""AI Troubleshooter - diagnoses authentication and network issues"""
import structlog

logger = structlog.get_logger()


class AITroubleshooter:
    async def analyze(self, request: dict) -> dict:
        """Analyze an issue and provide root cause + recommended fixes"""
        query = request.get("query", "")
        session_id = request.get("session_id", "")
        endpoint_mac = request.get("endpoint_mac", "")
        username = request.get("username", "")

        # Common troubleshooting patterns
        issues = []
        fixes = []
        evidence = []
        root_cause = "Unable to determine root cause"

        query_lower = query.lower()

        if "authentication" in query_lower and "fail" in query_lower:
            root_cause = "Authentication failure detected"
            issues = ["Certificate mismatch", "Expired credentials", "Wrong EAP type", "Identity source unreachable"]
            fixes = [
                "Verify the endpoint certificate is signed by a trusted CA",
                "Check identity source connectivity (LDAP/AD)",
                "Ensure EAP type matches the authentication policy",
                "Review RADIUS live logs for detailed failure reason",
            ]
            evidence = [f"Session: {session_id}", f"User: {username}", f"MAC: {endpoint_mac}"]

        elif "vlan" in query_lower or "assignment" in query_lower:
            root_cause = "Incorrect authorization profile assignment"
            fixes = [
                "Check policy rule conditions match the endpoint attributes",
                "Verify the authorization profile has the correct VLAN configured",
                "Ensure the policy set priority is correct",
                "Check if a higher-priority deny rule is matching first",
            ]

        elif "coa" in query_lower or "reauthentication" in query_lower:
            root_cause = "CoA/Reauthentication issue"
            fixes = [
                "Verify the NAD supports CoA on the configured port",
                "Check shared secret matches between NeuraNAC and the NAD",
                "Ensure the session is still active on the NAD",
                "Review NAD CoA configuration (RFC 5176 support)",
            ]

        elif "shadow" in query_lower and "ai" in query_lower:
            root_cause = "Shadow AI service detected"
            fixes = [
                "Review the AI data flow policy for this endpoint",
                "Check if the AI service needs to be added to the approved list",
                "Verify the user's group has AI service access permissions",
                "Consider creating a specific SGT for AI-using endpoints",
            ]

        elif "slow" in query_lower or "latency" in query_lower:
            root_cause = "Performance degradation"
            fixes = [
                "Check RADIUS server CPU and memory utilization",
                "Review database query performance (slow query log)",
                "Verify Redis cache hit rates",
                "Check network latency between NeuraNAC and identity sources",
                "Review policy evaluation time in session logs",
            ]

        else:
            root_cause = "General troubleshooting"
            fixes = [
                "Check RADIUS live logs for the affected session",
                "Verify network device configuration",
                "Review recent policy changes in audit log",
                "Check system health dashboard for service status",
            ]

        return {
            "root_cause": root_cause,
            "explanation": f"Analysis based on: {query}",
            "recommended_fixes": fixes,
            "evidence": evidence or [f"Query: {query}"],
        }
