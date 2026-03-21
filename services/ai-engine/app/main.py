"""NeuraNAC AI Engine - ML profiling, risk scoring, shadow AI detection, NLP policy assistant"""
import os
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from fastapi import Depends

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
from app.schemas import (
    ProfileRequest, RiskScoreRequest, ShadowAIDetectRequest, NLPTranslateRequest,
    TroubleshootRequest, AnomalyRequest, DriftRecordRequest, AIChatRequest,
    RAGTroubleshootRequest, TrainingSampleRequest, NLSQLRequest, RiskFeedbackRequest,
    TLSJA3Request, TLSJA4Request, ComputeJA3Request, CustomTLSSigRequest,
    CapacityRecordRequest, PlaybookCreateRequest, PlaybookExecuteRequest,
    ModelRegisterRequest, ExperimentCreateRequest,
)
from app.dependencies import (
    AIContainer, get_container,
    get_profiler, get_risk_scorer, get_shadow_detector, get_nlp_assistant,
    get_troubleshooter, get_anomaly_detector, get_drift_detector, get_action_router,
    get_rag_troubleshooter, get_training_pipeline, get_nl_to_sql, get_adaptive_risk,
    get_tls_fingerprinter, get_capacity_planner, get_playbook_engine, get_model_registry,
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting NeuraNAC AI Engine")
    container = get_container()
    await container.startup()
    yield
    await container.shutdown()
    logger.info("AI Engine stopped")


AI_ENGINE_API_KEY = os.getenv("AI_ENGINE_API_KEY", "")
AI_ENGINE_API_KEY_PREVIOUS = os.getenv("AI_ENGINE_API_KEY_PREVIOUS", "")
AI_PUBLIC_PATHS = {"/health", "/docs", "/openapi.json", "/knowledge-status", "/llm-status"}

if not AI_ENGINE_API_KEY:
    logger.warning("AI_ENGINE_API_KEY not set — AI Engine API key auth disabled (dev only)")
elif "dev_key" in AI_ENGINE_API_KEY:
    logger.warning("AI_ENGINE_API_KEY contains dev placeholder — change for production")


def _valid_api_keys() -> set:
    """Return set of currently accepted API keys (current + previous for rotation)."""
    keys = {AI_ENGINE_API_KEY}
    if AI_ENGINE_API_KEY_PREVIOUS:
        keys.add(AI_ENGINE_API_KEY_PREVIOUS)
    keys.discard("")
    return keys


class AIEngineAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in AI_PUBLIC_PATHS or request.method == "OPTIONS":
            return await call_next(request)
        api_key = request.headers.get("X-API-Key", "")
        if api_key not in _valid_api_keys():
            return JSONResponse(
                status_code=401,
                content={"error": "Invalid or missing API key", "status_code": 401},
            )
        if api_key == AI_ENGINE_API_KEY_PREVIOUS:
            logger.warning("Request used previous API key — rotate callers soon")
        return await call_next(request)


app = FastAPI(title="NeuraNAC AI Engine", version="1.0.0", lifespan=lifespan)
app.add_middleware(AIEngineAuthMiddleware)


@app.get("/health")
async def health():
    try:
        container = get_container()
        model_loaded = (
            container.profiler.model_loaded
            if container.is_ready and container.profiler
            else False
        )
        return {
            "status": "healthy",
            "service": "ai-engine",
            "model_loaded": model_loaded,
            "ready": container.is_ready,
        }
    except Exception as exc:
        return JSONResponse(
            status_code=503,
            content={
                "status": "degraded",
                "service": "ai-engine",
                "model_loaded": False,
                "ready": False,
                "error": str(exc),
            },
        )


@app.get("/knowledge-status")
async def knowledge_status():
    """Report loaded knowledge base status — verifiable by any deployment."""
    from app.intents import ALL_INTENTS
    from app.intents.nac_knowledge import NAC_KNOWLEDGE_ARTICLES
    from app.intents.product_knowledge import PRODUCT_KNOWLEDGE_INTENTS

    knowledge_intents = [i for i in ALL_INTENTS if "knowledge" in i]
    nac_ids = [a["id"] for a in NAC_KNOWLEDGE_ARTICLES]
    product_ids = [i["intent"] for i in PRODUCT_KNOWLEDGE_INTENTS]

    return {
        "status": "loaded",
        "total_intents": len(ALL_INTENTS),
        "knowledge_intents": len(knowledge_intents),
        "nac_knowledge_articles": len(NAC_KNOWLEDGE_ARTICLES),
        "nac_article_ids": nac_ids,
        "product_knowledge_intents": len(PRODUCT_KNOWLEDGE_INTENTS),
        "product_intent_ids": product_ids,
    }


@app.get("/llm-status")
async def llm_status():
    """Report LLM configuration and availability — verifiable by any deployment."""
    import httpx
    llm_api_url = os.getenv("AI_LLM_API_URL", "http://localhost:11434/api/generate")
    llm_model = os.getenv("AI_LLM_MODEL", "llama3.1:8b")
    ollama_base = llm_api_url.replace("/api/generate", "")

    status = {
        "configured_model": llm_model,
        "configured_url": llm_api_url,
        "ollama_reachable": False,
        "model_available": False,
        "available_models": [],
        "llm_active_in_router": False,
    }

    # Check Ollama connectivity
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{ollama_base}/api/tags")
            if resp.status_code == 200:
                status["ollama_reachable"] = True
                models_data = resp.json().get("models", [])
                status["available_models"] = [m.get("name", "") for m in models_data]
                status["model_available"] = any(
                    llm_model in m.get("name", "") for m in models_data
                )
    except Exception:
        pass

    # Check if ActionRouter has LLM enabled
    try:
        container = get_container()
        if container.is_ready and container.action_router:
            status["llm_active_in_router"] = container.action_router._llm_available
    except Exception:
        pass

    overall = "active" if status["llm_active_in_router"] else (
        "reachable_not_active" if status["ollama_reachable"] else "not_running"
    )
    status["status"] = overall

    return status


@app.post("/api/v1/profile")
async def profile_endpoint(request: ProfileRequest, svc: EndpointProfiler = Depends(get_profiler)):
    return await svc.predict(request.model_dump())


@app.post("/api/v1/risk-score")
async def compute_risk(request: RiskScoreRequest, svc: RiskScorer = Depends(get_risk_scorer)):
    return await svc.compute(request.model_dump())


@app.post("/api/v1/shadow-ai/detect")
async def detect_shadow_ai(request: ShadowAIDetectRequest, svc: ShadowAIDetector = Depends(get_shadow_detector)):
    return await svc.detect(request.model_dump())


@app.post("/api/v1/nlp/translate")
async def translate_policy(request: NLPTranslateRequest, svc: NLPolicyAssistant = Depends(get_nlp_assistant)):
    return await svc.translate(request.natural_language, request.context or "")


@app.post("/api/v1/troubleshoot")
async def troubleshoot(request: TroubleshootRequest, svc: AITroubleshooter = Depends(get_troubleshooter)):
    return await svc.analyze(request.model_dump())


@app.post("/api/v1/anomaly/analyze")
async def analyze_anomaly(request: AnomalyRequest, svc: AnomalyDetector = Depends(get_anomaly_detector)):
    return await svc.analyze(request.model_dump())


@app.post("/api/v1/drift/record")
async def record_drift_outcome(request: DriftRecordRequest, svc: PolicyDriftDetector = Depends(get_drift_detector)):
    await svc.record_outcome(
        policy_id=request.policy_id,
        expected_action=request.expected_action,
        actual_action=request.actual_action,
        matched=request.matched,
        evaluation_time_us=request.evaluation_time_us,
    )
    return {"status": "recorded"}


@app.get("/api/v1/drift/analyze")
async def analyze_drift(policy_id: str = None, svc: PolicyDriftDetector = Depends(get_drift_detector)):
    return await svc.analyze_drift(policy_id)


@app.post("/api/v1/ai/chat")
async def ai_chat(request: AIChatRequest, svc: ActionRouter = Depends(get_action_router)):
    """AI Action Router — natural language to API action."""
    return await svc.route(request.message, context=request.context, token=request.token)


@app.get("/api/v1/ai/capabilities")
async def ai_capabilities(container: AIContainer = Depends(lambda request: get_container())):
    """List all AI capabilities and available intents."""
    from app.action_router import INTENTS, NAVIGATION_INTENTS
    return {
        "modules": [
            {"name": "EndpointProfiler", "status": "active", "model_loaded": container.profiler.model_loaded if container.profiler else False},
            {"name": "RiskScorer", "status": "active"},
            {"name": "ShadowAIDetector", "status": "active"},
            {"name": "NLPolicyAssistant", "status": "active"},
            {"name": "AITroubleshooter", "status": "active"},
            {"name": "AnomalyDetector", "status": "active"},
            {"name": "PolicyDriftDetector", "status": "active"},
            {"name": "ActionRouter", "status": "active", "llm_available": container.action_router._llm_available if container.action_router else False},
            {"name": "RAGTroubleshooter", "status": "active"},
            {"name": "TrainingPipeline", "status": "active"},
            {"name": "NLToSQL", "status": "active"},
            {"name": "AdaptiveRiskEngine", "status": "active"},
            {"name": "TLSFingerprinter", "status": "active"},
            {"name": "CapacityPlanner", "status": "active"},
            {"name": "PlaybookEngine", "status": "active"},
            {"name": "ModelRegistry", "status": "active"},
        ],
        "action_intents": [{"intent": i["intent"], "description": i["description"]} for i in INTENTS],
        "navigation_intents": list(NAVIGATION_INTENTS.keys()),
        "total_intents": len(INTENTS) + len(NAVIGATION_INTENTS),
    }


# ─── Phase 4.1: RAG Troubleshooter ───────────────────────────────────────────

@app.post("/api/v1/rag/troubleshoot")
async def rag_troubleshoot(request: RAGTroubleshootRequest, svc: RAGTroubleshooter = Depends(get_rag_troubleshooter)):
    return await svc.troubleshoot(request.query, request.context)


# ─── Phase 4.2: Training Pipeline ────────────────────────────────────────────

@app.post("/api/v1/training/sample")
async def add_training_sample(request: TrainingSampleRequest, svc: TrainingPipeline = Depends(get_training_pipeline)):
    return await svc.add_sample(request.model_dump())


@app.get("/api/v1/training/stats")
async def training_stats(svc: TrainingPipeline = Depends(get_training_pipeline)):
    return await svc.get_stats()


@app.post("/api/v1/training/train")
async def train_model(svc: TrainingPipeline = Depends(get_training_pipeline)):
    return await svc.train_and_export()


# ─── Phase 4.3: NL-to-SQL ────────────────────────────────────────────────────

@app.post("/api/v1/nl-sql/query")
async def nl_sql_query(request: NLSQLRequest, svc: NLToSQL = Depends(get_nl_to_sql)):
    return await svc.translate_and_execute(request.question)


# ─── Phase 4.4: Adaptive Risk ─────────────────────────────────────────────────

@app.post("/api/v1/risk/feedback")
async def risk_feedback(request: RiskFeedbackRequest, svc: AdaptiveRiskEngine = Depends(get_adaptive_risk)):
    return await svc.record_feedback(
        request.tenant_id, request.risk_score, request.decision, request.was_correct,
    )


@app.get("/api/v1/risk/thresholds")
async def risk_thresholds(tenant_id: str = "default", svc: AdaptiveRiskEngine = Depends(get_adaptive_risk)):
    return svc.get_thresholds(tenant_id)


@app.get("/api/v1/risk/adaptive-stats")
async def risk_adaptive_stats(tenant_id: str = "default", svc: AdaptiveRiskEngine = Depends(get_adaptive_risk)):
    return await svc.get_stats(tenant_id)


# ─── Phase 4.5: TLS Fingerprinting ────────────────────────────────────────────

@app.post("/api/v1/tls/analyze-ja3")
async def analyze_ja3(request: TLSJA3Request, svc: TLSFingerprinter = Depends(get_tls_fingerprinter)):
    return svc.analyze_ja3(
        request.ja3_hash, request.endpoint_mac or "", request.src_ip or "", request.dst_ip or "",
    )


@app.post("/api/v1/tls/analyze-ja4")
async def analyze_ja4(request: TLSJA4Request, svc: TLSFingerprinter = Depends(get_tls_fingerprinter)):
    return svc.analyze_ja4(request.ja4_hash, request.endpoint_mac or "")


@app.post("/api/v1/tls/compute-ja3")
async def compute_ja3(request: ComputeJA3Request, svc: TLSFingerprinter = Depends(get_tls_fingerprinter)):
    ja3 = svc.compute_ja3(
        request.tls_version, request.cipher_suites, request.extensions,
        request.elliptic_curves, request.ec_point_formats,
    )
    return {"ja3_hash": ja3}


@app.post("/api/v1/tls/custom-signature")
async def add_custom_tls_sig(request: CustomTLSSigRequest, svc: TLSFingerprinter = Depends(get_tls_fingerprinter)):
    return svc.add_custom_signature(
        request.ja3_hash, request.service, request.description, request.risk,
    )


@app.get("/api/v1/tls/detections")
async def tls_detections(limit: int = 50, svc: TLSFingerprinter = Depends(get_tls_fingerprinter)):
    return {"detections": svc.get_detections(limit)}


@app.get("/api/v1/tls/stats")
async def tls_stats(svc: TLSFingerprinter = Depends(get_tls_fingerprinter)):
    return svc.get_stats()


# ─── Phase 4.6: Capacity Planning ─────────────────────────────────────────────

@app.post("/api/v1/capacity/record")
async def record_capacity_metric(request: CapacityRecordRequest, svc: CapacityPlanner = Depends(get_capacity_planner)):
    await svc.record_metric(request.metric, request.value, request.timestamp)
    return {"status": "recorded"}


@app.get("/api/v1/capacity/forecast")
async def capacity_forecast(metric: str = "", horizon_hours: int = 24, svc: CapacityPlanner = Depends(get_capacity_planner)):
    if metric:
        return await svc.forecast(metric, horizon_hours)
    return await svc.get_all_forecasts(horizon_hours)


@app.get("/api/v1/capacity/metrics")
async def capacity_metrics(svc: CapacityPlanner = Depends(get_capacity_planner)):
    return {"metrics": await svc.get_metrics_list()}


# ─── Phase 4.7: Playbooks ─────────────────────────────────────────────────────

@app.get("/api/v1/playbooks")
async def list_playbooks(svc: PlaybookEngine = Depends(get_playbook_engine)):
    return {"playbooks": svc.list_playbooks()}


@app.get("/api/v1/playbooks/{playbook_id}")
async def get_playbook(playbook_id: str, svc: PlaybookEngine = Depends(get_playbook_engine)):
    pb = svc.get_playbook(playbook_id)
    if pb:
        return pb
    return {"error": "not found"}


@app.post("/api/v1/playbooks")
async def create_playbook(request: PlaybookCreateRequest, svc: PlaybookEngine = Depends(get_playbook_engine)):
    return svc.create_playbook(
        request.id, request.name, request.description,
        request.trigger, request.severity, request.steps,
    )


@app.post("/api/v1/playbooks/{playbook_id}/execute")
async def execute_playbook(playbook_id: str, request: PlaybookExecuteRequest, svc: PlaybookEngine = Depends(get_playbook_engine)):
    return await svc.execute(playbook_id, request.context)


@app.get("/api/v1/playbooks/executions/list")
async def playbook_executions(limit: int = 50, svc: PlaybookEngine = Depends(get_playbook_engine)):
    return {"executions": svc.get_executions(limit)}


@app.get("/api/v1/playbooks/stats/summary")
async def playbook_stats(svc: PlaybookEngine = Depends(get_playbook_engine)):
    return svc.get_stats()


# ─── Phase 4.8: Model Registry ────────────────────────────────────────────────

@app.post("/api/v1/models/register")
async def register_model(request: ModelRegisterRequest, svc: ModelRegistry = Depends(get_model_registry)):
    return svc.register_model(
        request.name, request.version, request.model_type,
        request.endpoint, request.weight, request.metadata,
    )


@app.get("/api/v1/models")
async def list_models(model_type: str = None, svc: ModelRegistry = Depends(get_model_registry)):
    return {"models": svc.list_models(model_type)}


@app.post("/api/v1/models/experiments")
async def create_experiment(request: ExperimentCreateRequest, svc: ModelRegistry = Depends(get_model_registry)):
    return svc.create_experiment(
        request.name, request.model_a_id, request.model_b_id, request.traffic_split,
    )


@app.get("/api/v1/models/experiments")
async def list_experiments(svc: ModelRegistry = Depends(get_model_registry)):
    return {"experiments": svc.list_experiments()}


@app.post("/api/v1/models/experiments/{experiment_id}/stop")
async def stop_experiment(experiment_id: str, svc: ModelRegistry = Depends(get_model_registry)):
    return svc.stop_experiment(experiment_id)


@app.get("/api/v1/models/stats")
async def model_stats(svc: ModelRegistry = Depends(get_model_registry)):
    return svc.get_stats()
