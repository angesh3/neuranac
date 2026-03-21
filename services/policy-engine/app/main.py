"""NeuraNAC Policy Engine - Evaluates access control policies"""
import asyncio
import os
from concurrent import futures
from contextlib import asynccontextmanager

import grpc
import structlog
from fastapi import FastAPI

from app.engine import PolicyEvaluator
from app.grpc_server import PolicyServicer

logger = structlog.get_logger()
evaluator: PolicyEvaluator = None
grpc_server = None
_nats_nc = None
_nats_sub = None

# Site / deployment context (loaded from environment)
SITE_ID = os.getenv("NEURANAC_SITE_ID", "00000000-0000-0000-0000-000000000001")
SITE_TYPE = os.getenv("NEURANAC_SITE_TYPE", "onprem")
DEPLOYMENT_MODE = os.getenv("DEPLOYMENT_MODE", "standalone")


async def _start_nats_subscriber():
    """Subscribe to NATS for live policy reload notifications."""
    global _nats_nc, _nats_sub
    nats_url = os.getenv("NATS_URL", "")
    if not nats_url:
        logger.info("NATS_URL not set — live policy reload disabled")
        return
    try:
        import nats as nats_pkg
        _nats_nc = await nats_pkg.connect(nats_url)
        js = _nats_nc.jetstream()

        async def _on_policy_change(msg):
            logger.info("Received policy change event, reloading policies", subject=msg.subject)
            if evaluator:
                await evaluator.load_policies()
            await msg.ack()

        _nats_sub = await js.subscribe(
            "neuranac.policy.changed",
            durable="policy-engine-reload",
            stream="neuranac",
        )
        # Start consuming in background
        asyncio.create_task(_nats_consume(_nats_sub, _on_policy_change))
        logger.info("NATS policy reload subscriber started", subject="neuranac.policy.changed")
    except Exception as exc:
        logger.warning("NATS subscription failed — live reload disabled", error=str(exc))


async def _nats_consume(sub, handler):
    """Consume messages from NATS subscription."""
    try:
        async for msg in sub.messages:
            await handler(msg)
    except Exception as exc:
        logger.warning("NATS consumer stopped", error=str(exc))


async def _stop_nats():
    global _nats_nc, _nats_sub
    if _nats_sub:
        try:
            await _nats_sub.unsubscribe()
        except Exception:
            pass
        _nats_sub = None
    if _nats_nc:
        try:
            await _nats_nc.close()
        except Exception:
            pass
        _nats_nc = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global evaluator, grpc_server
    logger.info("Starting NeuraNAC Policy Engine",
                 site_id=SITE_ID, site_type=SITE_TYPE, deployment_mode=DEPLOYMENT_MODE)
    evaluator = PolicyEvaluator(site_id=SITE_ID, site_type=SITE_TYPE, deployment_mode=DEPLOYMENT_MODE)
    await evaluator.load_policies()

    # Start gRPC server in background
    # SECURITY: gRPC reflection is intentionally NOT enabled.
    # Reflection exposes service/method metadata and must remain disabled in production.
    grpc_server = grpc.aio.server(futures.ThreadPoolExecutor(max_workers=10))
    PolicyServicer.register(grpc_server, evaluator)

    grpc_port = int(os.getenv("GRPC_PORT", "9091"))
    tls_cert = os.getenv("GRPC_TLS_CERT", "")
    tls_key = os.getenv("GRPC_TLS_KEY", "")
    ca_cert = os.getenv("GRPC_CA_CERT", "")

    if tls_cert and tls_key and os.path.isfile(tls_cert) and os.path.isfile(tls_key):
        with open(tls_cert, "rb") as f:
            cert_pem = f.read()
        with open(tls_key, "rb") as f:
            key_pem = f.read()
        ca_pem = None
        if ca_cert and os.path.isfile(ca_cert):
            with open(ca_cert, "rb") as f:
                ca_pem = f.read()
        creds = grpc.ssl_server_credentials(
            [(key_pem, cert_pem)],
            root_certificates=ca_pem,
            require_client_auth=ca_pem is not None,
        )
        grpc_server.add_secure_port(f"[::]:{grpc_port}", creds)
        logger.info("Policy Engine gRPC server started with mTLS", port=grpc_port,
                    mutual_auth=ca_pem is not None)
    else:
        if os.getenv("NeuraNAC_ENV") == "production":
            raise RuntimeError(
                f"GRPC_TLS_CERT and GRPC_TLS_KEY are required in production. "
                f"Set NeuraNAC_ENV != 'production' to allow insecure gRPC."
            )
        grpc_server.add_insecure_port(f"[::]:{grpc_port}")
        logger.warning("Policy Engine gRPC server started INSECURE (no TLS certs)", port=grpc_port)

    await grpc_server.start()

    # Start NATS subscriber for live policy reload
    await _start_nats_subscriber()

    yield

    await _stop_nats()
    await grpc_server.stop(5)
    logger.info("Policy Engine stopped")


app = FastAPI(title="NeuraNAC Policy Engine", version="1.0.0", lifespan=lifespan)


@app.get("/health")
async def health():
    pool_stats = {}
    if evaluator and evaluator.db_pool:
        pool = evaluator.db_pool
        pool_stats = {
            "pool_size": pool.get_size(),
            "pool_free": pool.get_idle_size(),
            "pool_min": pool.get_min_size(),
            "pool_max": pool.get_max_size(),
        }
    return {
        "status": "healthy",
        "service": "policy-engine",
        "site_id": SITE_ID,
        "site_type": SITE_TYPE,
        "deployment_mode": DEPLOYMENT_MODE,
        "policies_loaded": evaluator.policy_count if evaluator else 0,
        "nats_connected": _nats_nc is not None and _nats_nc.is_connected if _nats_nc else False,
        "db_pool": pool_stats,
    }


@app.post("/api/v1/evaluate")
async def evaluate_policy(request: dict):
    if not evaluator:
        return {"error": "Engine not ready"}
    result = await evaluator.evaluate(request)
    return result


@app.post("/api/v1/reload")
async def reload_policies():
    if evaluator:
        await evaluator.load_policies()
    return {"status": "reloaded", "policies_loaded": evaluator.policy_count}
