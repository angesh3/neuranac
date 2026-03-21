"""Network, policy, session, and endpoint response schemas."""
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from uuid import UUID


class NetworkDeviceResponse(BaseModel):
    id: UUID
    name: str
    ip_address: str
    device_type: Optional[str] = None
    vendor: Optional[str] = None
    model: Optional[str] = None
    radsec_enabled: bool = False
    coa_port: int = 3799
    location: Optional[str] = None
    status: str = "active"
    last_seen: Optional[datetime] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class NetworkDeviceCreate(BaseModel):
    name: str
    ip_address: str
    shared_secret: str
    device_type: Optional[str] = None
    vendor: Optional[str] = None
    model: Optional[str] = None
    radsec_enabled: bool = False
    coa_port: int = 3799
    location: Optional[str] = None


class EndpointResponse(BaseModel):
    id: UUID
    mac_address: str
    device_type: Optional[str] = None
    vendor: Optional[str] = None
    os: Optional[str] = None
    ip_address: Optional[str] = None
    status: str = "active"
    attributes: Dict[str, Any] = Field(default_factory=dict)
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None

    class Config:
        from_attributes = True


class SessionResponse(BaseModel):
    id: UUID
    session_id_radius: Optional[str] = None
    endpoint_mac: Optional[str] = None
    username: Optional[str] = None
    nas_ip: Optional[str] = None
    auth_method: Optional[str] = None
    auth_result: Optional[str] = None
    vlan_id: Optional[str] = None
    sgt: Optional[str] = None
    risk_score: int = 0
    is_active: bool = True
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PolicySetResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None
    priority: int = 1
    status: str = "active"
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PolicyRuleResponse(BaseModel):
    id: UUID
    policy_set_id: UUID
    name: str
    priority: int = 1
    conditions: List[dict] = Field(default_factory=list)
    auth_profile_id: Optional[UUID] = None
    action: str = "permit"
    status: str = "active"
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AuthorizationProfileResponse(BaseModel):
    id: UUID
    name: str
    vlan_id: Optional[str] = None
    vlan_name: Optional[str] = None
    sgt_value: Optional[int] = None
    dacl_id: Optional[str] = None
    coa_action: Optional[str] = None
    session_timeout: Optional[int] = None
    bandwidth_limit_mbps: Optional[int] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SecurityGroupResponse(BaseModel):
    id: UUID
    name: str
    tag_value: int
    description: Optional[str] = None
    is_ai_sgt: bool = False
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CertificateResponse(BaseModel):
    id: UUID
    subject: str
    serial: Optional[str] = None
    not_before: Optional[datetime] = None
    not_after: Optional[datetime] = None
    revoked: bool = False
    usage: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class IdentitySourceResponse(BaseModel):
    id: UUID
    name: str
    source_type: str
    priority: int = 1
    status: str = "active"
    last_sync: Optional[datetime] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
