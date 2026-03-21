"""Webhooks & Plugin Interface router - event subscriptions, plugin registration"""
import json
import time
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

router = APIRouter()


# ─── Webhook Subscriptions ───────────────────────────────────────────────────

class WebhookCreate(BaseModel):
    name: str
    url: str
    events: List[str]  # e.g. ["auth.success", "auth.failure", "coa.sent", "posture.noncompliant"]
    headers: dict = {}
    secret: Optional[str] = None  # HMAC signing secret
    enabled: bool = True
    retry_count: int = 3
    timeout_seconds: int = 10


_webhooks: List[dict] = []


# ─── Plugin Interface ────────────────────────────────────────────────────────
# NOTE: Plugin routes MUST be registered before /{webhook_id} to avoid shadowing

class PluginRegister(BaseModel):
    name: str
    version: str
    description: str = ""
    hooks: List[str] = []  # e.g. ["pre_auth", "post_auth", "pre_policy", "post_policy"]
    config_url: Optional[str] = None  # Plugin's configuration endpoint
    callback_url: Optional[str] = None  # Plugin's event callback URL
    enabled: bool = True


_plugins: List[dict] = []


@router.get("/plugins")
async def list_plugins():
    return {"items": _plugins, "total": len(_plugins)}


@router.post("/plugins", status_code=201)
async def register_plugin(req: PluginRegister):
    plugin = req.model_dump()
    plugin["id"] = f"plugin-{len(_plugins)+1}"
    plugin["registered_at"] = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    plugin["status"] = "active"
    _plugins.append(plugin)
    return plugin


@router.delete("/plugins/{plugin_id}", status_code=204)
async def unregister_plugin(plugin_id: str):
    global _plugins
    _plugins = [p for p in _plugins if p.get("id") != plugin_id]


@router.post("/plugins/{plugin_id}/disable")
async def disable_plugin(plugin_id: str):
    plugin = next((p for p in _plugins if p.get("id") == plugin_id), None)
    if not plugin:
        raise HTTPException(404, "Plugin not found")
    plugin["status"] = "disabled"
    plugin["enabled"] = False
    return plugin


@router.post("/plugins/{plugin_id}/enable")
async def enable_plugin(plugin_id: str):
    plugin = next((p for p in _plugins if p.get("id") == plugin_id), None)
    if not plugin:
        raise HTTPException(404, "Plugin not found")
    plugin["status"] = "active"
    plugin["enabled"] = True
    return plugin


# ─── Webhook Subscriptions ──────────────────────────────────────────────────

@router.get("/")
async def list_webhooks():
    return {"items": _webhooks, "total": len(_webhooks)}


@router.post("/", status_code=201)
async def create_webhook(req: WebhookCreate):
    wh = req.model_dump()
    wh["id"] = f"wh-{len(_webhooks)+1}"
    wh["created_at"] = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    wh["last_triggered"] = None
    wh["trigger_count"] = 0
    wh["failure_count"] = 0
    _webhooks.append(wh)
    return wh


@router.get("/{webhook_id}")
async def get_webhook(webhook_id: str):
    wh = next((w for w in _webhooks if w.get("id") == webhook_id), None)
    if not wh:
        raise HTTPException(404, "Webhook not found")
    return wh


@router.put("/{webhook_id}")
async def update_webhook(webhook_id: str, req: WebhookCreate):
    for i, wh in enumerate(_webhooks):
        if wh.get("id") == webhook_id:
            updated = req.model_dump()
            updated["id"] = webhook_id
            updated["created_at"] = wh.get("created_at")
            updated["last_triggered"] = wh.get("last_triggered")
            updated["trigger_count"] = wh.get("trigger_count", 0)
            updated["failure_count"] = wh.get("failure_count", 0)
            _webhooks[i] = updated
            return updated
    raise HTTPException(404, "Webhook not found")


@router.delete("/{webhook_id}", status_code=204)
async def delete_webhook(webhook_id: str):
    global _webhooks
    _webhooks = [w for w in _webhooks if w.get("id") != webhook_id]


@router.post("/{webhook_id}/test")
async def test_webhook(webhook_id: str):
    wh = next((w for w in _webhooks if w.get("id") == webhook_id), None)
    if not wh:
        raise HTTPException(404, "Webhook not found")
    try:
        import httpx
        import hashlib
        import hmac
        payload = {"event": "test", "source": "neuranac", "timestamp": datetime.now(timezone.utc).replace(tzinfo=None).isoformat()}
        headers = dict(wh.get("headers", {}))
        if wh.get("secret"):
            sig = hmac.new(wh["secret"].encode(), json.dumps(payload).encode(), hashlib.sha256).hexdigest()
            headers["X-NeuraNAC-Signature"] = f"sha256={sig}"
        async with httpx.AsyncClient(timeout=wh.get("timeout_seconds", 10)) as client:
            resp = await client.post(wh["url"], json=payload, headers=headers)
            return {"status": "success", "http_status": resp.status_code}
    except Exception as e:
        return {"status": "failed", "error": str(e)}


async def dispatch_event(event_type: str, payload: dict):
    """Dispatch an event to all matching webhook subscribers (called internally)"""
    import httpx
    import hashlib
    import hmac
    for wh in _webhooks:
        if not wh.get("enabled", True):
            continue
        if event_type not in wh.get("events", []) and "*" not in wh.get("events", []):
            continue
        try:
            body = {"event": event_type, "payload": payload, "timestamp": datetime.now(timezone.utc).replace(tzinfo=None).isoformat()}
            headers = dict(wh.get("headers", {}))
            if wh.get("secret"):
                sig = hmac.new(wh["secret"].encode(), json.dumps(body).encode(), hashlib.sha256).hexdigest()
                headers["X-NeuraNAC-Signature"] = f"sha256={sig}"
            async with httpx.AsyncClient(timeout=wh.get("timeout_seconds", 10)) as client:
                await client.post(wh["url"], json=body, headers=headers)
            wh["trigger_count"] = wh.get("trigger_count", 0) + 1
            wh["last_triggered"] = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        except Exception:
            wh["failure_count"] = wh.get("failure_count", 0) + 1
