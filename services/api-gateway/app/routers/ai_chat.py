"""AI Chat Router — proxies natural language requests to AI Engine Action Router."""
import os
from fastapi import APIRouter, Request, Depends
import httpx
import structlog

from app.middleware.auth import require_permission

logger = structlog.get_logger()

router = APIRouter()

AI_ENGINE_URL = os.getenv("AI_ENGINE_URL", "http://localhost:8081")
AI_ENGINE_API_KEY = os.getenv("AI_ENGINE_API_KEY", "neuranac_ai_dev_key_change_in_production")
AI_HEADERS = {"X-API-Key": AI_ENGINE_API_KEY, "Content-Type": "application/json"}


@router.post("/chat", dependencies=[Depends(require_permission("ai:read"))])
async def ai_chat(request: Request):
    """Forward a natural language message to the AI Action Router."""
    body = await request.json()
    message = body.get("message", "")
    context = body.get("context", {})
    # Pass the user's auth token so AI engine can call back to API gateway
    token = request.headers.get("Authorization", "").replace("Bearer ", "")

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{AI_ENGINE_URL}/api/v1/ai/chat",
                json={"message": message, "context": context, "token": token},
                headers=AI_HEADERS,
            )
            return resp.json()
    except httpx.ConnectError:
        logger.warning("AI Engine unavailable, returning fallback")
        return {
            "type": "error",
            "intent": "unavailable",
            "message": "AI Engine is currently unavailable. Please try again later or switch to Classic mode.",
        }
    except Exception as e:
        logger.error("AI chat proxy error", error=str(e))
        return {"type": "error", "intent": "error", "message": f"AI request failed: {str(e)}"}


@router.get("/capabilities")
async def ai_capabilities():
    """Proxy AI capabilities listing from AI Engine."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{AI_ENGINE_URL}/api/v1/ai/capabilities", headers=AI_HEADERS)
            return resp.json()
    except Exception:
        return {"modules": [], "action_intents": [], "navigation_intents": [], "total_intents": 0}


@router.get("/suggestions")
async def ai_suggestions(route: str = "/"):
    """Return context-aware suggestion chips based on current route."""
    suggestions_map = {
        "/": [
            {"label": "Show system status", "prompt": "Show system status"},
            {"label": "Active sessions", "prompt": "How many active sessions?"},
            {"label": "Recent audit log", "prompt": "Show audit log"},
            {"label": "Shadow AI detections", "prompt": "Show shadow AI detections"},
        ],
        "/policies": [
            {"label": "List all policies", "prompt": "List all policies"},
            {"label": "Create new policy", "prompt": "Create a new policy named Corporate Access"},
            {"label": "Translate policy", "prompt": "Create a rule to allow all employees on VLAN 100"},
            {"label": "Check policy drift", "prompt": "Analyze policy drift"},
        ],
        "/network-devices": [
            {"label": "List devices", "prompt": "List all network devices"},
            {"label": "Add a switch", "prompt": "Add a Cisco switch at 10.0.0.1"},
            {"label": "Discover devices", "prompt": "Discover devices on 10.0.0.0/24"},
        ],
        "/endpoints": [
            {"label": "List endpoints", "prompt": "List all endpoints"},
            {"label": "Profile endpoint", "prompt": "Profile the last connected endpoint"},
            {"label": "Check anomalies", "prompt": "Check for endpoint anomalies"},
        ],
        "/sessions": [
            {"label": "Active sessions", "prompt": "Show all active sessions"},
            {"label": "Failed auths", "prompt": "Show failed authentication sessions"},
            {"label": "Session count", "prompt": "How many active sessions?"},
        ],
        "/ai/agents": [
            {"label": "List AI agents", "prompt": "List all AI agents"},
            {"label": "Risk scores", "prompt": "Compute risk score for current sessions"},
        ],
        "/ai/shadow": [
            {"label": "Shadow detections", "prompt": "Show shadow AI detections"},
            {"label": "AI services", "prompt": "List known AI services"},
            {"label": "Block OpenAI", "prompt": "Block all traffic to OpenAI"},
        ],
        "/ai/data-flow": [
            {"label": "Data flow policies", "prompt": "List AI data flow policies"},
            {"label": "Create policy", "prompt": "Create an AI data flow policy to monitor Copilot"},
        ],
        "/legacy-nac": [
            {"label": "legacy connections", "prompt": "List legacy connections"},
            {"label": "NeuraNAC summary", "prompt": "Show NeuraNAC integration summary"},
        ],
        "/diagnostics": [
            {"label": "System status", "prompt": "Show system status"},
            {"label": "RADIUS log", "prompt": "Show RADIUS live log"},
            {"label": "Troubleshoot", "prompt": "Why are users failing authentication?"},
        ],
        "/certificates": [
            {"label": "List certificates", "prompt": "List all certificates"},
            {"label": "List CAs", "prompt": "Show certificate authorities"},
        ],
        "/segmentation": [
            {"label": "List SGTs", "prompt": "List security group tags"},
            {"label": "Create SGT", "prompt": "Create a new SGT named IoT-Devices with tag 100"},
        ],
        "/topology": [
            {"label": "Show topology", "prompt": "Show network topology"},
            {"label": "Health matrix", "prompt": "Show service health matrix"},
            {"label": "Data flow", "prompt": "Trace RADIUS authentication flow"},
            {"label": "NeuraNAC topology", "prompt": "Show NeuraNAC integration topology"},
        ],
        "/nodes": [
            {"label": "List nodes", "prompt": "List twin nodes"},
            {"label": "Sync status", "prompt": "Check node sync status"},
        ],
        "/audit": [
            {"label": "Audit log", "prompt": "Show audit log"},
            {"label": "Auth report", "prompt": "Show authentication report"},
        ],
    }
    # Return matching suggestions or default
    chips = suggestions_map.get(route, suggestions_map["/"])
    return {"route": route, "suggestions": chips}


# ─── Phase 4 proxy routes to AI Engine ────────────────────────────────────────

async def _proxy_post(path: str, request: Request):
    """Generic POST proxy to AI Engine."""
    body = await request.json()
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(f"{AI_ENGINE_URL}{path}", json=body, headers=AI_HEADERS)
            return resp.json()
    except httpx.ConnectError:
        return {"error": "AI Engine unavailable"}
    except Exception as e:
        return {"error": str(e)}


async def _proxy_get(path: str, request: Request):
    """Generic GET proxy to AI Engine."""
    qs = str(request.url.query)
    url = f"{AI_ENGINE_URL}{path}"
    if qs:
        url += f"?{qs}"
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, headers=AI_HEADERS)
            return resp.json()
    except httpx.ConnectError:
        return {"error": "AI Engine unavailable"}
    except Exception as e:
        return {"error": str(e)}


# RAG Troubleshooter
@router.post("/rag/troubleshoot")
async def proxy_rag_troubleshoot(request: Request):
    return await _proxy_post("/api/v1/rag/troubleshoot", request)


# Training Pipeline
@router.post("/training/sample")
async def proxy_training_sample(request: Request):
    return await _proxy_post("/api/v1/training/sample", request)


@router.get("/training/stats")
async def proxy_training_stats(request: Request):
    return await _proxy_get("/api/v1/training/stats", request)


@router.post("/training/train", dependencies=[Depends(require_permission("ai:manage"))])
async def proxy_training_train(request: Request):
    return await _proxy_post("/api/v1/training/train", request)


# NL-to-SQL
@router.post("/nl-sql/query", dependencies=[Depends(require_permission("ai:read"))])
async def proxy_nl_sql(request: Request):
    return await _proxy_post("/api/v1/nl-sql/query", request)


# Adaptive Risk
@router.get("/risk/thresholds")
async def proxy_risk_thresholds(request: Request):
    return await _proxy_get("/api/v1/risk/thresholds", request)


@router.post("/risk/feedback")
async def proxy_risk_feedback(request: Request):
    return await _proxy_post("/api/v1/risk/feedback", request)


@router.get("/risk/adaptive-stats")
async def proxy_risk_stats(request: Request):
    return await _proxy_get("/api/v1/risk/adaptive-stats", request)


# TLS Fingerprinting
@router.post("/tls/analyze-ja3")
async def proxy_tls_ja3(request: Request):
    return await _proxy_post("/api/v1/tls/analyze-ja3", request)


@router.post("/tls/analyze-ja4")
async def proxy_tls_ja4(request: Request):
    return await _proxy_post("/api/v1/tls/analyze-ja4", request)


@router.post("/tls/compute-ja3")
async def proxy_tls_compute(request: Request):
    return await _proxy_post("/api/v1/tls/compute-ja3", request)


@router.post("/tls/custom-signature")
async def proxy_tls_custom(request: Request):
    return await _proxy_post("/api/v1/tls/custom-signature", request)


@router.get("/tls/detections")
async def proxy_tls_detections(request: Request):
    return await _proxy_get("/api/v1/tls/detections", request)


@router.get("/tls/stats")
async def proxy_tls_stats(request: Request):
    return await _proxy_get("/api/v1/tls/stats", request)


# Capacity Planning
@router.post("/capacity/record")
async def proxy_cap_record(request: Request):
    return await _proxy_post("/api/v1/capacity/record", request)


@router.get("/capacity/forecast")
async def proxy_cap_forecast(request: Request):
    return await _proxy_get("/api/v1/capacity/forecast", request)


@router.get("/capacity/metrics")
async def proxy_cap_metrics(request: Request):
    return await _proxy_get("/api/v1/capacity/metrics", request)


# Playbooks
@router.get("/playbooks")
async def proxy_pb_list(request: Request):
    return await _proxy_get("/api/v1/playbooks", request)


@router.get("/playbooks/executions/list")
async def proxy_pb_executions(request: Request):
    return await _proxy_get("/api/v1/playbooks/executions/list", request)


@router.get("/playbooks/stats/summary")
async def proxy_pb_stats(request: Request):
    return await _proxy_get("/api/v1/playbooks/stats/summary", request)


@router.get("/playbooks/{playbook_id}")
async def proxy_pb_get(playbook_id: str, request: Request):
    return await _proxy_get(f"/api/v1/playbooks/{playbook_id}", request)


@router.post("/playbooks", dependencies=[Depends(require_permission("ai:manage"))])
async def proxy_pb_create(request: Request):
    return await _proxy_post("/api/v1/playbooks", request)


@router.post("/playbooks/{playbook_id}/execute", dependencies=[Depends(require_permission("ai:manage"))])
async def proxy_pb_execute(playbook_id: str, request: Request):
    return await _proxy_post(f"/api/v1/playbooks/{playbook_id}/execute", request)


# Model Registry
@router.post("/models/register", dependencies=[Depends(require_permission("ai:manage"))])
async def proxy_model_register(request: Request):
    return await _proxy_post("/api/v1/models/register", request)


@router.get("/models")
async def proxy_model_list(request: Request):
    return await _proxy_get("/api/v1/models", request)


@router.post("/models/experiments", dependencies=[Depends(require_permission("ai:manage"))])
async def proxy_model_exp_create(request: Request):
    return await _proxy_post("/api/v1/models/experiments", request)


@router.get("/models/experiments")
async def proxy_model_exp_list(request: Request):
    return await _proxy_get("/api/v1/models/experiments", request)


@router.post("/models/experiments/{experiment_id}/stop", dependencies=[Depends(require_permission("ai:manage"))])
async def proxy_model_exp_stop(experiment_id: str, request: Request):
    return await _proxy_post(f"/api/v1/models/experiments/{experiment_id}/stop", request)


@router.get("/models/stats")
async def proxy_model_stats(request: Request):
    return await _proxy_get("/api/v1/models/stats", request)
