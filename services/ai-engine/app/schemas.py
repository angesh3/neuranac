"""Pydantic request/response models for AI Engine endpoints (G25)."""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ─── Profiling ───────────────────────────────────────────────────────────────

class ProfileRequest(BaseModel):
    mac_address: str = Field(..., description="Endpoint MAC address")
    traffic_features: Dict[str, Any] = Field(default_factory=dict)
    dhcp_fingerprint: Optional[str] = None
    hostname: Optional[str] = None
    oui: Optional[str] = None


class ProfileResponse(BaseModel):
    device_type: str
    vendor: str
    os: Optional[str] = None
    confidence: float
    method: str = "ml"


# ─── Risk Scoring ────────────────────────────────────────────────────────────

class RiskScoreRequest(BaseModel):
    username: Optional[str] = None
    endpoint_mac: Optional[str] = None
    nas_ip: Optional[str] = None
    eap_type: Optional[str] = None
    tenant_id: str = "default"


class RiskScoreResponse(BaseModel):
    total_score: int
    risk_level: str
    factors: List[Dict[str, Any]] = []


# ─── Shadow AI Detection ─────────────────────────────────────────────────────

class ShadowAIDetectRequest(BaseModel):
    endpoint_mac: str
    traffic_sample: Dict[str, Any] = Field(default_factory=dict)
    dns_queries: List[str] = []
    tls_sni: List[str] = []


class ShadowAIDetectResponse(BaseModel):
    is_shadow_ai: bool
    confidence: float
    detected_services: List[Dict[str, Any]] = []
    recommendation: str = ""


# ─── NLP Policy Translation ──────────────────────────────────────────────────

class NLPTranslateRequest(BaseModel):
    natural_language: str
    context: Optional[str] = None


class NLPTranslateResponse(BaseModel):
    policy_json: Dict[str, Any]
    confidence: float
    explanation: str = ""


# ─── Troubleshoot ────────────────────────────────────────────────────────────

class TroubleshootRequest(BaseModel):
    session_id: Optional[str] = None
    endpoint_mac: Optional[str] = None
    username: Optional[str] = None
    error_type: Optional[str] = None
    symptoms: List[str] = []


class TroubleshootResponse(BaseModel):
    diagnosis: str
    root_cause: str = ""
    recommendations: List[str] = []
    confidence: float = 0.0


# ─── Anomaly Analysis ────────────────────────────────────────────────────────

class AnomalyRequest(BaseModel):
    endpoint_mac: Optional[str] = None
    username: Optional[str] = None
    nas_ip: Optional[str] = None
    eap_type: Optional[str] = None
    auth_time_hour: int = 0
    day_of_week: int = 0


class AnomalyResponse(BaseModel):
    is_anomalous: bool
    anomaly_score: int = 0
    factors: List[str] = []
    recommendation: str = ""


# ─── Drift ────────────────────────────────────────────────────────────────────

class DriftRecordRequest(BaseModel):
    policy_id: str
    expected_action: str
    actual_action: str
    matched: bool = False
    evaluation_time_us: int = 0


# ─── AI Chat ─────────────────────────────────────────────────────────────────

class AIChatRequest(BaseModel):
    message: str
    context: Dict[str, Any] = Field(default_factory=dict)
    token: Optional[str] = None


class AIChatResponse(BaseModel):
    intent: str = ""
    response: str = ""
    data: Optional[Dict[str, Any]] = None
    confidence: float = 0.0
    actions_taken: List[str] = []


# ─── RAG Troubleshoot ─────────────────────────────────────────────────────────

class RAGTroubleshootRequest(BaseModel):
    query: str
    context: Optional[Dict[str, Any]] = None


# ─── Training ─────────────────────────────────────────────────────────────────

class TrainingSampleRequest(BaseModel):
    mac_address: str
    device_type: str
    features: Dict[str, Any] = Field(default_factory=dict)


# ─── NL-SQL ───────────────────────────────────────────────────────────────────

class NLSQLRequest(BaseModel):
    question: str


# ─── Risk Feedback ────────────────────────────────────────────────────────────

class RiskFeedbackRequest(BaseModel):
    tenant_id: str = "default"
    risk_score: int = 0
    decision: str = "allow"
    was_correct: bool = True


# ─── TLS ──────────────────────────────────────────────────────────────────────

class TLSJA3Request(BaseModel):
    ja3_hash: str
    endpoint_mac: Optional[str] = None
    src_ip: Optional[str] = None
    dst_ip: Optional[str] = None


class TLSJA4Request(BaseModel):
    ja4_hash: str
    endpoint_mac: Optional[str] = None


class ComputeJA3Request(BaseModel):
    tls_version: int = 771
    cipher_suites: List[int] = []
    extensions: List[int] = []
    elliptic_curves: List[int] = []
    ec_point_formats: List[int] = []


class CustomTLSSigRequest(BaseModel):
    ja3_hash: str
    service: str
    description: str = ""
    risk: str = "medium"


# ─── Capacity ─────────────────────────────────────────────────────────────────

class CapacityRecordRequest(BaseModel):
    metric: str
    value: float
    timestamp: Optional[str] = None


# ─── Playbooks ────────────────────────────────────────────────────────────────

class PlaybookCreateRequest(BaseModel):
    id: str
    name: str
    description: str = ""
    trigger: str = ""
    severity: str = "medium"
    steps: List[Dict[str, Any]] = []


class PlaybookExecuteRequest(BaseModel):
    context: Dict[str, Any] = Field(default_factory=dict)


# ─── Model Registry ──────────────────────────────────────────────────────────

class ModelRegisterRequest(BaseModel):
    name: str
    version: str = "v1"
    model_type: str = ""
    endpoint: str = ""
    weight: float = 1.0
    metadata: Optional[Dict[str, Any]] = None


class ExperimentCreateRequest(BaseModel):
    name: str
    model_a_id: str
    model_b_id: str
    traffic_split: float = 0.5
