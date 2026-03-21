"""Product knowledge intents — enables the AI Agent to answer questions about NeuraNAC.

These intents match conversational and exploratory questions and return
rich, context-aware text responses instead of proxying to an API endpoint.
Each intent has a "knowledge" key (the answer) instead of "path"/"method".
"""
from app.intents.nac_knowledge import NAC_KNOWLEDGE_ARTICLES

# Fetch the comprehensive competitor comparison from the NAC knowledge base
_COMPETITORS_CONTENT = next(
    (a["content"] for a in NAC_KNOWLEDGE_ARTICLES if a["id"] == "competitors_overview"),
    "Competitor comparison not available."
)

# ─── Core Product Knowledge Base ─────────────────────────────────────────────

_PRODUCT_OVERVIEW = (
    "**NeuraNAC (NeuraNAC)** is a next-generation cloud-native Network Access Control (NAC) "
    "platform designed to replace and extend Legacy NAC (Identity Services Engine).\n\n"
    "### What it does\n"
    "NeuraNAC centralizes **authentication, authorization, and accounting (AAA)** for every device "
    "and user on your network — wired, wireless, VPN, and IoT — while adding modern AI-powered "
    "security capabilities that Legacy NAC lacks.\n\n"
    "### Key Capabilities\n"
    "- **RADIUS Authentication** — Built-in RADIUS server with 802.1X, MAB, and TACACS+ support\n"
    "- **Policy Engine** — Centralized access policies with conditions, rules, and segmentation (SGTs/TrustSec)\n"
    "- **AI-Powered Security** — Shadow AI detection, adaptive risk scoring, anomaly detection, and TLS fingerprinting\n"
    "- **Legacy NAC Migration** — Zero-downtime migration wizard that imports NeuraNAC policies, endpoints, and network devices\n"
    "- **Twin-Node Architecture** — Active-active on-prem + cloud nodes with real-time sync for high availability\n"
    "- **Network Visibility** — Endpoint profiling, session monitoring, SNMP/NetFlow/Syslog ingestion\n"
    "- **Certificate Management** — Internal CA, SCEP enrollment, certificate lifecycle management\n"
    "- **Multi-Tenant SaaS** — Row-level tenant isolation, per-tenant quotas, and mTLS bridge trust\n\n"
    "### Architecture\n"
    "NeuraNAC is a **microservices** platform with 7 backend services:\n"
    "| Service | Purpose |\n"
    "|---|---|\n"
    "| API Gateway | REST API, auth, middleware (FastAPI) |\n"
    "| AI Engine | Intent routing, risk scoring, anomaly detection |\n"
    "| Policy Engine | Policy evaluation and enforcement |\n"
    "| RADIUS Server | 802.1X / MAB authentication (Go) |\n"
    "| Sync Engine | Twin-node replication (Go + gRPC) |\n"
    "| NeuraNAC Bridge | Secure on-prem ↔ cloud tunnel |\n"
    "| Ingestion Collector | SNMP, Syslog, NetFlow, DHCP collection |\n\n"
    "The **web dashboard** is a React + TypeScript SPA with an AI-first chat interface and a classic dashboard mode."
)

_FEATURES_DETAIL = (
    "### NeuraNAC Feature Overview\n\n"
    "**1. Network Access Control**\n"
    "- 802.1X wired & wireless authentication\n"
    "- MAC Authentication Bypass (MAB) for IoT/headless devices\n"
    "- RADIUS CoA (Change of Authorization) for dynamic policy updates\n"
    "- Guest & BYOD self-service portals\n\n"
    "**2. Policy Management**\n"
    "- Condition-based access policies (user role, device type, location, time, posture)\n"
    "- Security Group Tags (SGTs) and TrustSec segmentation\n"
    "- Natural language → policy translation (\"Allow all employees on VLAN 100\")\n"
    "- Policy drift detection and compliance auditing\n\n"
    "**3. AI & Machine Learning**\n"
    "- **Shadow AI Detection** — identifies unauthorized AI services on your network\n"
    "- **Adaptive Risk Scoring** — learns from feedback to adjust risk thresholds\n"
    "- **Anomaly Detection** — baselines endpoint behavior and flags deviations\n"
    "- **TLS Fingerprinting** — JA3/JA4 fingerprint analysis for threat detection\n"
    "- **NL-to-SQL** — query your data using natural language\n"
    "- **RAG Troubleshooter** — AI-assisted troubleshooting with knowledge base lookup\n"
    "- **Capacity Planning** — forecasting and growth analysis\n"
    "- **Automated Playbooks** — pre-built and custom incident response workflows\n\n"
    "**4. Cisco Legacy Integration**\n"
    "- Discover and connect to existing NeuraNAC deployments\n"
    "- Import policies, endpoints, network devices, and identity sources\n"
    "- Real-time Event Stream event streaming\n"
    "- Side-by-side RADIUS traffic analysis\n"
    "- AI-powered NeuraNAC → NeuraNAC policy translation\n\n"
    "**5. Infrastructure**\n"
    "- Twin-node active-active deployment (on-prem + cloud)\n"
    "- Real-time data replication via gRPC\n"
    "- Certificate authority and SCEP enrollment\n"
    "- Webhook integrations and SIEM forwarding\n"
    "- Prometheus/Grafana observability stack\n"
    "- Multi-tenant SaaS with zero-trust bridge connectivity"
)

_ARCHITECTURE = (
    "### NeuraNAC Architecture\n\n"
    "NeuraNAC uses a **microservices architecture** with the following components:\n\n"
    "```\n"
    "┌─────────────┐   ┌──────────────┐   ┌──────────────┐\n"
    "│  Web UI      │   │  API Gateway  │   │  AI Engine    │\n"
    "│  (React/TS)  │──▶│  (FastAPI)    │──▶│  (FastAPI)    │\n"
    "│  Port 5173   │   │  Port 8080    │   │  Port 8081    │\n"
    "└─────────────┘   └──────┬───────┘   └──────────────┘\n"
    "                         │\n"
    "        ┌────────────────┼────────────────┐\n"
    "        ▼                ▼                ▼\n"
    "┌──────────────┐ ┌──────────────┐ ┌──────────────┐\n"
    "│ RADIUS Server│ │ Policy Engine│ │ Sync Engine  │\n"
    "│ (Go)         │ │ (Python)     │ │ (Go + gRPC)  │\n"
    "│ Port 1812    │ │ Port 8082    │ │ Port 9090    │\n"
    "└──────────────┘ └──────────────┘ └──────────────┘\n"
    "        │                │                │\n"
    "        └────────────────┼────────────────┘\n"
    "                         ▼\n"
    "        ┌──────────┐ ┌───────┐ ┌──────┐\n"
    "        │ PostgreSQL│ │ Redis │ │ NATS │\n"
    "        │ Port 5432 │ │  6379 │ │ 4222 │\n"
    "        └──────────┘ └───────┘ └──────┘\n"
    "```\n\n"
    "**Data stores:**\n"
    "- **PostgreSQL** — primary database (61+ tables), policies, sessions, endpoints, audit log\n"
    "- **Redis** — caching, rate limiting, AI baselines, session store\n"
    "- **NATS JetStream** — event bus for real-time inter-service messaging\n\n"
    "**Additional services:**\n"
    "- **NeuraNAC Bridge** (port 8090) — secure tunnel between on-prem and cloud nodes\n"
    "- **Ingestion Collector** — SNMP traps (1162), Syslog (1514), NetFlow (2055), DHCP snooping (6767)\n"
    "- **Bridge Connector** — optional, bridges to existing Legacy NAC deployments\n\n"
    "**Deployment modes:** standalone, hybrid (on-prem + cloud), multi-tenant SaaS"
)

_HOW_TO_USE = (
    "### Getting Started with NeuraNAC\n\n"
    "**1. Log in** — Use the credentials provided during setup (default: `admin`)\n\n"
    "**2. Choose your mode:**\n"
    "- **AI Agent mode** (default) — chat with the AI to manage your network using natural language\n"
    "- **Dashboard mode** — click the **Dash** toggle for the traditional UI with sidebar navigation\n\n"
    "**3. Common first steps:**\n"
    "- Ask: *\"Show system status\"* to verify all services are healthy\n"
    "- Ask: *\"List network devices\"* to see discovered devices\n"
    "- Ask: *\"Create a policy named Guest Access\"* to create your first policy\n"
    "- Ask: *\"Show all endpoints\"* to see connected devices\n\n"
    "**4. If migrating from Legacy NAC:**\n"
    "- Navigate to **Legacy NAC → Legacy Overview** in Dashboard mode\n"
    "- Or ask: *\"Open NeuraNAC integration\"*\n"
    "- Add your legacy connection, test connectivity, then run the Migration Wizard\n\n"
    "**5. AI capabilities you can try:**\n"
    "- *\"Why is user jdoe failing authentication?\"* — AI troubleshooting\n"
    "- *\"Block all traffic to OpenAI\"* — Shadow AI policy creation\n"
    "- *\"Allow all employees on VLAN 100\"* — natural language → policy rules\n"
    "- *\"Show shadow AI detections\"* — AI-powered security insights\n"
    "- *\"Compute risk score for active sessions\"* — adaptive risk analysis"
)

_AI_AGENT_HELP = (
    "### What can the AI Agent do?\n\n"
    "I'm your NeuraNAC AI assistant. I can help you manage your entire network through conversation. "
    "Here's everything I can do:\n\n"
    "**🔍 View & Query**\n"
    "- Show dashboards, sessions, endpoints, network devices, policies, certificates\n"
    "- Query audit logs, RADIUS logs, system health\n"
    "- Check license status, node sync, service health\n\n"
    "**⚙️ Create & Configure**\n"
    "- Create access policies using natural language\n"
    "- Add network devices (switches, APs, WLCs)\n"
    "- Configure security group tags (SGTs)\n"
    "- Set up certificate authorities and enrollment\n"
    "- Create AI data flow policies and Shadow AI rules\n\n"
    "**🤖 AI & Analytics**\n"
    "- Detect shadow AI services on your network\n"
    "- Compute adaptive risk scores for sessions\n"
    "- Analyze endpoint anomalies and behavior drift\n"
    "- Run TLS fingerprint analysis (JA3/JA4)\n"
    "- Forecast capacity and plan growth\n"
    "- Execute automated incident response playbooks\n\n"
    "**🔧 Troubleshoot**\n"
    "- Diagnose authentication failures\n"
    "- Analyze RADIUS traffic patterns\n"
    "- Check policy drift and compliance\n"
    "- Review system diagnostics\n\n"
    "**🧭 Navigate**\n"
    "- Open any page: *\"Go to policies\"*, *\"Open NeuraNAC integration\"*, *\"Show settings\"*\n\n"
    "**💡 Pro tip:** Be specific! Instead of \"help me\", try *\"Show all failed authentications in the last hour\"* "
    "or *\"Create a policy that blocks IoT devices from the server VLAN\"*."
)

_NeuraNAC_MIGRATION = (
    "### Migrating from Legacy NAC to NeuraNAC\n\n"
    "NeuraNAC provides a **zero-downtime migration path** from Legacy NAC:\n\n"
    "**Step 1: Connect to NeuraNAC**\n"
    "- Add your NeuraNAC deployment (hostname, ERS credentials, Event Stream certificates)\n"
    "- NeuraNAC tests connectivity and auto-detects your NeuraNAC version\n\n"
    "**Step 2: Discovery**\n"
    "- NeuraNAC imports your NeuraNAC inventory: policies, endpoints, network devices, identity sources\n"
    "- Real-time Event Stream captures live session data\n\n"
    "**Step 3: Policy Translation**\n"
    "- AI-powered translation converts NeuraNAC authorization profiles → NeuraNAC access policies\n"
    "- Side-by-side comparison lets you review before applying\n\n"
    "**Step 4: Parallel Operation**\n"
    "- Run NeuraNAC alongside NeuraNAC with RADIUS traffic analysis\n"
    "- Compare authentication decisions between the two systems\n\n"
    "**Step 5: Cutover**\n"
    "- Redirect network devices to NeuraNAC RADIUS (port 1812)\n"
    "- NeuraNAC handles all authentications; NeuraNAC remains as backup\n\n"
    "**Step 6: Decommission NeuraNAC**\n"
    "- Once validated, remove NeuraNAC from the network\n\n"
    "Try: *\"Open NeuraNAC integration\"* or *\"Show legacy connections\"* to get started."
)

_SECURITY_INFO = (
    "### NeuraNAC Security Features\n\n"
    "**Zero-Trust Network Access**\n"
    "- Every device and user must authenticate before gaining network access\n"
    "- Continuous posture assessment and adaptive authorization\n"
    "- Dynamic VLAN and SGT assignment based on identity and context\n\n"
    "**AI-Powered Threat Detection**\n"
    "- **Shadow AI Detection** — identifies unauthorized AI/ML services (ChatGPT, Copilot, etc.) on your network\n"
    "- **Adaptive Risk Scoring** — machine learning model that adjusts risk thresholds based on analyst feedback\n"
    "- **Anomaly Detection** — baselines normal endpoint behavior and flags deviations\n"
    "- **TLS Fingerprinting** — JA3/JA4 signatures to identify malicious or unauthorized applications\n\n"
    "**Infrastructure Security**\n"
    "- mTLS between all microservices\n"
    "- Per-tenant ECDSA P-256 client certificates with SPIFFE URIs\n"
    "- Federation HMAC-SHA256 authentication between sites\n"
    "- JWT-based API authentication with RSA-256 signing\n"
    "- Rate limiting, input validation, and security headers middleware\n"
    "- Encrypted data at rest (PostgreSQL) and in transit (TLS 1.3)\n\n"
    "**Compliance & Auditing**\n"
    "- Complete audit trail of all administrative actions\n"
    "- Policy version history and drift detection\n"
    "- SIEM integration for log forwarding\n"
    "- Webhook notifications for security events"
)

_TWIN_NODES = (
    "### Twin-Node Architecture\n\n"
    "NeuraNAC uses an **active-active twin-node** deployment model:\n\n"
    "**On-Prem Node (Twin-A)**\n"
    "- Runs inside your data center\n"
    "- Handles local RADIUS authentication with minimal latency\n"
    "- Stores local copy of all policies, endpoints, and sessions\n\n"
    "**Cloud Node (Twin-B)**\n"
    "- Runs in your cloud environment (AWS/Azure/GCP) or NeuraNAC SaaS\n"
    "- Provides the management dashboard and AI capabilities\n"
    "- Serves as DR/failover for the on-prem node\n\n"
    "**Real-Time Sync**\n"
    "- Bidirectional gRPC replication with sub-second sync lag\n"
    "- Automatic conflict resolution with configurable merge strategies\n"
    "- NATS JetStream for event-driven state propagation\n\n"
    "**NeuraNAC Bridge**\n"
    "- Secure tunnel connecting on-prem and cloud nodes\n"
    "- mTLS with per-tenant certificates\n"
    "- Works through firewalls (outbound HTTPS only)\n\n"
    "Check status: *\"Show twin node status\"* or *\"Check node sync status\"*"
)

_COMPARISON_NeuraNAC = None  # Now served from nac_knowledge.py (competitors_overview article)


# ─── Intent Definitions ──────────────────────────────────────────────────────

PRODUCT_KNOWLEDGE_INTENTS = [
    {
        "intent": "product_overview",
        "patterns": [
            r"what is (this|neuranac|the product|this product|this platform|this tool|this system|this application|this app)",
            r"(help me |help )?understand (this|neuranac|the product|this product|what this)",
            r"tell me (about|more about) (this|neuranac|the product|this product|yourself|this platform|this system)",
            r"explain (this|neuranac|the product|this product|this platform|what you are|what this is|this system)",
            r"describe (this|neuranac|the product|this product|this system)",
            r"(product|platform|tool|system|application) (overview|description|info|summary|details)",
            r"what does (this|neuranac|the product|it|this system|this platform) do",
            r"(introduce|introduction|intro)\b",
            r"what('s| is) neuranac\b",
            r"who are you",
            r"what are you",
            r"what (is|are) (this|the) (for|about|purpose)",
            r"(give me|provide|show).*(overview|summary|introduction|rundown)",
            r"(learn|know) (more )?(about|what) (this|neuranac)",
            r"(purpose|goal|objective) of (this|neuranac|the product)",
            r"what (should|do) i know about (this|neuranac)",
            r"brief(ing|ly| me| us)",
            r"how (does )?(this|neuranac|the product|this product|this platform|it) work",
            r"how (this|neuranac|the product|it) works",
        ],
        "knowledge": _PRODUCT_OVERVIEW,
        "description": "Product overview",
    },
    {
        "intent": "product_features",
        "patterns": [
            r"(what|show|list|tell).*(features|capabilities|can it do|can you do|functions|functionality)",
            r"what (all )?can (you|this|neuranac|it) (help|do|manage|handle|support)",
            r"(feature|capability) (list|overview|summary)",
            r"all features",
            r"what (does|can) (this|neuranac|it|the product) (offer|support|provide|include)",
            r"(what|which) (things|stuff|tasks|operations) can",
            r"(full|complete) list of",
            r"everything (you|this|neuranac|it) can do",
        ],
        "knowledge": _FEATURES_DETAIL,
        "description": "Product features",
    },
    {
        "intent": "product_architecture",
        "patterns": [
            r"(architecture|tech stack|technology)\b",
            r"how is (this|neuranac|it|the product|the system|the platform) (built|designed|architected|work)",
            r"(system|platform) (design|architecture|components|diagram)",
            r"what (services|microservices|components) (does|are)",
            r"(backend|infrastructure|stack) (overview|architecture|details)",
            r"(what|which) (technologies|languages|frameworks)",
            r"(under the hood|behind the scenes|internals)",
            r"(technical|system) (details|overview|design)",
        ],
        "knowledge": _ARCHITECTURE,
        "description": "Architecture overview",
    },
    {
        "intent": "product_howto",
        "patterns": [
            r"(how (do i|to)|getting) start",
            r"(where|how) (do i|should i|to) begin",
            r"(quick ?start|first steps|onboarding|tutorial)",
            r"how (do i|to) use (this|neuranac|the product|the dashboard|the ai)",
            r"(help|guide) me (get|getting) started",
            r"what (should|can|do) i do (first|next|now)",
            r"(walk|guide|take) me through",
            r"(step.by.step|walkthrough|how.to guide)",
            r"(new here|first time|just started|new user)",
            r"(where|how) (do|can|should) i (begin|go|navigate)",
        ],
        "knowledge": _HOW_TO_USE,
        "description": "Getting started guide",
    },
    {
        "intent": "ai_capabilities",
        "patterns": [
            r"what can (you|the ai|the agent|this agent|ai) (do|help)",
            r"(your|ai|agent) (capabilities|abilities|powers|skills)",
            r"how (can|do) (you|the ai) help",
            r"what (are|do) you (help|do|know|support)",
            r"show me what you can do",
            r"what('s| is) (possible|available)",
            r"what (questions|things|commands) can i (ask|say|do)",
            r"(help|assist|support) me (with|on|about)",
            r"(can you|could you|are you able to)",
            r"(what|how) (else )?can i (ask|do|try)",
        ],
        "knowledge": _AI_AGENT_HELP,
        "description": "AI Agent capabilities",
    },
    {
        "intent": "legacy_nac_migration_info",
        "patterns": [
            r"(how (do i|to|can i)|help me) migrat",
            r"(legacy|legacy.?nac) (migration|migrating|replacement|transition)",
            r"(replace|replacing|move|moving) (from )?legacy",
            r"(import|bring) (from|over from) legacy",
            r"switch(ing)? from (legacy |)nac",
            r"(transition|upgrade|move) (from|away from) (legacy |)nac",
            r"migrat.*(from|to|legacy|neuranac)",
        ],
        "knowledge": _NeuraNAC_MIGRATION,
        "description": "migration guide",
    },
    {
        "intent": "security_features",
        "patterns": [
            r"(security|zero.trust|threat) (features|capabilities|model|overview)",
            r"how (does|is|do) (security|authentication|authorization) (work|handled)",
            r"what (security|protection|defense) (does|do) (neuranac|this|you) (have|offer|provide)",
            r"(tell|explain).*(security|zero.trust|mfa|encryption)",
            r"(how|is).*(secure|safe|protected)",
            r"(security|threat|risk) (posture|model|approach)",
        ],
        "knowledge": _SECURITY_INFO,
        "description": "Security features overview",
    },
    {
        "intent": "twin_node_info",
        "patterns": [
            r"(what is|explain|tell me about) (twin|dual).?node",
            r"(how does|explain) (ha|high.availability|failover|replication|sync)",
            r"(twin|dual).?node (architecture|how|explain|info)",
            r"(on.prem|cloud|hybrid) (deployment|architecture|setup)",
        ],
        "knowledge": _TWIN_NODES,
        "description": "Twin-node architecture info",
    },
    {
        "intent": "legacy_nac_comparison",
        "patterns": [
            r"(compare|comparison|difference|vs|versus).*(legacy|competitor|other|alternative)",
            r"(legacy|competitor).*(compare|comparison|difference|vs|versus|better|worse)",
            r"why (use |choose )?(neuranac|this)( over| instead| vs| versus)? (legacy|competitor)",
            r"(advantages?|benefits?) (over|vs|compared to) (legacy|competitor)",
            r"(how|what).*(different|differ|unique|special|stand.?out|better).*(than|from)? ?(other|competitor|competition|alternative|them|the rest|it)",
            r"(how|what) (is|does) (this|neuranac|it) (differ|different|unique|special|stand.?out|better)",
            r"(competitor|competition|alternative|rival|other product|other tool|other solution)",
            r"(what|how) (sets|makes) (this|neuranac|it) (apart|different|unique|special)",
            r"(why|should).*(choose|pick|use|switch to|prefer) (this|neuranac)",
            r"(better|worse) than",
            r"(how|what).*(compare|stack up|measure up)",
        ],
        "knowledge": _COMPETITORS_CONTENT,
        "description": "NeuraNAC vs competitors comparison",
    },
    {
        "intent": "greeting",
        "patterns": [
            r"^(hi|hello|hey|greetings|good (morning|afternoon|evening)|howdy|sup|yo)\b",
            r"^(hi|hello|hey) (there|neuranac|agent|bot|ai)\b",
        ],
        "knowledge": (
            "Hello! I'm your **NeuraNAC AI Agent** — your intelligent assistant for network access control.\n\n"
            "I can help you **manage your entire network** through natural conversation. Try asking:\n"
            "- *\"What is this product?\"* — learn about NeuraNAC\n"
            "- *\"Show system status\"* — check service health\n"
            "- *\"List all endpoints\"* — view connected devices\n"
            "- *\"Create a policy named Guest WiFi\"* — configure access policies\n"
            "- *\"Why is user jdoe failing auth?\"* — troubleshoot issues\n\n"
            "What would you like to do?"
        ),
        "description": "Greeting response",
    },
    {
        "intent": "thanks",
        "patterns": [
            r"^(thanks?|thank you|thx|ty|cheers|appreciate)\b",
        ],
        "knowledge": (
            "You're welcome! Let me know if there's anything else I can help with. "
            "You can ask me about any NeuraNAC feature, create policies, view endpoints, "
            "troubleshoot authentication issues, or manage your network — all through chat."
        ),
        "description": "Thank you response",
    },
    {
        "intent": "policy_howto",
        "patterns": [
            r"how (do i|can i|to|should i) (configure|create|set ?up|add|build|define|write|make) (a |an |the )?(policy|policies|access rule|rule)",
            r"(configure|create|set ?up|build|define|write|manage) (a |an |the )?(policy|policies|access rule|rule)",
            r"(policy|policies|access rule) (configuration|creation|setup|management|how.?to|guide|tutorial)",
            r"(help|assist).*(policy|policies|access rule|rule)",
            r"(walk|guide|take) me.*(policy|policies)",
        ],
        "knowledge": (
            "### How to Configure Policies in NeuraNAC\n\n"
            "There are several ways to create and manage access policies:\n\n"
            "**Option 1: Natural Language (AI Agent)**\n"
            "Just describe what you want in plain English:\n"
            "- *\"Create a policy that allows employees on VLAN 100\"*\n"
            "- *\"Block guest users from accessing the server network\"*\n"
            "- *\"Allow IoT devices only on VLAN 200 with limited access\"*\n\n"
            "The AI will translate your request into actual policy rules.\n\n"
            "**Option 2: Dashboard UI**\n"
            "1. Switch to **Dashboard** mode (click the **Dash** toggle)\n"
            "2. Navigate to **Policies** in the sidebar\n"
            "3. Click **Create Policy** to start the policy builder\n"
            "4. Define conditions (user role, device type, location, time)\n"
            "5. Set the authorization result (VLAN, SGT, ACL, dACL)\n\n"
            "**Option 3: API**\n"
            "```\nPOST /api/v1/policies/\n{\n  \"name\": \"Corporate Access\",\n  \"match_type\": \"all\",\n  \"rules\": [...]\n}\n```\n\n"
            "**Policy Types Available:**\n"
            "- **Authentication policies** — who can connect\n"
            "- **Authorization policies** — what they can access\n"
            "- **Posture policies** — device compliance checks\n"
            "- **Segmentation policies** — SGT/TrustSec rules\n"
            "- **Guest/BYOD policies** — self-service device onboarding\n\n"
            "Try: *\"Create a policy named Guest WiFi\"* or *\"Go to policies\"*"
        ),
        "description": "Policy configuration guide",
    },
    {
        "intent": "device_howto",
        "patterns": [
            r"how (do i|can i|to|should i) (add|configure|register|onboard|set ?up) (a |an |the )?(device|switch|router|ap|access point|wlc|network device|nad)",
            r"(add|register|onboard|configure|manage) (a |an |the )?(network )?device",
            r"(device|switch|router|ap) (setup|configuration|registration|onboarding|how.?to)",
        ],
        "knowledge": (
            "### How to Add Network Devices in NeuraNAC\n\n"
            "**Option 1: AI Agent** (fastest)\n"
            "Just tell me:\n"
            "- *\"Add a Cisco switch at 10.0.0.1 with secret Cisco123\"*\n"
            "- *\"Register an access point at 192.168.1.10\"*\n\n"
            "**Option 2: Dashboard UI**\n"
            "1. Go to **Network Devices** in the sidebar\n"
            "2. Click **Add Device**\n"
            "3. Enter: IP address, RADIUS shared secret, device type, vendor\n"
            "4. Optionally configure SNMP credentials for monitoring\n\n"
            "**Option 3: Discovery**\n"
            "- Ask: *\"Discover devices on 10.0.0.0/24\"*\n"
            "- NeuraNAC will scan the subnet via SNMP and auto-register discovered devices\n\n"
            "**Supported Device Types:** switches, routers, wireless APs, WLCs, firewalls, VPN concentrators"
        ),
        "description": "Network device setup guide",
    },
    {
        "intent": "endpoint_howto",
        "patterns": [
            r"how (do i|can i|to) (manage|view|monitor|track|profile) (endpoints?|devices?|clients?)",
            r"(endpoint|device|client) (management|profiling|tracking|monitoring|visibility)",
            r"(what|which|how many) (endpoints?|devices?|clients?) (are|do|have)",
        ],
        "knowledge": (
            "### Endpoint Management in NeuraNAC\n\n"
            "NeuraNAC automatically tracks every device that authenticates to your network.\n\n"
            "**View Endpoints:**\n"
            "- Ask: *\"Show all endpoints\"* or *\"List endpoints\"*\n"
            "- Or go to **Endpoints** in Dashboard mode\n\n"
            "**Endpoint Profiling:**\n"
            "- NeuraNAC auto-profiles devices using DHCP fingerprinting, HTTP user-agent, MAC OUI, and SNMP data\n"
            "- Categories: workstation, phone, printer, IoT, camera, etc.\n\n"
            "**Monitoring:**\n"
            "- Real-time session tracking for connected endpoints\n"
            "- Historical authentication records\n"
            "- Anomaly detection flags unusual endpoint behavior\n\n"
            "Try: *\"Show all endpoints\"* or *\"Check for endpoint anomalies\"*"
        ),
        "description": "Endpoint management guide",
    },
    {
        "intent": "troubleshooting_howto",
        "patterns": [
            r"how (do i|can i|to) (troubleshoot|debug|diagnose|fix|resolve)",
            r"(something|it).*(not working|broken|failing|wrong|issue|problem|error)",
            r"(troubleshoot|debug|diagnose|fix) (guide|help|tips)",
            r"(auth|authentication|login|access).*(fail|issue|problem|error|denied|reject)",
            r"(user|device|endpoint).*(can't|cannot|unable|fail).*(connect|auth|access|login)",
            r"why (is|are|can't|isn't|does)",
        ],
        "knowledge": (
            "### Troubleshooting in NeuraNAC\n\n"
            "**AI-Powered Troubleshooting:**\n"
            "Describe the problem in natural language:\n"
            "- *\"Why is user jdoe failing authentication?\"*\n"
            "- *\"Why can't the printer connect to the network?\"*\n"
            "- *\"Show failed authentications in the last hour\"*\n\n"
            "**Manual Troubleshooting:**\n"
            "1. **Check RADIUS logs** — *\"Show RADIUS live log\"* or go to Diagnostics\n"
            "2. **Review sessions** — *\"Show failed sessions\"* to see rejected authentications\n"
            "3. **Check policies** — *\"Analyze policy drift\"* to find misconfigurations\n"
            "4. **System health** — *\"Show system status\"* to verify all services are running\n"
            "5. **Audit log** — *\"Show audit log\"* to see recent configuration changes\n\n"
            "**Common Issues:**\n"
            "- **Wrong shared secret** — RADIUS secret mismatch between device and NeuraNAC\n"
            "- **Certificate expired** — check with *\"List certificates\"*\n"
            "- **Policy too restrictive** — review with *\"Show policies\"*\n"
            "- **Device not registered** — add it with *\"Add switch 10.0.0.1\"*"
        ),
        "description": "Troubleshooting guide",
    },
]
