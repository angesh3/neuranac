"""Authentication router"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database.session import get_db
from app.middleware.auth import (
    create_access_token, create_refresh_token, verify_password, decode_token,
    hash_password, store_refresh_token, validate_and_rotate_refresh, revoke_token_family,
)

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 900


class RefreshRequest(BaseModel):
    refresh_token: str


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    from app.models.admin import AdminUser
    result = await db.execute(select(AdminUser).where(AdminUser.username == req.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token_data = {
        "sub": str(user.id),
        "tenant_id": str(user.tenant_id),
        "username": user.username,
        "roles": [user.role_name] if hasattr(user, 'role_name') else ["admin"],
        "permissions": ["admin:super"],
    }
    refresh_token = create_refresh_token(token_data)
    # Store refresh token in Redis for rotation tracking
    rt_payload = decode_token(refresh_token)
    await store_refresh_token(
        jti=rt_payload.get("jti", ""),
        family_id=rt_payload.get("family", ""),
        user_id=str(user.id),
    )
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=refresh_token,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(req: RefreshRequest):
    payload = await validate_and_rotate_refresh(req.refresh_token)
    family_id = payload.get("family")
    token_data = {k: v for k, v in payload.items() if k not in ("exp", "type", "jti", "family")}
    new_refresh = create_refresh_token(token_data, family_id=family_id)
    # Store the new refresh token
    rt_payload = decode_token(new_refresh)
    await store_refresh_token(
        jti=rt_payload.get("jti", ""),
        family_id=family_id or "",
        user_id=payload.get("sub", ""),
    )
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=new_refresh,
    )


@router.post("/logout")
async def logout(request = None):
    # If the request has a refresh token, revoke its family
    try:
        if request:
            body = await request.json()
            rt = body.get("refresh_token", "")
            if rt:
                rt_payload = decode_token(rt)
                family_id = rt_payload.get("family")
                if family_id:
                    await revoke_token_family(family_id)
    except Exception:
        pass
    return {"message": "Logged out successfully"}
