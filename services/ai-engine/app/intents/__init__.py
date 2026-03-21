"""Intent definitions package for the AI Action Router.

Splits the monolithic INTENTS list into domain-specific modules for
maintainability. Each module exports a list of intent dicts.
"""
from app.intents.dashboard import DASHBOARD_INTENTS
from app.intents.policies import POLICY_INTENTS
from app.intents.network import NETWORK_INTENTS
from app.intents.sessions import SESSION_INTENTS
from app.intents.security import SECURITY_INTENTS
from app.intents.ai_intents import AI_INTENTS
from app.intents.infrastructure import INFRA_INTENTS
from app.intents.navigation import NAVIGATION_INTENTS
from app.intents.product_knowledge import PRODUCT_KNOWLEDGE_INTENTS

ALL_INTENTS = (
    PRODUCT_KNOWLEDGE_INTENTS
    + DASHBOARD_INTENTS
    + POLICY_INTENTS
    + NETWORK_INTENTS
    + SESSION_INTENTS
    + SECURITY_INTENTS
    + AI_INTENTS
    + INFRA_INTENTS
)

__all__ = ["ALL_INTENTS", "NAVIGATION_INTENTS"]
