"""Security: certificates, segmentation, guest, and privacy intents."""

SECURITY_INTENTS = [
    {"intent": "list_certs", "patterns": ["list cert", "show cert", "certificates", "all certs", "expiring cert"],
     "method": "GET", "path": "/api/v1/certificates/", "description": "List certificates"},
    {"intent": "list_cas", "patterns": ["list ca", "certificate authorities", "root ca", "show ca"],
     "method": "GET", "path": "/api/v1/certificates/cas", "description": "List certificate authorities"},
    {"intent": "list_sgts", "patterns": ["list sgt", "show sgt", "segmentation", "security group", "trustsec"],
     "method": "GET", "path": "/api/v1/segmentation/sgts", "description": "List security group tags"},
    {"intent": "create_sgt", "patterns": ["create sgt", "add sgt", "new sgt", "new security group"],
     "method": "POST", "path": "/api/v1/segmentation/sgts", "description": "Create a security group tag",
     "extract_fields": ["name", "tag_value", "description"]},
    {"intent": "list_portals", "patterns": ["list portal", "guest portal", "show portal", "captive portal"],
     "method": "GET", "path": "/api/v1/guest/portals", "description": "List guest portals"},
    {"intent": "list_guests", "patterns": ["list guest", "guest account", "show guest", "visitor"],
     "method": "GET", "path": "/api/v1/guest/accounts", "description": "List guest accounts"},
    {"intent": "list_subjects", "patterns": ["privacy", "data subject", "gdpr", "data protection"],
     "method": "GET", "path": "/api/v1/privacy/subjects", "description": "List data subjects"},
]
