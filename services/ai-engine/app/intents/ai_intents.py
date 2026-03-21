"""AI, shadow AI, risk, anomaly, and drift intents."""

AI_INTENTS = [
    {"intent": "list_ai_agents", "patterns": ["list ai agent", "show ai agent", "ai agents", "registered agent"],
     "method": "GET", "path": "/api/v1/ai/agents/", "description": "List AI agents"},
    {"intent": "shadow_detections", "patterns": ["shadow ai", "shadow detection", "unauthorized ai", "ai detection"],
     "method": "GET", "path": "/api/v1/ai/data-flow/detections", "description": "Show shadow AI detections"},
    {"intent": "ai_services", "patterns": ["ai service", "known ai service", "ai registry"],
     "method": "GET", "path": "/api/v1/ai/data-flow/services", "description": "List known AI services"},
    {"intent": "ai_data_policies", "patterns": ["ai data flow", "ai policies", "data flow polic"],
     "method": "GET", "path": "/api/v1/ai/data-flow/policies", "description": "List AI data flow policies"},
    {"intent": "create_ai_policy", "patterns": ["block ai", "block openai", "allow ai", "create ai policy", "ai data flow policy"],
     "method": "POST", "path": "/api/v1/ai/data-flow/policies", "description": "Create AI data flow policy",
     "extract_fields": ["name", "service_type", "action"]},
    {"intent": "risk_score", "patterns": ["risk score", "compute risk", "risk assessment", "threat score"],
     "method": "POST", "path": "/api/v1/ai/risk-score", "description": "Compute risk score for a session"},
    {"intent": "anomaly_check", "patterns": ["anomaly", "anomalous", "unusual behavior", "behavior analysis"],
     "method": "POST", "path": "/api/v1/ai/anomaly/analyze", "description": "Analyze for anomalies"},
    {"intent": "drift_analysis", "patterns": ["drift", "policy drift", "drift analysis", "policy mismatch"],
     "method": "GET", "path": "/api/v1/ai/drift/analyze", "description": "Analyze policy drift"},
]
