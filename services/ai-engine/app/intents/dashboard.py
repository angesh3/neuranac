"""Dashboard and system overview intents."""

DASHBOARD_INTENTS = [
    {"intent": "show_dashboard", "patterns": ["dashboard", "overview", "summary", "home", "system status"],
     "method": "GET", "path": "/api/v1/diagnostics/system-status", "description": "Show system dashboard overview"},
    {"intent": "system_status", "patterns": ["system status", "health check", "is everything ok", "service health", "system health"],
     "method": "GET", "path": "/api/v1/diagnostics/system-status", "description": "Check system health"},
    {"intent": "show_settings", "patterns": ["settings", "configuration", "show settings", "system settings"],
     "method": "GET", "path": "/api/v1/admin/settings", "description": "Show system settings"},
    {"intent": "show_licenses", "patterns": ["license", "licensing", "license status", "usage"],
     "method": "GET", "path": "/api/v1/licenses/", "description": "Show license information"},
    {"intent": "audit_log", "patterns": ["audit", "audit log", "who changed", "activity log"],
     "method": "GET", "path": "/api/v1/audit/", "description": "Show audit log"},
]
