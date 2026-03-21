"""Policy management intents."""

POLICY_INTENTS = [
    {"intent": "list_policies", "patterns": ["list policies", "show policies", "get policies", "all policies"],
     "method": "GET", "path": "/api/v1/policies/", "description": "List all policy sets"},
    {"intent": "create_policy", "patterns": ["create policy", "add policy", "new policy", "make policy"],
     "method": "POST", "path": "/api/v1/policies/", "description": "Create a new policy set",
     "extract_fields": ["name", "description", "match_type"]},
    {"intent": "delete_policy", "patterns": ["delete policy", "remove policy"],
     "method": "DELETE", "path": "/api/v1/policies/{id}", "description": "Delete a policy set",
     "extract_fields": ["id"]},
    {"intent": "list_posture", "patterns": ["list posture", "posture policies", "compliance", "show posture"],
     "method": "GET", "path": "/api/v1/posture/policies", "description": "List posture policies"},
    {"intent": "create_posture", "patterns": ["create posture", "add posture", "new posture policy"],
     "method": "POST", "path": "/api/v1/posture/policies", "description": "Create a posture policy",
     "extract_fields": ["name", "os_type", "checks"]},
    {"intent": "translate_policy", "patterns": ["translate.*policy", "natural language.*policy", "nlp.*policy",
                                                  "create.*rule.*for", "assign.*vlan", "block.*user", "allow.*employee"],
     "method": "POST", "path": "/api/v1/ai/nlp/translate", "description": "Translate natural language to policy",
     "passthrough": True},
]
