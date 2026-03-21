"""Session and identity source intents."""

SESSION_INTENTS = [
    {"intent": "list_sessions", "patterns": ["list sessions", "show sessions", "active sessions", "all sessions", "auth sessions"],
     "method": "GET", "path": "/api/v1/sessions/", "description": "List all sessions"},
    {"intent": "failed_sessions", "patterns": ["failed auth", "failed sessions", "rejected sessions", "auth failures", "access reject"],
     "method": "GET", "path": "/api/v1/sessions/?auth_result=reject", "description": "Show failed authentication sessions"},
    {"intent": "session_count", "patterns": ["how many sessions", "session count", "active count", "active session count"],
     "method": "GET", "path": "/api/v1/sessions/active/count", "description": "Get active session count"},
    {"intent": "list_identity", "patterns": ["list identity", "show identity", "identity sources", "ldap", "active directory"],
     "method": "GET", "path": "/api/v1/identity-sources/", "description": "List identity sources"},
    {"intent": "add_identity", "patterns": ["add identity", "add ldap", "new identity source", "create identity"],
     "method": "POST", "path": "/api/v1/identity-sources/", "description": "Add an identity source",
     "extract_fields": ["name", "source_type", "config"]},
]
