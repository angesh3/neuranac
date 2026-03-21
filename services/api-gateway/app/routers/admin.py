"""Admin users, roles, and settings router"""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database.session import get_db
from app.models.admin import AdminUser, AdminRole, Tenant
from app.middleware.auth import hash_password, require_permission
from app.middleware.tenant_helper import get_tenant_id

router = APIRouter()


class AdminUserCreate(BaseModel):
    username: str
    email: Optional[str] = None
    password: str
    role_name: str = "admin"


class AdminRoleCreate(BaseModel):
    name: str
    description: Optional[str] = None
    permissions: List[str] = []


class TenantCreate(BaseModel):
    name: str
    slug: str
    isolation_mode: str = "row"


@router.get("/users", dependencies=[Depends(require_permission("admin:read"))])
async def list_admin_users(skip: int = Query(0), limit: int = Query(50), db: AsyncSession = Depends(get_db)):
    total = await db.scalar(select(func.count()).select_from(AdminUser))
    result = await db.execute(select(AdminUser).offset(skip).limit(limit))
    items = result.scalars().all()
    return {"items": [_ser_user(u) for u in items], "total": total or 0}


@router.post("/users", status_code=201, dependencies=[Depends(require_permission("admin:manage"))])
async def create_admin_user(req: AdminUserCreate, request: Request, db: AsyncSession = Depends(get_db)):
    user = AdminUser(username=req.username, email=req.email, password_hash=hash_password(req.password),
                     role_name=req.role_name, tenant_id=get_tenant_id(request))
    db.add(user)
    await db.flush()
    return _ser_user(user)


@router.get("/users/{user_id}", dependencies=[Depends(require_permission("admin:read"))])
async def get_admin_user(user_id: UUID, db: AsyncSession = Depends(get_db)):
    user = await db.get(AdminUser, user_id)
    if not user:
        raise HTTPException(404, "Admin user not found")
    return _ser_user(user)


@router.delete("/users/{user_id}", status_code=204, dependencies=[Depends(require_permission("admin:manage"))])
async def delete_admin_user(user_id: UUID, db: AsyncSession = Depends(get_db)):
    user = await db.get(AdminUser, user_id)
    if not user:
        raise HTTPException(404, "Admin user not found")
    await db.delete(user)


@router.get("/roles", dependencies=[Depends(require_permission("admin:read"))])
async def list_admin_roles(skip: int = Query(0), limit: int = Query(50, le=200), db: AsyncSession = Depends(get_db)):
    total = await db.scalar(select(func.count()).select_from(AdminRole))
    result = await db.execute(select(AdminRole).offset(skip).limit(limit).order_by(AdminRole.name))
    items = result.scalars().all()
    return {"items": [_ser_role(r) for r in items], "total": total or 0, "skip": skip, "limit": limit}


@router.post("/roles", status_code=201, dependencies=[Depends(require_permission("admin:manage"))])
async def create_admin_role(req: AdminRoleCreate, request: Request, db: AsyncSession = Depends(get_db)):
    role = AdminRole(name=req.name, description=req.description, permissions=req.permissions,
                     tenant_id=get_tenant_id(request))
    db.add(role)
    await db.flush()
    return _ser_role(role)


@router.get("/tenants", dependencies=[Depends(require_permission("admin:read"))])
async def list_tenants(skip: int = Query(0), limit: int = Query(50, le=200), db: AsyncSession = Depends(get_db)):
    total = await db.scalar(select(func.count()).select_from(Tenant))
    result = await db.execute(select(Tenant).offset(skip).limit(limit).order_by(Tenant.created_at.desc()))
    items = result.scalars().all()
    return {"items": [_ser_tenant(t) for t in items], "total": total or 0, "skip": skip, "limit": limit}


@router.post("/tenants", status_code=201, dependencies=[Depends(require_permission("admin:manage"))])
async def create_tenant(req: TenantCreate, db: AsyncSession = Depends(get_db)):
    tenant = Tenant(name=req.name, slug=req.slug, isolation_mode=req.isolation_mode)
    db.add(tenant)
    await db.flush()
    return _ser_tenant(tenant)


def _ser_user(u: AdminUser) -> dict:
    return {"id": str(u.id), "username": u.username, "email": u.email,
            "role_name": u.role_name, "is_active": u.is_active, "mfa_enabled": u.mfa_enabled,
            "last_login": str(u.last_login) if u.last_login else None}


def _ser_role(r: AdminRole) -> dict:
    return {"id": str(r.id), "name": r.name, "description": r.description,
            "permissions": r.permissions, "is_builtin": r.is_builtin}


def _ser_tenant(t: Tenant) -> dict:
    return {"id": str(t.id), "name": t.name, "slug": t.slug,
            "isolation_mode": t.isolation_mode, "status": t.status,
            "created_at": str(t.created_at) if t.created_at else None}
