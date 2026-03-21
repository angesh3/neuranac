"""Tenant Management Router — CRUD, quotas, onboarding for multi-tenant SaaS.

Provides:
  - Tenant lifecycle (create, read, update, delete, list)
  - Quota management (view, update limits)
  - Node allocation (assign/release nodes to tenants)
  - Tenant onboarding flow (provision site + default config)

Security:
  - All endpoints require admin:manage permission
  - Tenant isolation enforced at row level via tenant_id FK
  - Node-to-tenant mapping enforced: 1 node → 1 tenant (many nodes per tenant OK)
"""
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import structlog

from app.config import get_settings
from app.database.session import get_db
from app.middleware.auth import require_permission
from app.middleware.tenant_helper import get_tenant_id

logger = structlog.get_logger()
router = APIRouter()


# ─── Models ──────────────────────────────────────────────────────────────────

class TenantCreate(BaseModel):
    name: str
    slug: str = Field(..., pattern="^[a-z0-9][a-z0-9-]{1,98}[a-z0-9]$")
    isolation_mode: str = Field(default="row", pattern="^(row|schema|namespace)$")
    tier: str = Field(default="standard", pattern="^(free|standard|enterprise|unlimited)$")
    settings: dict = {}


class TenantUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None
    settings: Optional[dict] = None


class QuotaUpdate(BaseModel):
    max_sites: Optional[int] = None
    max_nodes: Optional[int] = None
    max_connectors: Optional[int] = None
    max_sessions: Optional[int] = None
    max_policies: Optional[int] = None
    max_endpoints: Optional[int] = None
    max_admins: Optional[int] = None
    storage_gb: Optional[int] = None
    tier: Optional[str] = None


class NodeAllocate(BaseModel):
    node_id: str
    tenant_id: str


# ─── Tenant CRUD ──────────────────────────────────────────────────────────────

@router.get("/", dependencies=[Depends(require_permission("admin:manage"))])
async def list_tenants(db: AsyncSession = Depends(get_db)):
    """List all tenants with usage stats."""
    result = await db.execute(text(
        "SELECT t.id, t.name, t.slug, t.isolation_mode, t.status, t.settings, "
        "t.created_at, t.updated_at, "
        "q.tier, q.max_sites, q.max_nodes, q.max_connectors, q.max_sessions, "
        "(SELECT count(*) FROM neuranac_sites s WHERE s.tenant_id = t.id) as site_count, "
        "(SELECT count(*) FROM neuranac_node_registry n WHERE n.tenant_id = t.id) as node_count, "
        "(SELECT count(*) FROM neuranac_connectors c WHERE c.tenant_id = t.id) as connector_count "
        "FROM tenants t "
        "LEFT JOIN neuranac_tenant_quotas q ON q.tenant_id = t.id "
        "ORDER BY t.created_at"
    ))
    rows = result.fetchall()
    items = []
    for r in rows:
        items.append({
            "id": str(r[0]), "name": r[1], "slug": r[2],
            "isolation_mode": r[3], "status": r[4],
            "settings": r[5], "created_at": r[6].isoformat() if r[6] else None,
            "updated_at": r[7].isoformat() if r[7] else None,
            "quota": {
                "tier": r[8] or "standard",
                "max_sites": r[9], "max_nodes": r[10],
                "max_connectors": r[11], "max_sessions": r[12],
            },
            "usage": {
                "sites": r[13], "nodes": r[14], "connectors": r[15],
            },
        })
    return {"items": items, "total": len(items)}


@router.get("/{tenant_id}", dependencies=[Depends(require_permission("admin:manage"))])
async def get_tenant(tenant_id: str, db: AsyncSession = Depends(get_db)):
    """Get detailed tenant info with quota and usage."""
    result = await db.execute(text(
        "SELECT t.id, t.name, t.slug, t.isolation_mode, t.status, t.settings, "
        "t.created_at, t.updated_at "
        "FROM tenants t WHERE t.id = :tid"
    ), {"tid": tenant_id})
    r = result.fetchone()
    if not r:
        raise HTTPException(404, "Tenant not found")

    # Fetch quota
    q_result = await db.execute(text(
        "SELECT tier, max_sites, max_nodes, max_connectors, max_sessions, "
        "max_policies, max_endpoints, max_admins, storage_gb, custom_limits "
        "FROM neuranac_tenant_quotas WHERE tenant_id = :tid"
    ), {"tid": tenant_id})
    q = q_result.fetchone()

    # Fetch usage counts
    usage_result = await db.execute(text(
        "SELECT "
        "(SELECT count(*) FROM neuranac_sites WHERE tenant_id = :tid), "
        "(SELECT count(*) FROM neuranac_node_registry WHERE tenant_id = :tid), "
        "(SELECT count(*) FROM neuranac_connectors WHERE tenant_id = :tid), "
        "(SELECT count(*) FROM admin_users WHERE tenant_id = :tid)"
    ), {"tid": tenant_id})
    u = usage_result.fetchone()

    return {
        "id": str(r[0]), "name": r[1], "slug": r[2],
        "isolation_mode": r[3], "status": r[4], "settings": r[5],
        "created_at": r[6].isoformat() if r[6] else None,
        "updated_at": r[7].isoformat() if r[7] else None,
        "quota": {
            "tier": q[0] if q else "standard",
            "max_sites": q[1] if q else 5, "max_nodes": q[2] if q else 20,
            "max_connectors": q[3] if q else 10, "max_sessions": q[4] if q else 10000,
            "max_policies": q[5] if q else 500, "max_endpoints": q[6] if q else 50000,
            "max_admins": q[7] if q else 50, "storage_gb": q[8] if q else 100,
            "custom_limits": q[9] if q else {},
        },
        "usage": {
            "sites": u[0] if u else 0, "nodes": u[1] if u else 0,
            "connectors": u[2] if u else 0, "admins": u[3] if u else 0,
        },
    }


@router.post("/", status_code=201,
             dependencies=[Depends(require_permission("admin:manage"))])
async def create_tenant(body: TenantCreate, db: AsyncSession = Depends(get_db)):
    """Provision a new tenant with default quota and site.

    Creates:
      1. Tenant record
      2. Default quota based on tier
      3. Default deployment config
      4. Default site for the tenant
    """
    # Check slug uniqueness
    existing = await db.execute(
        text("SELECT id FROM tenants WHERE slug = :slug"), {"slug": body.slug})
    if existing.fetchone():
        raise HTTPException(409, f"Tenant slug '{body.slug}' already exists")

    # 1. Create tenant
    result = await db.execute(text(
        "INSERT INTO tenants (name, slug, isolation_mode, status, settings) "
        "VALUES (:name, :slug, :iso, 'active', :settings) RETURNING id"
    ), {
        "name": body.name, "slug": body.slug,
        "iso": body.isolation_mode, "settings": str(body.settings),
    })
    row = result.fetchone()
    tenant_id = str(row[0])

    # 2. Create quota
    tier_defaults = {
        "free":       {"sites": 1, "nodes": 2,  "connectors": 1,  "sessions": 100},
        "standard":   {"sites": 5, "nodes": 20, "connectors": 10, "sessions": 10000},
        "enterprise": {"sites": 20, "nodes": 100, "connectors": 50, "sessions": 100000},
        "unlimited":  {"sites": 999, "nodes": 999, "connectors": 999, "sessions": 999999},
    }
    defaults = tier_defaults.get(body.tier, tier_defaults["standard"])
    await db.execute(text(
        "INSERT INTO neuranac_tenant_quotas (tenant_id, tier, max_sites, max_nodes, "
        "max_connectors, max_sessions) VALUES (:tid, :tier, :ms, :mn, :mc, :msess)"
    ), {
        "tid": tenant_id, "tier": body.tier,
        "ms": defaults["sites"], "mn": defaults["nodes"],
        "mc": defaults["connectors"], "msess": defaults["sessions"],
    })

    # 3. Create default deployment config
    await db.execute(text(
        "INSERT INTO neuranac_deployment_config (tenant_id, deployment_mode, legacy_nac_enabled) "
        "VALUES (:tid, 'standalone', false)"
    ), {"tid": tenant_id})

    # 4. Create default site
    await db.execute(text(
        "INSERT INTO neuranac_sites (tenant_id, name, site_type, deployment_mode) "
        "VALUES (:tid, :name, 'cloud', 'standalone')"
    ), {"tid": tenant_id, "name": f"{body.name} - Default Site"})

    await db.commit()
    logger.info("Tenant provisioned", tenant_id=tenant_id, slug=body.slug, tier=body.tier)
    return {"id": tenant_id, "slug": body.slug, "tier": body.tier, "status": "provisioned"}


@router.put("/{tenant_id}",
            dependencies=[Depends(require_permission("admin:manage"))])
async def update_tenant(tenant_id: str, body: TenantUpdate, db: AsyncSession = Depends(get_db)):
    """Update tenant properties."""
    sets = []
    params = {"tid": tenant_id}
    for field in ("name", "status"):
        val = getattr(body, field, None)
        if val is not None:
            sets.append(f"{field} = :{field}")
            params[field] = val
    if body.settings is not None:
        sets.append("settings = :settings")
        params["settings"] = str(body.settings)
    if not sets:
        raise HTTPException(400, "No fields to update")
    sets.append("updated_at = now()")
    query = f"UPDATE tenants SET {', '.join(sets)} WHERE id = :tid RETURNING id"
    result = await db.execute(text(query), params)
    await db.commit()
    if not result.fetchone():
        raise HTTPException(404, "Tenant not found")
    return {"id": tenant_id, "status": "updated"}


@router.delete("/{tenant_id}",
               dependencies=[Depends(require_permission("admin:manage"))])
async def delete_tenant(tenant_id: str, db: AsyncSession = Depends(get_db)):
    """Deactivate a tenant (soft delete — sets status to 'suspended')."""
    if tenant_id == "00000000-0000-0000-0000-000000000000":
        raise HTTPException(400, "Cannot delete the system default tenant")
    result = await db.execute(text(
        "UPDATE tenants SET status = 'suspended', updated_at = now() "
        "WHERE id = :tid RETURNING id"
    ), {"tid": tenant_id})
    await db.commit()
    if not result.fetchone():
        raise HTTPException(404, "Tenant not found")
    logger.info("Tenant suspended", tenant_id=tenant_id)
    return {"id": tenant_id, "status": "suspended"}


# ─── Quota Management ─────────────────────────────────────────────────────────

@router.get("/{tenant_id}/quota",
            dependencies=[Depends(require_permission("admin:manage"))])
async def get_tenant_quota(tenant_id: str, db: AsyncSession = Depends(get_db)):
    """Get tenant quota and current usage."""
    result = await db.execute(text(
        "SELECT tier, max_sites, max_nodes, max_connectors, max_sessions, "
        "max_policies, max_endpoints, max_admins, storage_gb, custom_limits "
        "FROM neuranac_tenant_quotas WHERE tenant_id = :tid"
    ), {"tid": tenant_id})
    q = result.fetchone()
    if not q:
        raise HTTPException(404, "Quota not found for tenant")

    usage_result = await db.execute(text(
        "SELECT "
        "(SELECT count(*) FROM neuranac_sites WHERE tenant_id = :tid), "
        "(SELECT count(*) FROM neuranac_node_registry WHERE tenant_id = :tid), "
        "(SELECT count(*) FROM neuranac_connectors WHERE tenant_id = :tid)"
    ), {"tid": tenant_id})
    u = usage_result.fetchone()

    return {
        "tenant_id": tenant_id,
        "limits": {
            "tier": q[0], "max_sites": q[1], "max_nodes": q[2],
            "max_connectors": q[3], "max_sessions": q[4],
            "max_policies": q[5], "max_endpoints": q[6],
            "max_admins": q[7], "storage_gb": q[8],
            "custom_limits": q[9],
        },
        "usage": {
            "sites": u[0] if u else 0,
            "nodes": u[1] if u else 0,
            "connectors": u[2] if u else 0,
        },
    }


@router.put("/{tenant_id}/quota",
            dependencies=[Depends(require_permission("admin:manage"))])
async def update_tenant_quota(tenant_id: str, body: QuotaUpdate, db: AsyncSession = Depends(get_db)):
    """Update tenant quota limits."""
    sets = []
    params = {"tid": tenant_id}
    for field in ("max_sites", "max_nodes", "max_connectors", "max_sessions",
                  "max_policies", "max_endpoints", "max_admins", "storage_gb", "tier"):
        val = getattr(body, field, None)
        if val is not None:
            sets.append(f"{field} = :{field}")
            params[field] = val
    if not sets:
        raise HTTPException(400, "No fields to update")
    sets.append("updated_at = now()")
    query = f"UPDATE neuranac_tenant_quotas SET {', '.join(sets)} WHERE tenant_id = :tid RETURNING id"
    result = await db.execute(text(query), params)
    await db.commit()
    if not result.fetchone():
        raise HTTPException(404, "Quota not found for tenant")
    return {"tenant_id": tenant_id, "status": "quota_updated"}


# ─── Node Allocation ──────────────────────────────────────────────────────────

@router.get("/{tenant_id}/nodes",
            dependencies=[Depends(require_permission("admin:manage"))])
async def list_tenant_nodes(tenant_id: str, db: AsyncSession = Depends(get_db)):
    """List all nodes allocated to a tenant."""
    result = await db.execute(text(
        "SELECT m.id, m.node_id, m.allocated_at, m.status, "
        "n.node_name, n.role, n.k8s_pod_name, n.k8s_namespace, "
        "n.service_type, n.ip_address, n.status as node_status, "
        "n.active_sessions, n.cpu_pct, n.mem_pct, n.last_heartbeat "
        "FROM neuranac_tenant_node_map m "
        "JOIN neuranac_node_registry n ON m.node_id = n.id "
        "WHERE m.tenant_id = :tid AND m.status = 'active' "
        "ORDER BY n.node_name"
    ), {"tid": tenant_id})
    rows = result.fetchall()
    items = []
    for r in rows:
        items.append({
            "allocation_id": str(r[0]), "node_id": str(r[1]),
            "allocated_at": r[2].isoformat() if r[2] else None,
            "allocation_status": r[3],
            "node_name": r[4], "role": r[5],
            "k8s_pod_name": r[6], "k8s_namespace": r[7],
            "service_type": r[8], "ip_address": r[9],
            "node_status": r[10], "active_sessions": r[11],
            "cpu_pct": r[12], "mem_pct": r[13],
            "last_heartbeat": r[14].isoformat() if r[14] else None,
        })
    return {"items": items, "total": len(items), "tenant_id": tenant_id}


@router.post("/nodes/allocate", status_code=201,
             dependencies=[Depends(require_permission("admin:manage"))])
async def allocate_node_to_tenant(body: NodeAllocate, db: AsyncSession = Depends(get_db)):
    """Allocate a node to a tenant.

    Enforces: one node can only be actively allocated to one tenant at a time.
    """
    # Verify tenant exists
    t_check = await db.execute(
        text("SELECT id FROM tenants WHERE id = :tid"), {"tid": body.tenant_id})
    if not t_check.fetchone():
        raise HTTPException(404, "Tenant not found")

    # Verify node exists
    n_check = await db.execute(
        text("SELECT id FROM neuranac_node_registry WHERE id = :nid"), {"nid": body.node_id})
    if not n_check.fetchone():
        raise HTTPException(404, "Node not found")

    # Check quota
    quota_check = await db.execute(text(
        "SELECT q.max_nodes, "
        "(SELECT count(*) FROM neuranac_tenant_node_map WHERE tenant_id = :tid AND status = 'active') "
        "FROM neuranac_tenant_quotas q WHERE q.tenant_id = :tid"
    ), {"tid": body.tenant_id})
    q_row = quota_check.fetchone()
    if q_row and q_row[1] >= q_row[0]:
        raise HTTPException(429, f"Tenant has reached node quota ({q_row[0]})")

    # Check node is not already allocated to another tenant
    existing = await db.execute(text(
        "SELECT tenant_id FROM neuranac_tenant_node_map "
        "WHERE node_id = :nid AND status = 'active'"
    ), {"nid": body.node_id})
    ex_row = existing.fetchone()
    if ex_row:
        if str(ex_row[0]) == body.tenant_id:
            raise HTTPException(409, "Node is already allocated to this tenant")
        raise HTTPException(409, "Node is already allocated to another tenant")

    # Allocate
    result = await db.execute(text(
        "INSERT INTO neuranac_tenant_node_map (tenant_id, node_id) "
        "VALUES (:tid, :nid) RETURNING id"
    ), {"tid": body.tenant_id, "nid": body.node_id})

    # Also stamp tenant_id on the node registry row
    await db.execute(text(
        "UPDATE neuranac_node_registry SET tenant_id = :tid WHERE id = :nid"
    ), {"tid": body.tenant_id, "nid": body.node_id})

    await db.commit()
    row = result.fetchone()
    logger.info("Node allocated to tenant",
                allocation_id=str(row[0]), node_id=body.node_id, tenant_id=body.tenant_id)
    return {"allocation_id": str(row[0]), "node_id": body.node_id,
            "tenant_id": body.tenant_id, "status": "allocated"}


@router.post("/nodes/{node_id}/release",
             dependencies=[Depends(require_permission("admin:manage"))])
async def release_node(node_id: str, db: AsyncSession = Depends(get_db)):
    """Release a node from its current tenant allocation."""
    result = await db.execute(text(
        "UPDATE neuranac_tenant_node_map SET status = 'released', released_at = now() "
        "WHERE node_id = :nid AND status = 'active' RETURNING id, tenant_id"
    ), {"nid": node_id})
    await db.execute(text(
        "UPDATE neuranac_node_registry SET tenant_id = NULL WHERE id = :nid"
    ), {"nid": node_id})
    await db.commit()
    row = result.fetchone()
    if not row:
        raise HTTPException(404, "No active allocation for this node")
    logger.info("Node released from tenant",
                allocation_id=str(row[0]), node_id=node_id, tenant_id=str(row[1]))
    return {"allocation_id": str(row[0]), "node_id": node_id,
            "tenant_id": str(row[1]), "status": "released"}
