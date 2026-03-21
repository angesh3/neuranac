"""
Automated Incident Response Playbooks — predefined and custom playbooks
that execute a sequence of actions in response to security incidents.
"""
import time
import uuid
import structlog
from typing import Dict, Any, List, Optional
from enum import Enum

logger = structlog.get_logger()


class PlaybookStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ─── Built-in Playbooks ──────────────────────────────────────────────────────

BUILTIN_PLAYBOOKS: Dict[str, Dict[str, Any]] = {
    "pb-auth-failure-lockout": {
        "name": "Auth Failure Lockout",
        "description": "Lock out endpoint after repeated authentication failures",
        "trigger": "auth_failure_count > 5 within 10 minutes",
        "severity": "high",
        "steps": [
            {"action": "log_incident", "params": {"level": "warning", "msg": "Repeated auth failures detected"}},
            {"action": "lookup_endpoint", "params": {"by": "mac_address"}},
            {"action": "quarantine_endpoint", "params": {"vlan": "quarantine", "duration_minutes": 30}},
            {"action": "send_coa", "params": {"action": "reauthenticate"}},
            {"action": "notify_admin", "params": {"channel": "email", "template": "auth_lockout"}},
            {"action": "create_ticket", "params": {"priority": "high", "category": "security"}},
        ],
    },
    "pb-shadow-ai-block": {
        "name": "Shadow AI Service Block",
        "description": "Block unauthorized AI service usage and notify security team",
        "trigger": "shadow_ai_detection with risk=high",
        "severity": "high",
        "steps": [
            {"action": "log_incident", "params": {"level": "warning", "msg": "Unauthorized AI service detected"}},
            {"action": "lookup_endpoint", "params": {"by": "mac_address"}},
            {"action": "block_service", "params": {"method": "acl", "direction": "outbound"}},
            {"action": "notify_admin", "params": {"channel": "slack", "template": "shadow_ai_alert"}},
            {"action": "create_ticket", "params": {"priority": "medium", "category": "compliance"}},
        ],
    },
    "pb-anomaly-investigate": {
        "name": "Anomaly Investigation",
        "description": "Investigate and respond to behavioral anomaly detection",
        "trigger": "anomaly_score > 50",
        "severity": "medium",
        "steps": [
            {"action": "log_incident", "params": {"level": "info", "msg": "Behavioral anomaly detected"}},
            {"action": "lookup_endpoint", "params": {"by": "mac_address"}},
            {"action": "collect_context", "params": {"lookback_minutes": 60}},
            {"action": "run_profiling", "params": {}},
            {"action": "compute_risk", "params": {}},
            {"action": "decide_action", "params": {"if_risk_high": "quarantine", "if_risk_medium": "monitor"}},
            {"action": "notify_admin", "params": {"channel": "email", "template": "anomaly_report"}},
        ],
    },
    "pb-cert-expiry-renew": {
        "name": "Certificate Expiry Auto-Renewal",
        "description": "Auto-renew expiring certificates and notify operators",
        "trigger": "certificate expires within 14 days",
        "severity": "medium",
        "steps": [
            {"action": "log_incident", "params": {"level": "info", "msg": "Certificate approaching expiry"}},
            {"action": "check_ca_status", "params": {}},
            {"action": "generate_csr", "params": {"key_size": 2048, "algorithm": "RSA"}},
            {"action": "submit_to_ca", "params": {"ca": "internal"}},
            {"action": "install_certificate", "params": {}},
            {"action": "notify_admin", "params": {"channel": "email", "template": "cert_renewed"}},
        ],
    },
    "pb-rogue-device": {
        "name": "Rogue Device Isolation",
        "description": "Isolate an unregistered or suspicious device",
        "trigger": "unknown endpoint with no MAB/802.1X profile",
        "severity": "high",
        "steps": [
            {"action": "log_incident", "params": {"level": "warning", "msg": "Rogue device detected"}},
            {"action": "lookup_endpoint", "params": {"by": "mac_address"}},
            {"action": "quarantine_endpoint", "params": {"vlan": "quarantine", "duration_minutes": 60}},
            {"action": "send_coa", "params": {"action": "reauthenticate"}},
            {"action": "run_profiling", "params": {}},
            {"action": "notify_admin", "params": {"channel": "slack", "template": "rogue_device"}},
            {"action": "create_ticket", "params": {"priority": "high", "category": "security"}},
        ],
    },
    "pb-high-risk-session": {
        "name": "High Risk Session Response",
        "description": "Respond to sessions with critical risk scores",
        "trigger": "risk_score >= 80",
        "severity": "critical",
        "steps": [
            {"action": "log_incident", "params": {"level": "error", "msg": "Critical risk session detected"}},
            {"action": "quarantine_endpoint", "params": {"vlan": "quarantine", "duration_minutes": 120}},
            {"action": "send_coa", "params": {"action": "disconnect"}},
            {"action": "collect_context", "params": {"lookback_minutes": 120}},
            {"action": "notify_admin", "params": {"channel": "pagerduty", "template": "critical_risk"}},
            {"action": "create_ticket", "params": {"priority": "critical", "category": "security"}},
        ],
    },
}


class PlaybookEngine:
    """Manages and executes incident response playbooks."""

    def __init__(self):
        self._custom_playbooks: Dict[str, Dict[str, Any]] = {}
        self._executions: List[Dict[str, Any]] = []

    def list_playbooks(self) -> List[Dict[str, Any]]:
        """List all available playbooks (built-in + custom)."""
        all_pb = {**BUILTIN_PLAYBOOKS, **self._custom_playbooks}
        return [
            {
                "id": pb_id,
                "name": pb["name"],
                "description": pb["description"],
                "trigger": pb["trigger"],
                "severity": pb["severity"],
                "step_count": len(pb["steps"]),
                "is_custom": pb_id in self._custom_playbooks,
            }
            for pb_id, pb in all_pb.items()
        ]

    def get_playbook(self, playbook_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific playbook by ID."""
        return self._custom_playbooks.get(playbook_id) or BUILTIN_PLAYBOOKS.get(playbook_id)

    def create_playbook(self, playbook_id: str, name: str, description: str,
                         trigger: str, severity: str, steps: List[Dict]) -> Dict[str, Any]:
        """Create a custom playbook."""
        self._custom_playbooks[playbook_id] = {
            "name": name,
            "description": description,
            "trigger": trigger,
            "severity": severity,
            "steps": steps,
        }
        return {"status": "created", "playbook_id": playbook_id}

    async def execute(self, playbook_id: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a playbook with the given incident context."""
        pb = self.get_playbook(playbook_id)
        if not pb:
            return {"status": "error", "message": f"Playbook {playbook_id} not found"}

        execution_id = str(uuid.uuid4())[:8]
        execution = {
            "execution_id": execution_id,
            "playbook_id": playbook_id,
            "playbook_name": pb["name"],
            "status": PlaybookStatus.RUNNING,
            "context": context,
            "started_at": time.time(),
            "steps_completed": [],
            "steps_failed": [],
        }

        logger.info("Playbook execution started",
                     playbook=playbook_id, execution=execution_id, context=context)

        for i, step in enumerate(pb["steps"]):
            step_result = await self._execute_step(step, context, execution_id)
            if step_result["success"]:
                execution["steps_completed"].append({
                    "step": i + 1,
                    "action": step["action"],
                    "result": step_result.get("detail", "ok"),
                })
            else:
                execution["steps_failed"].append({
                    "step": i + 1,
                    "action": step["action"],
                    "error": step_result.get("error", "unknown"),
                })
                # Continue execution despite step failure (best-effort)
                logger.warning("Playbook step failed",
                               playbook=playbook_id, step=i+1, action=step["action"])

        execution["status"] = (
            PlaybookStatus.COMPLETED if not execution["steps_failed"]
            else PlaybookStatus.FAILED
        )
        execution["completed_at"] = time.time()
        execution["duration_seconds"] = round(execution["completed_at"] - execution["started_at"], 2)

        self._executions.append(execution)
        logger.info("Playbook execution completed",
                     playbook=playbook_id, execution=execution_id,
                     status=execution["status"],
                     steps_ok=len(execution["steps_completed"]),
                     steps_fail=len(execution["steps_failed"]))

        return execution

    async def _execute_step(self, step: Dict, context: Dict, exec_id: str) -> Dict[str, Any]:
        """Execute a single playbook step. In production, this calls real APIs."""
        action = step["action"]
        params = step.get("params", {})

        # Simulated step execution (in production, each action type calls a real service)
        try:
            if action == "log_incident":
                logger.info(f"[Playbook {exec_id}] {params.get('msg', 'incident logged')}")
                return {"success": True, "detail": "logged"}
            elif action == "lookup_endpoint":
                mac = context.get("endpoint_mac", context.get("mac", "unknown"))
                return {"success": True, "detail": f"looked up {mac}"}
            elif action == "quarantine_endpoint":
                vlan = params.get("vlan", "quarantine")
                return {"success": True, "detail": f"quarantined to VLAN {vlan}"}
            elif action == "send_coa":
                return {"success": True, "detail": f"CoA sent: {params.get('action', 'reauthenticate')}"}
            elif action == "block_service":
                return {"success": True, "detail": f"service blocked via {params.get('method', 'acl')}"}
            elif action == "notify_admin":
                channel = params.get("channel", "email")
                return {"success": True, "detail": f"notified via {channel}"}
            elif action == "create_ticket":
                return {"success": True, "detail": f"ticket created (priority={params.get('priority', 'medium')})"}
            elif action == "collect_context":
                return {"success": True, "detail": "context collected"}
            elif action == "run_profiling":
                return {"success": True, "detail": "profiling completed"}
            elif action == "compute_risk":
                return {"success": True, "detail": "risk computed"}
            elif action == "decide_action":
                return {"success": True, "detail": "action decided: monitor"}
            elif action == "check_ca_status":
                return {"success": True, "detail": "CA status: online"}
            elif action == "generate_csr":
                return {"success": True, "detail": "CSR generated"}
            elif action == "submit_to_ca":
                return {"success": True, "detail": "submitted to CA"}
            elif action == "install_certificate":
                return {"success": True, "detail": "certificate installed"}
            else:
                return {"success": True, "detail": f"action '{action}' executed"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_executions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return recent playbook executions."""
        return self._executions[-limit:]

    def get_stats(self) -> Dict[str, Any]:
        """Return playbook engine statistics."""
        total = len(self._executions)
        completed = sum(1 for e in self._executions if e["status"] == PlaybookStatus.COMPLETED)
        failed = sum(1 for e in self._executions if e["status"] == PlaybookStatus.FAILED)
        return {
            "total_playbooks": len(BUILTIN_PLAYBOOKS) + len(self._custom_playbooks),
            "builtin_count": len(BUILTIN_PLAYBOOKS),
            "custom_count": len(self._custom_playbooks),
            "total_executions": total,
            "completed": completed,
            "failed": failed,
            "success_rate": round(completed / max(total, 1), 4),
        }
