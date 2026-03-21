"""Authentication and authorization schemas."""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
from uuid import UUID


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 900


class TokenRefreshRequest(BaseModel):
    refresh_token: str


class TokenRefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 900


class UserResponse(BaseModel):
    id: UUID
    username: str
    email: Optional[str] = None
    role_name: str
    is_active: bool
    mfa_enabled: bool = False
    last_login: Optional[datetime] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class RoleResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None
    permissions: List[str] = Field(default_factory=list)
    is_builtin: bool = False

    class Config:
        from_attributes = True


class AuditLogResponse(BaseModel):
    id: UUID
    actor: str
    action: str
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    source_ip: Optional[str] = None
    timestamp: Optional[datetime] = None

    class Config:
        from_attributes = True
