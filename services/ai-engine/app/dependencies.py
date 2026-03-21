"""Dependency injection container for AI Engine modules.

Replaces module-level globals with a singleton container that can be
injected via FastAPI Depends() for testability and clean lifecycle.
"""
from __future__ import annotations

import structlog
from fastapi import Request

from app.profiler import EndpointProfiler
from app.risk import RiskScorer
from app.shadow import ShadowAIDetector
from app.nlp_policy import NLPolicyAssistant
from app.troubleshooter import AITroubleshooter
from app.anomaly import AnomalyDetector, PolicyDriftDetector
from app.action_router import ActionRouter
from app.rag_troubleshooter import RAGTroubleshooter
from app.training_pipeline import TrainingPipeline
from app.nl_to_sql import NLToSQL
from app.adaptive_risk import AdaptiveRiskEngine
from app.tls_fingerprint import TLSFingerprinter
from app.capacity_planner import CapacityPlanner
from app.playbooks import PlaybookEngine
from app.model_registry import ModelRegistry

logger = structlog.get_logger()


class AIContainer:
    """Holds all AI module instances with explicit lifecycle."""

    def __init__(self) -> None:
        self.profiler: EndpointProfiler | None = None
        self.risk_scorer: RiskScorer | None = None
        self.shadow_detector: ShadowAIDetector | None = None
        self.nlp_assistant: NLPolicyAssistant | None = None
        self.troubleshooter: AITroubleshooter | None = None
        self.anomaly_detector: AnomalyDetector | None = None
        self.drift_detector: PolicyDriftDetector | None = None
        self.action_router: ActionRouter | None = None
        self.rag_troubleshooter: RAGTroubleshooter | None = None
        self.training_pipeline: TrainingPipeline | None = None
        self.nl_to_sql: NLToSQL | None = None
        self.adaptive_risk: AdaptiveRiskEngine | None = None
        self.tls_fingerprinter: TLSFingerprinter | None = None
        self.capacity_planner: CapacityPlanner | None = None
        self.playbook_engine: PlaybookEngine | None = None
        self.model_registry: ModelRegistry | None = None
        self._initialized = False

    async def startup(self) -> None:
        """Initialize all AI modules."""
        logger.info("Initializing AI container")
        self.profiler = EndpointProfiler()
        await self.profiler.load_model()
        self.risk_scorer = RiskScorer()
        self.shadow_detector = ShadowAIDetector()
        await self.shadow_detector.load_signatures()
        self.nlp_assistant = NLPolicyAssistant()
        self.troubleshooter = AITroubleshooter()
        self.anomaly_detector = AnomalyDetector()
        self.drift_detector = PolicyDriftDetector()
        self.action_router = ActionRouter()
        await self.action_router.check_llm()
        # Phase 4 modules
        self.rag_troubleshooter = RAGTroubleshooter()
        await self.rag_troubleshooter.initialize()
        self.training_pipeline = TrainingPipeline()
        self.nl_to_sql = NLToSQL()
        await self.nl_to_sql.initialize()
        self.adaptive_risk = AdaptiveRiskEngine()
        await self.adaptive_risk.load_thresholds()
        self.tls_fingerprinter = TLSFingerprinter()
        await self.tls_fingerprinter.load_state()
        self.capacity_planner = CapacityPlanner()
        self.playbook_engine = PlaybookEngine()
        self.model_registry = ModelRegistry()
        self._initialized = True
        logger.info("AI container ready (16 modules loaded)")

    async def shutdown(self) -> None:
        """Cleanup resources."""
        self._initialized = False
        logger.info("AI container stopped")

    @property
    def is_ready(self) -> bool:
        return self._initialized


# Singleton instance — set during app lifespan
_container: AIContainer | None = None


def get_container() -> AIContainer:
    """Return the global AI container (call from lifespan only)."""
    global _container
    if _container is None:
        _container = AIContainer()
    return _container


def set_container(c: AIContainer) -> None:
    """Override the container (useful for testing)."""
    global _container
    _container = c


# ── FastAPI Depends() helpers ────────────────────────────────────────────────

def _resolve(request: Request) -> AIContainer:
    c = get_container()
    if not c.is_ready:
        from fastapi import HTTPException
        raise HTTPException(503, "AI Engine is still initializing")
    return c


def get_profiler(request: Request) -> EndpointProfiler:
    return _resolve(request).profiler


def get_risk_scorer(request: Request) -> RiskScorer:
    return _resolve(request).risk_scorer


def get_shadow_detector(request: Request) -> ShadowAIDetector:
    return _resolve(request).shadow_detector


def get_nlp_assistant(request: Request) -> NLPolicyAssistant:
    return _resolve(request).nlp_assistant


def get_troubleshooter(request: Request) -> AITroubleshooter:
    return _resolve(request).troubleshooter


def get_anomaly_detector(request: Request) -> AnomalyDetector:
    return _resolve(request).anomaly_detector


def get_drift_detector(request: Request) -> PolicyDriftDetector:
    return _resolve(request).drift_detector


def get_action_router(request: Request) -> ActionRouter:
    return _resolve(request).action_router


def get_rag_troubleshooter(request: Request) -> RAGTroubleshooter:
    return _resolve(request).rag_troubleshooter


def get_training_pipeline(request: Request) -> TrainingPipeline:
    return _resolve(request).training_pipeline


def get_nl_to_sql(request: Request) -> NLToSQL:
    return _resolve(request).nl_to_sql


def get_adaptive_risk(request: Request) -> AdaptiveRiskEngine:
    return _resolve(request).adaptive_risk


def get_tls_fingerprinter(request: Request) -> TLSFingerprinter:
    return _resolve(request).tls_fingerprinter


def get_capacity_planner(request: Request) -> CapacityPlanner:
    return _resolve(request).capacity_planner


def get_playbook_engine(request: Request) -> PlaybookEngine:
    return _resolve(request).playbook_engine


def get_model_registry(request: Request) -> ModelRegistry:
    return _resolve(request).model_registry
