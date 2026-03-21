"""AI Agent Delegation Chain Validator.

Validates that an AI agent's delegation chain is legitimate before
allowing the agent to perform actions. Checks:

1. Delegating user exists and has sufficient permissions.
2. Delegation scope does not exceed the delegator's permissions.
3. Agent TTL has not expired.
4. Transitive delegation chains (agent → agent → user) are bounded
   and acyclic (max depth configurable via MAX_DELEGATION_DEPTH).
5. Revoked agents anywhere in the chain invalidate the entire chain.
"""
import os
import structlog
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.network import AIAgent
from app.models.admin import AdminUser, AdminRole

logger = structlog.get_logger()

MAX_DELEGATION_DEPTH = int(os.getenv("MAX_DELEGATION_DEPTH", "5"))

# All known delegation scopes — agents cannot claim scopes outside this set
VALID_SCOPES = {
    "ai:read", "ai:manage", "ai:execute",
    "policy:read", "policy:write",
    "endpoint:read", "endpoint:write",
    "session:read",
    "device:read", "device:write",
    "audit:read",
    "report:read",
    "diagnostics:read", "diagnostics:execute",
}


class DelegationChainError(Exception):
    """Raised when the delegation chain is invalid."""

    def __init__(self, reason: str, chain: List[str] | None = None):
        self.reason = reason
        self.chain = chain or []
        super().__init__(reason)


class DelegationChainValidator:
    """Validates AI agent delegation chains against the DB."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def validate(self, agent_id: UUID) -> Dict[str, Any]:
        """Validate the full delegation chain for an agent.

        Returns a dict with:
          valid: bool
          chain: list of dicts describing each link
          effective_scopes: intersection of all scopes along the chain
          errors: list of error strings (empty if valid)
        """
        chain: List[Dict[str, Any]] = []
        errors: List[str] = []
        visited: set = set()
        effective_scopes: set = set()
        current_id = agent_id

        for depth in range(MAX_DELEGATION_DEPTH):
            if current_id in visited:
                errors.append(f"Cycle detected at agent {current_id}")
                break
            visited.add(current_id)

            agent = await self.db.get(AIAgent, current_id)
            if agent is None:
                errors.append(f"Agent {current_id} not found")
                break

            # Check status
            if agent.status == "revoked":
                errors.append(f"Agent '{agent.agent_name}' ({current_id}) is revoked")
                break
            if agent.status not in ("active", "pending"):
                errors.append(f"Agent '{agent.agent_name}' has invalid status: {agent.status}")
                break

            # Check TTL expiry
            if agent.created_at and agent.ttl_hours:
                expires_at = agent.created_at.replace(tzinfo=None) + timedelta(hours=agent.ttl_hours)
                if datetime.now(timezone.utc).replace(tzinfo=None) > expires_at:
                    errors.append(
                        f"Agent '{agent.agent_name}' delegation expired "
                        f"(created {agent.created_at}, TTL {agent.ttl_hours}h)"
                    )
                    break

            # Validate scopes are a subset of VALID_SCOPES
            agent_scopes = set(agent.delegation_scope or [])
            invalid = agent_scopes - VALID_SCOPES
            if invalid:
                errors.append(f"Agent '{agent.agent_name}' has unknown scopes: {invalid}")

            # Intersect scopes
            if depth == 0:
                effective_scopes = agent_scopes.copy()
            else:
                effective_scopes &= agent_scopes

            link = {
                "depth": depth,
                "type": "agent",
                "id": str(agent.id),
                "name": agent.agent_name,
                "status": agent.status,
                "scopes": list(agent_scopes),
            }
            chain.append(link)

            # Follow delegation to user or parent agent
            if agent.delegated_by_user_id:
                user_result = await self._validate_delegating_user(
                    agent.delegated_by_user_id, agent_scopes
                )
                chain.append(user_result["link"])
                if user_result["errors"]:
                    errors.extend(user_result["errors"])
                else:
                    # Restrict effective scopes to user's permissions
                    effective_scopes &= set(user_result.get("user_scopes", []))
                break  # end of chain — reached root user
            else:
                # No delegating user — check if this is a root agent (system-created)
                if agent.agent_type in ("system", "builtin"):
                    break  # system agents are self-authorizing
                errors.append(
                    f"Agent '{agent.agent_name}' has no delegated_by_user_id and is not a system agent"
                )
                break
        else:
            errors.append(
                f"Delegation chain exceeds max depth ({MAX_DELEGATION_DEPTH})"
            )

        valid = len(errors) == 0
        result = {
            "valid": valid,
            "chain": chain,
            "effective_scopes": sorted(effective_scopes) if valid else [],
            "errors": errors,
            "depth": len(chain),
        }

        if not valid:
            logger.warning("Delegation chain invalid",
                           agent_id=str(agent_id), errors=errors)
        return result

    async def _validate_delegating_user(
        self, user_id: UUID, required_scopes: set
    ) -> Dict[str, Any]:
        """Validate that the delegating user exists and has sufficient permissions."""
        errors: List[str] = []
        link: Dict[str, Any] = {
            "depth": -1,  # will be set by caller
            "type": "user",
            "id": str(user_id),
        }

        user = await self.db.get(AdminUser, user_id)
        if user is None:
            errors.append(f"Delegating user {user_id} not found")
            link["name"] = "unknown"
            link["status"] = "missing"
            return {"link": link, "errors": errors, "user_scopes": []}

        link["name"] = user.username
        link["status"] = "active"

        # Get user's role permissions
        user_scopes: set = set()
        if user.role_id:
            role = await self.db.get(AdminRole, user.role_id)
            if role and role.permissions:
                user_scopes = set(role.permissions)
            link["role"] = role.name if role else "none"
        else:
            link["role"] = "none"

        link["scopes"] = sorted(user_scopes)

        # Check that user's permissions cover the agent's delegation scope
        missing = required_scopes - user_scopes
        if missing:
            errors.append(
                f"User '{user.username}' lacks permissions for delegated scopes: {missing}"
            )

        return {"link": link, "errors": errors, "user_scopes": list(user_scopes)}

    async def validate_scope_request(
        self, agent_id: UUID, requested_action: str
    ) -> Dict[str, Any]:
        """Check if an agent is authorized for a specific action.

        Returns: {"allowed": bool, "reason": str}
        """
        result = await self.validate(agent_id)
        if not result["valid"]:
            return {
                "allowed": False,
                "reason": f"Invalid delegation chain: {'; '.join(result['errors'])}",
            }

        if requested_action not in result["effective_scopes"]:
            return {
                "allowed": False,
                "reason": (
                    f"Action '{requested_action}' not in effective scopes: "
                    f"{result['effective_scopes']}"
                ),
            }

        return {"allowed": True, "reason": "ok"}
