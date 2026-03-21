"""Comprehensive NAC domain knowledge base.

Provides deep knowledge across all Network Access Control topics so the AI
Agent can answer *any* NAC-related question — not just pattern-matched ones.

Each article has:
  - id: unique identifier
  - title: short title
  - keywords: list of words/stems that signal this topic
  - content: rich markdown answer
"""

# ─── NAC Knowledge Articles ──────────────────────────────────────────────────

NAC_KNOWLEDGE_ARTICLES = [
    # ── Core NAC Concepts ─────────────────────────────────────────────────
    {
        "id": "nac_overview",
        "title": "Network Access Control Overview",
        "keywords": [
            "nac", "network access control", "what is nac", "access control",
            "zero trust", "ztna", "network security", "admission control",
            "802.1x overview",
        ],
        "content": (
            "### What is Network Access Control (NAC)?\n\n"
            "**Network Access Control (NAC)** is a security approach that enforces policy on devices "
            "seeking to access network resources. It ensures that only authenticated, authorized, and "
            "compliant devices can connect to the network.\n\n"
            "**Core Functions of NAC:**\n"
            "1. **Authentication** — Verify the identity of users and devices (802.1X, MAB, WebAuth)\n"
            "2. **Authorization** — Determine what resources each identity can access (VLANs, ACLs, SGTs)\n"
            "3. **Accounting** — Log all access events for auditing and compliance\n"
            "4. **Posture Assessment** — Check device compliance (OS patches, antivirus, encryption)\n"
            "5. **Profiling** — Identify device types automatically (DHCP, HTTP, SNMP fingerprinting)\n"
            "6. **Guest/BYOD Management** — Self-service portals for visitor and personal device access\n"
            "7. **Segmentation** — Micro-segmentation via SGTs/TrustSec or VLANs\n\n"
            "**How NeuraNAC implements NAC:**\n"
            "NeuraNAC is a **cloud-native NAC platform** that provides all of these functions through a "
            "modern microservices architecture with an AI-powered interface. It replaces traditional "
            "on-prem NAC appliances like Legacy NAC, Aruba ClearPass, and Forescout with a scalable, "
            "intelligent solution.\n\n"
            "**Industry Standards:** IEEE 802.1X, RADIUS (RFC 2865), TACACS+ (RFC 8907), "
            "EAP (RFC 3748), TLS 1.3, SNMP, Syslog, NetFlow"
        ),
    },
    {
        "id": "radius_protocol",
        "title": "RADIUS Protocol",
        "keywords": [
            "radius", "radius server", "radius protocol", "aaa", "authentication server",
            "radius attributes", "radius packet", "access-request", "access-accept",
            "access-reject", "accounting-request", "rfc 2865", "shared secret",
            "radius port", "1812", "1813", "udp",
        ],
        "content": (
            "### RADIUS Protocol in NeuraNAC\n\n"
            "**RADIUS (Remote Authentication Dial-In User Service)** is the backbone protocol for NAC. "
            "NeuraNAC includes a **built-in high-performance RADIUS server** written in Go.\n\n"
            "**How RADIUS Works:**\n"
            "```\n"
            "Device → Switch (NAS) → RADIUS Server (NeuraNAC) → Identity Store\n"
            "  ①         ②              ③                      ④\n"
            "```\n"
            "1. Device connects to the network port\n"
            "2. Switch sends **Access-Request** to NeuraNAC RADIUS (UDP 1812)\n"
            "3. NeuraNAC authenticates against identity stores (local DB, LDAP, AD, SAML)\n"
            "4. NeuraNAC returns **Access-Accept** (with VLAN/SGT/ACL) or **Access-Reject**\n\n"
            "**Key RADIUS Concepts:**\n"
            "- **Shared Secret** — pre-shared key between switch and RADIUS server for packet signing\n"
            "- **RADIUS Attributes** — key-value pairs in packets (e.g., User-Name, NAS-IP, Tunnel-Type)\n"
            "- **Vendor-Specific Attributes (VSAs)** — vendor extensions (Cisco av-pair, etc.)\n"
            "- **CoA (Change of Authorization)** — push policy changes to switches mid-session (RFC 5176)\n"
            "- **Accounting** — session start/stop/interim tracking (UDP 1813)\n\n"
            "**NeuraNAC RADIUS Features:**\n"
            "- High-performance Go implementation handling 10K+ auth/sec\n"
            "- EAP support: EAP-TLS, PEAP, EAP-FAST, EAP-TTLS\n"
            "- Inline AI enrichment: real-time risk scoring and anomaly detection per auth\n"
            "- RADIUS live log with filtering and search\n"
            "- CoA support for dynamic VLAN/SGT reassignment\n\n"
            "**NeuraNAC Ports:** RADIUS auth (1812/UDP), RADIUS acct (1813/UDP)\n\n"
            "Try: *\"Show RADIUS live log\"* or *\"Show failed authentications\"*"
        ),
    },
    {
        "id": "dot1x",
        "title": "802.1X Authentication",
        "keywords": [
            "802.1x", "dot1x", "8021x", "eap", "supplicant", "authenticator",
            "eapol", "port-based", "wired authentication", "wireless authentication",
            "eap-tls", "peap", "eap-fast", "eap-ttls", "mschapv2",
            "certificate based", "certificate authentication",
        ],
        "content": (
            "### 802.1X Authentication\n\n"
            "**802.1X** is the IEEE standard for port-based network access control. It's the most "
            "secure method for authenticating devices to wired and wireless networks.\n\n"
            "**Three Roles:**\n"
            "- **Supplicant** — the client device (laptop, phone, IoT)\n"
            "- **Authenticator** — the network switch or wireless AP\n"
            "- **Authentication Server** — NeuraNAC RADIUS server\n\n"
            "**Authentication Flow:**\n"
            "```\n"
            "Supplicant ←EAPOL→ Switch ←RADIUS→ NeuraNAC\n"
            "    ①                  ②              ③\n"
            "1. Device connects → port is blocked\n"
            "2. EAP exchange begins over EAPOL (EAP over LAN)\n"
            "3. Switch relays EAP to NeuraNAC via RADIUS\n"
            "4. NeuraNAC validates credentials → returns Access-Accept + VLAN/SGT\n"
            "5. Switch opens port with assigned policy\n"
            "```\n\n"
            "**EAP Methods Supported by NeuraNAC:**\n"
            "| Method | Credentials | Security Level |\n"
            "|---|---|---|\n"
            "| **EAP-TLS** | Client + server certificates | Highest (mutual TLS) |\n"
            "| **PEAP (MSCHAPv2)** | Username/password + server cert | High |\n"
            "| **EAP-FAST** | PAC + username/password | High |\n"
            "| **EAP-TTLS** | Server cert + inner method | High |\n\n"
            "**When to use 802.1X:**\n"
            "- Corporate laptops and desktops (wired)\n"
            "- Corporate wireless (WPA2/WPA3-Enterprise)\n"
            "- Any device with a supplicant\n\n"
            "**When to use MAB instead:** headless/IoT devices without a supplicant (printers, cameras, sensors)"
        ),
    },
    {
        "id": "mab",
        "title": "MAC Authentication Bypass (MAB)",
        "keywords": [
            "mab", "mac authentication", "mac bypass", "mac address", "mac-based",
            "headless device", "iot authentication", "printer", "camera", "sensor",
            "no supplicant",
        ],
        "content": (
            "### MAC Authentication Bypass (MAB)\n\n"
            "**MAB** is used to authenticate devices that don't support 802.1X — like printers, "
            "IP cameras, IoT sensors, medical devices, and legacy equipment.\n\n"
            "**How MAB Works:**\n"
            "1. Device connects to the switch port\n"
            "2. Switch waits for 802.1X (no response — device has no supplicant)\n"
            "3. Switch falls back to MAB — sends the device's **MAC address** as the username/password\n"
            "4. NeuraNAC looks up the MAC in its endpoint database\n"
            "5. If the MAC is known and authorized → Access-Accept with appropriate VLAN/SGT\n\n"
            "**MAB Best Practices:**\n"
            "- Maintain an **endpoint database** of known MAC addresses\n"
            "- Use **profiling** to auto-categorize unknown devices\n"
            "- Assign IoT devices to **restricted VLANs** with limited access\n"
            "- Combine with **SGTs** for microsegmentation\n"
            "- Enable **anomaly detection** to flag MAC spoofing\n\n"
            "**NeuraNAC MAB Features:**\n"
            "- Automatic MAC OUI vendor lookup (500+ vendors)\n"
            "- AI-based device profiling and categorization\n"
            "- Dynamic VLAN assignment based on device type\n"
            "- MAC spoofing detection via behavioral analysis\n\n"
            "Try: *\"Show all endpoints\"* or *\"Profile the last connected endpoint\"*"
        ),
    },
    {
        "id": "tacacs",
        "title": "TACACS+ Protocol",
        "keywords": [
            "tacacs", "tacacs+", "device administration", "network admin",
            "command authorization", "privilege level", "device management",
            "switch admin", "router admin", "cli access",
        ],
        "content": (
            "### TACACS+ in NeuraNAC\n\n"
            "**TACACS+ (Terminal Access Controller Access-Control System Plus)** is used for "
            "**device administration** — controlling who can manage network devices (switches, "
            "routers, firewalls) and what commands they can execute.\n\n"
            "**TACACS+ vs RADIUS:**\n"
            "| Feature | TACACS+ | RADIUS |\n"
            "|---|---|---|\n"
            "| Purpose | Device admin | Network access |\n"
            "| Transport | TCP (port 49) | UDP (1812/1813) |\n"
            "| Encryption | Full packet | Password only |\n"
            "| AAA Separation | Yes | No |\n"
            "| Command Auth | Yes | No |\n\n"
            "**Use Cases:**\n"
            "- SSH/Telnet access to switches and routers\n"
            "- Per-command authorization (allow `show` but block `config`)\n"
            "- Privilege level assignment (level 1 vs level 15)\n"
            "- Audit trail of all admin commands\n\n"
            "**NeuraNAC supports both RADIUS and TACACS+** for complete AAA coverage."
        ),
    },
    {
        "id": "posture",
        "title": "Posture Assessment & Compliance",
        "keywords": [
            "posture", "compliance", "health check", "device compliance",
            "endpoint compliance", "antivirus", "patch", "os version",
            "disk encryption", "firewall enabled", "agent", "agentless",
            "remediation", "quarantine",
        ],
        "content": (
            "### Posture Assessment & Compliance\n\n"
            "**Posture assessment** verifies that a device meets your security requirements "
            "before granting full network access.\n\n"
            "**What Posture Checks:**\n"
            "- **OS version** — is the device running a supported/patched OS?\n"
            "- **Antivirus** — is AV installed, running, and up-to-date?\n"
            "- **Firewall** — is the host firewall enabled?\n"
            "- **Disk encryption** — is FileVault/BitLocker enabled?\n"
            "- **Patch level** — are critical security patches applied?\n"
            "- **Required software** — is the corporate VPN/MDM agent installed?\n"
            "- **Prohibited software** — is any banned software running?\n\n"
            "**Posture Flow:**\n"
            "```\n"
            "1. Device authenticates via 802.1X → gets LIMITED access\n"
            "2. Posture agent checks device compliance\n"
            "3. If compliant → CoA → FULL access\n"
            "4. If non-compliant → QUARANTINE VLAN → remediation portal\n"
            "```\n\n"
            "**NeuraNAC Posture Features:**\n"
            "- Configurable compliance rules per OS type\n"
            "- Grace periods for remediation\n"
            "- Auto-remediation links\n"
            "- Periodic re-assessment\n\n"
            "Try: *\"List posture policies\"* or *\"Create a posture policy\"*"
        ),
    },
    {
        "id": "profiling",
        "title": "Endpoint Profiling",
        "keywords": [
            "profiling", "endpoint profiling", "device profiling", "fingerprinting",
            "dhcp fingerprint", "http user-agent", "mac oui", "cdp", "lldp",
            "device type", "classify", "categorize", "identify device",
            "byod", "iot profiling",
        ],
        "content": (
            "### Endpoint Profiling\n\n"
            "**Profiling** automatically identifies and categorizes devices connecting to your "
            "network — without requiring any agent on the device.\n\n"
            "**Profiling Data Sources:**\n"
            "| Source | What it reveals |\n"
            "|---|---|\n"
            "| **DHCP fingerprint** | OS type, device class |\n"
            "| **HTTP User-Agent** | Browser, OS, device model |\n"
            "| **MAC OUI** | Manufacturer (Apple, Dell, HP, etc.) |\n"
            "| **CDP/LLDP** | Cisco/network device info |\n"
            "| **SNMP** | Detailed device inventory |\n"
            "| **NMAP scan** | Open ports, services, OS |\n"
            "| **NetFlow** | Traffic behavior patterns |\n\n"
            "**Device Categories:**\n"
            "Workstation, Laptop, Mobile Phone, Tablet, Printer, IP Camera, IoT Sensor, "
            "VoIP Phone, Medical Device, Smart TV, Gaming Console, Network Device, Server, Unknown\n\n"
            "**Why Profiling Matters:**\n"
            "- **Policy enforcement** — different access rules per device type\n"
            "- **BYOD detection** — identify personal vs. corporate devices\n"
            "- **IoT visibility** — discover shadow IoT on the network\n"
            "- **Anomaly detection** — flag when a device type changes unexpectedly\n\n"
            "**NeuraNAC profiling** combines multiple data sources with AI/ML for 95%+ accuracy.\n\n"
            "Try: *\"Show all endpoints\"* or *\"Check for endpoint anomalies\"*"
        ),
    },
    {
        "id": "segmentation",
        "title": "Network Segmentation & TrustSec",
        "keywords": [
            "segmentation", "microsegmentation", "sgt", "security group tag",
            "trustsec", "sgacl", "vlan", "vlan assignment", "dynamic vlan",
            "network segment", "isolation", "lateral movement", "east-west",
            "software-defined segmentation",
        ],
        "content": (
            "### Network Segmentation & TrustSec\n\n"
            "**Segmentation** limits lateral movement by dividing the network into zones with "
            "controlled access between them.\n\n"
            "**Two Approaches:**\n\n"
            "**1. VLAN-Based Segmentation (Traditional)**\n"
            "- Assign devices to VLANs based on identity/role\n"
            "- Use ACLs between VLANs to control traffic\n"
            "- Simple but doesn't scale well\n\n"
            "**2. SGT/TrustSec (Modern — Software-Defined)**\n"
            "- Tag every packet with a **Security Group Tag (SGT)**\n"
            "- Enforcement via **SGACLs** (Security Group ACLs) at every switch\n"
            "- Identity-based, topology-independent\n"
            "- Scales to millions of flows\n\n"
            "**SGT Assignment in NeuraNAC:**\n"
            "```\n"
            "User authenticates → NeuraNAC assigns SGT (e.g., SGT=10 'Employees')\n"
            "→ Switch tags all traffic with SGT=10\n"
            "→ SGACL matrix controls access between SGT groups\n"
            "```\n\n"
            "**Example SGT Matrix:**\n"
            "| Source SGT | Dest SGT | Policy |\n"
            "|---|---|---|\n"
            "| Employees (10) | Servers (20) | Permit |\n"
            "| Guests (30) | Servers (20) | Deny |\n"
            "| IoT (40) | Internet (50) | Permit |\n"
            "| IoT (40) | Servers (20) | Deny |\n\n"
            "Try: *\"List security group tags\"* or *\"Create a new SGT named IoT-Devices with tag 100\"*"
        ),
    },
    {
        "id": "guest_byod",
        "title": "Guest & BYOD Access",
        "keywords": [
            "guest", "guest access", "guest portal", "captive portal",
            "byod", "bring your own device", "personal device", "visitor",
            "self-registration", "sponsor", "onboarding", "device registration",
            "hotspot", "web authentication", "webauth",
        ],
        "content": (
            "### Guest & BYOD Access Management\n\n"
            "**Guest Access** provides controlled network access for visitors, contractors, "
            "and temporary users through self-service portals.\n\n"
            "**Guest Portal Types:**\n"
            "- **Hotspot** — click-through terms acceptance, no credentials needed\n"
            "- **Self-Registration** — guest fills out a form, gets temporary credentials\n"
            "- **Sponsored** — employee creates a guest account and shares credentials\n"
            "- **Social Login** — authenticate via Google, Microsoft, etc.\n\n"
            "**Guest Flow:**\n"
            "```\n"
            "1. Guest connects to WiFi → redirected to captive portal\n"
            "2. Guest authenticates (self-reg, sponsor, social)\n"
            "3. NeuraNAC assigns Guest VLAN/SGT with restricted access\n"
            "4. Guest gets Internet + limited internal access\n"
            "5. Credentials expire after time limit\n"
            "```\n\n"
            "**BYOD (Bring Your Own Device):**\n"
            "- Employee registers their personal device through a portal\n"
            "- Device gets a certificate for future 802.1X authentication\n"
            "- BYOD devices get a different access level than corporate devices\n"
            "- MDM integration for advanced compliance checking\n\n"
            "**NeuraNAC Features:**\n"
            "- Customizable portal branding\n"
            "- Time-limited guest accounts (hours/days)\n"
            "- BYOD certificate enrollment (SCEP)\n"
            "- SMS/email notification for sponsored guests"
        ),
    },
    {
        "id": "certificates",
        "title": "Certificates & PKI",
        "keywords": [
            "certificate", "pki", "ca", "certificate authority", "x509",
            "scep", "enrollment", "tls", "ssl", "mutual tls", "mtls",
            "csr", "private key", "public key", "certificate lifecycle",
            "expiry", "renewal", "revocation", "crl", "ocsp",
        ],
        "content": (
            "### Certificate Management & PKI\n\n"
            "Certificates are fundamental to secure NAC — they enable **mutual authentication** "
            "between devices, servers, and network infrastructure.\n\n"
            "**Certificate Uses in NAC:**\n"
            "- **EAP-TLS** — strongest 802.1X authentication method (client cert + server cert)\n"
            "- **RADIUS server cert** — switches validate NeuraNAC's identity\n"
            "- **BYOD enrollment** — provision certs to personal devices\n"
            "- **Inter-service mTLS** — secure communication between NeuraNAC microservices\n\n"
            "**NeuraNAC PKI Features:**\n"
            "- **Internal Certificate Authority** — issue and manage certificates without external CA\n"
            "- **SCEP Enrollment** — automatic certificate provisioning for devices\n"
            "- **Certificate Lifecycle** — track issuance, expiry, renewal, revocation\n"
            "- **CRL/OCSP** — real-time certificate revocation checking\n"
            "- **Auto-renewal** — alerts and automated renewal before expiry\n\n"
            "**Certificate Hierarchy:**\n"
            "```\n"
            "Root CA (NeuraNAC)\n"
            " ├── Intermediate CA\n"
            " │    ├── RADIUS Server Certificate\n"
            " │    ├── Admin Portal Certificate\n"
            " │    └── Inter-service mTLS Certificates\n"
            " └── Endpoint CA\n"
            "      ├── Corporate Device Certificates\n"
            "      └── BYOD Device Certificates\n"
            "```\n\n"
            "Try: *\"List certificates\"* or *\"Show certificate authorities\"*"
        ),
    },
    {
        "id": "identity_sources",
        "title": "Identity Sources",
        "keywords": [
            "identity", "identity source", "ldap", "active directory", "ad",
            "saml", "oauth", "sso", "single sign-on", "directory",
            "user store", "identity provider", "idp", "radius proxy",
            "external authentication", "local users",
        ],
        "content": (
            "### Identity Sources\n\n"
            "NeuraNAC authenticates users against multiple **identity sources** — the databases "
            "or directories that store user credentials.\n\n"
            "**Supported Identity Sources:**\n"
            "| Source | Protocol | Use Case |\n"
            "|---|---|---|\n"
            "| **Local Database** | Internal | Small deployments, admin accounts |\n"
            "| **Active Directory** | LDAP/Kerberos | Enterprise Windows environments |\n"
            "| **LDAP** | LDAP v3 | Generic directory (OpenLDAP, etc.) |\n"
            "| **SAML 2.0** | SAML/SSO | Cloud identity (Okta, Azure AD, Ping) |\n"
            "| **OAuth 2.0 / OIDC** | OAuth | Modern identity federation |\n"
            "| **RADIUS Proxy** | RADIUS | Chain to external RADIUS servers |\n"
            "| **Certificate** | X.509 | Certificate-based auth (EAP-TLS) |\n"
            "| **Token/MFA** | TOTP/RADIUS | Two-factor authentication |\n\n"
            "**Identity Source Sequence:**\n"
            "NeuraNAC evaluates identity sources in order — if the first source rejects or is unavailable, "
            "it tries the next in the sequence. This provides resilience and flexibility.\n\n"
            "**Group/Role Mapping:**\n"
            "- Map AD/LDAP groups to NeuraNAC roles for automatic policy assignment\n"
            "- Example: AD group `Domain Users` → NeuraNAC role `employee` → VLAN 100"
        ),
    },
    {
        "id": "shadow_ai",
        "title": "Shadow AI Detection",
        "keywords": [
            "shadow ai", "unauthorized ai", "chatgpt", "openai", "copilot",
            "gemini", "claude", "ai detection", "ai services", "generative ai",
            "data leak", "data exfiltration", "ai governance", "ai policy",
            "block ai", "ai traffic",
        ],
        "content": (
            "### Shadow AI Detection\n\n"
            "**Shadow AI** refers to unauthorized use of AI/ML services on your corporate network — "
            "employees using ChatGPT, Copilot, Claude, Gemini, etc. without IT approval, potentially "
            "leaking sensitive data.\n\n"
            "**NeuraNAC Shadow AI Capabilities:**\n"
            "- **Detection** — identifies traffic to 50+ known AI services via DNS, TLS SNI, and JA3/JA4 fingerprints\n"
            "- **Classification** — categorizes AI services (LLM, code gen, image gen, translation)\n"
            "- **Monitoring** — tracks usage volume, users, and departments\n"
            "- **Policy Enforcement** — block, allow, or rate-limit AI service access\n"
            "- **Alerting** — real-time alerts when new AI services are detected\n\n"
            "**Known AI Services Tracked:**\n"
            "ChatGPT/OpenAI, Microsoft Copilot, GitHub Copilot, Google Gemini/Bard, "
            "Anthropic Claude, Midjourney, Stable Diffusion, Hugging Face, Jasper AI, "
            "Perplexity, DeepSeek, and 40+ more.\n\n"
            "**Example Policies:**\n"
            "- *\"Block all traffic to OpenAI\"*\n"
            "- *\"Allow Copilot but block ChatGPT\"*\n"
            "- *\"Alert when any new AI service is detected\"*\n\n"
            "Try: *\"Show shadow AI detections\"* or *\"List known AI services\"*"
        ),
    },
    {
        "id": "risk_scoring",
        "title": "Adaptive Risk Scoring",
        "keywords": [
            "risk score", "risk scoring", "adaptive risk", "risk assessment",
            "threat score", "risk level", "risk threshold", "behavioral",
            "anomaly score", "machine learning risk", "risk-based access",
        ],
        "content": (
            "### Adaptive Risk Scoring\n\n"
            "NeuraNAC assigns a **real-time risk score** to every session and endpoint using "
            "machine learning, then adjusts network access dynamically based on risk level.\n\n"
            "**Risk Factors:**\n"
            "- **Device posture** — is the device compliant? (OS, AV, patches)\n"
            "- **Authentication method** — cert-based is lower risk than password\n"
            "- **Location anomaly** — is the user connecting from an unusual location?\n"
            "- **Time anomaly** — is this outside normal working hours?\n"
            "- **Behavioral baseline** — does this session match the user's normal pattern?\n"
            "- **TLS fingerprint** — does the client's TLS match known good signatures?\n"
            "- **Failed attempts** — recent authentication failures\n\n"
            "**Risk-Based Access:**\n"
            "| Risk Level | Score | Action |\n"
            "|---|---|---|\n"
            "| Low | 0-30 | Full access |\n"
            "| Medium | 31-60 | Limited access + monitoring |\n"
            "| High | 61-80 | Restricted VLAN + alert |\n"
            "| Critical | 81-100 | Quarantine + incident |\n\n"
            "**Adaptive Learning:**\n"
            "- Analysts can provide feedback (\"this was a false positive\")\n"
            "- Model adjusts thresholds based on feedback\n"
            "- Continuous improvement over time\n\n"
            "Try: *\"Compute risk score for active sessions\"* or *\"Show risk thresholds\"*"
        ),
    },
    {
        "id": "tls_fingerprint",
        "title": "TLS Fingerprinting (JA3/JA4)",
        "keywords": [
            "tls fingerprint", "ja3", "ja4", "ssl fingerprint", "client hello",
            "tls signature", "malware detection", "c2 detection", "command and control",
            "encrypted traffic analysis",
        ],
        "content": (
            "### TLS Fingerprinting (JA3/JA4)\n\n"
            "**TLS fingerprinting** identifies applications and potential threats by analyzing the "
            "unique characteristics of their TLS Client Hello packets — even in encrypted traffic.\n\n"
            "**JA3** — hashes the TLS Client Hello fields (cipher suites, extensions, curves) "
            "into a 32-character MD5 fingerprint.\n\n"
            "**JA4** — next-generation fingerprint with protocol version, SNI, ALPN, cipher count "
            "for better accuracy and fewer collisions.\n\n"
            "**NeuraNAC TLS Features:**\n"
            "- **16+ known JA3 signatures** — Chrome, Firefox, Safari, curl, Python, Go, malware\n"
            "- **3+ JA4 signatures** — enhanced detection accuracy\n"
            "- **Custom signatures** — define your own fingerprints\n"
            "- **Real-time matching** — inline during RADIUS authentication\n"
            "- **Threat detection** — flag known malware/C2 TLS signatures\n\n"
            "**Use Cases:**\n"
            "- Detect malware command-and-control traffic\n"
            "- Identify unauthorized applications\n"
            "- Validate that corporate devices use expected TLS stacks\n"
            "- Detect TLS downgrade attacks\n\n"
            "Try: *\"Show TLS detections\"* or *\"Analyze JA3 fingerprint\"*"
        ),
    },
    {
        "id": "coa",
        "title": "Change of Authorization (CoA)",
        "keywords": [
            "coa", "change of authorization", "disconnect", "reauthenticate",
            "bounce port", "dynamic authorization", "rfc 5176", "session update",
            "push policy", "re-evaluate",
        ],
        "content": (
            "### Change of Authorization (CoA)\n\n"
            "**CoA (RFC 5176)** allows NeuraNAC to dynamically update a device's network access "
            "**after** it has already authenticated — without requiring the user to disconnect.\n\n"
            "**CoA Actions:**\n"
            "- **Session Terminate** — disconnect the device\n"
            "- **Port Bounce** — briefly disable/re-enable the port (triggers re-auth)\n"
            "- **Reauthenticate** — force the device to re-authenticate\n"
            "- **Policy Push** — change VLAN, ACL, or SGT assignment in real-time\n\n"
            "**When CoA is Used:**\n"
            "- Posture assessment completes → upgrade from limited to full access\n"
            "- Admin changes a policy → push updated access to all affected sessions\n"
            "- Risk score increases → move device to quarantine VLAN\n"
            "- Employee termination → immediately disconnect all their sessions\n\n"
            "**Example:**\n"
            "```\n"
            "1. Laptop authenticates → gets VLAN 10 (limited)\n"
            "2. Posture agent reports: compliant ✓\n"
            "3. NeuraNAC sends CoA to switch → VLAN changes to 100 (full)\n"
            "4. User gets full access without reconnecting\n"
            "```"
        ),
    },
    {
        "id": "playbooks",
        "title": "Automated Playbooks",
        "keywords": [
            "playbook", "automation", "incident response", "automated response",
            "workflow", "remediation", "auto-remediate", "runbook",
            "orchestration", "soar",
        ],
        "content": (
            "### Automated Playbooks\n\n"
            "**Playbooks** are pre-defined automated workflows that respond to security events "
            "without manual intervention.\n\n"
            "**Built-in Playbooks:**\n"
            "1. **Quarantine Endpoint** — isolate a compromised device to a quarantine VLAN\n"
            "2. **Block Shadow AI** — automatically block newly detected AI services\n"
            "3. **Revoke Access** — terminate sessions for a user across all devices\n"
            "4. **Posture Remediation** — guide non-compliant devices to fix issues\n"
            "5. **Incident Escalation** — create tickets and notify SecOps\n"
            "6. **Certificate Renewal** — auto-renew expiring certificates\n\n"
            "**Custom Playbooks:**\n"
            "Define your own playbooks with triggers, conditions, and actions:\n"
            "```\n"
            "Trigger: Risk score > 80\n"
            "Condition: Device is IoT\n"
            "Actions:\n"
            "  1. Move to quarantine VLAN\n"
            "  2. Send alert to SOC\n"
            "  3. Create incident ticket\n"
            "```\n\n"
            "Try: *\"List all playbooks\"* or *\"Show playbook executions\"*"
        ),
    },
    {
        "id": "deployment_modes",
        "title": "Deployment Modes",
        "keywords": [
            "deployment", "deploy", "install", "setup", "on-premise", "on-prem",
            "cloud", "hybrid", "saas", "multi-tenant", "single tenant",
            "docker", "kubernetes", "helm", "containerized",
        ],
        "content": (
            "### NeuraNAC Deployment Modes\n\n"
            "NeuraNAC supports multiple deployment models to fit different environments:\n\n"
            "**1. Standalone (On-Prem)**\n"
            "- All services run on a single server/VM\n"
            "- Best for: small to medium deployments, testing, labs\n"
            "- Deploy: `docker-compose up`\n\n"
            "**2. Hybrid (On-Prem + Cloud)**\n"
            "- **On-prem node** handles RADIUS (low latency)\n"
            "- **Cloud node** provides management UI and AI\n"
            "- Connected via **NeuraNAC Bridge** (mTLS tunnel)\n"
            "- Real-time sync between nodes\n\n"
            "**3. Multi-Tenant SaaS**\n"
            "- Fully managed cloud deployment\n"
            "- Row-level tenant isolation\n"
            "- Per-tenant encryption keys and certificates\n"
            "- Horizontal scaling via Kubernetes\n\n"
            "**4. Kubernetes (Production)**\n"
            "- Helm charts for all services\n"
            "- Auto-scaling, rolling updates\n"
            "- Network policies for pod isolation\n"
            "- Service mesh ready\n\n"
            "**Infrastructure Requirements:**\n"
            "- Docker & Docker Compose (dev/small)\n"
            "- Kubernetes 1.28+ (production)\n"
            "- PostgreSQL 16+, Redis 7+, NATS 2.10+\n"
            "- 4 vCPU, 8GB RAM minimum (standalone)"
        ),
    },
    # ── Competitor Comparisons ────────────────────────────────────────────
    {
        "id": "competitors_overview",
        "title": "NeuraNAC vs NAC Competitors",
        "keywords": [
            "competitor", "competition", "alternative", "rival", "versus",
            "compare", "comparison", "different", "differ", "better", "worse",
            "stand out", "unique", "advantage", "why choose", "why use",
            "other nac", "other product", "other solution", "market",
            "clearpass", "forescout", "portnox", "fortinac", "securew2",
            "aruba", "palo alto", "juniper",
        ],
        "content": (
            "### NeuraNAC vs NAC Competitors\n\n"
            "**Major NAC solutions in the market:**\n\n"
            "| Feature | NeuraNAC | Legacy NAC | Aruba ClearPass | Forescout | Portnox | FortiNAC |\n"
            "|---|---|---|---|---|---|---|\n"
            "| **Architecture** | Cloud-native microservices | On-prem VMs | On-prem appliance | On-prem appliance | Cloud-native | On-prem VM |\n"
            "| **AI/ML Security** | Shadow AI, risk scoring, anomaly, TLS fingerprinting | Limited (Event Stream analytics) | Basic profiling ML | Device classification | Basic risk | None |\n"
            "| **Natural Language Interface** | Full AI chat for all operations | None | None | None | None | None |\n"
            "| **802.1X / RADIUS** | Built-in (Go, 10K+ auth/s) | Built-in | Built-in | Agentless (no RADIUS) | Cloud RADIUS | Built-in |\n"
            "| **Scalability** | Horizontal (K8s) | Vertical (bigger VMs) | Vertical | Horizontal (segments) | Cloud auto-scale | Vertical |\n"
            "| **HA Model** | Active-Active twin-nodes | Active/Standby | Active/Standby | Active/Passive | Cloud HA | Active/Passive |\n"
            "| **Multi-Tenancy** | Row-level isolation | No | No | No | Yes | No |\n"
            "| **API** | Full REST (200+ endpoints) | ERS (limited) | REST API | REST API | REST API | Limited |\n"
            "| **Migration** | Zero-downtime wizard | N/A | Manual | Manual | Manual | Manual |\n"
            "| **Pricing** | Per-device SaaS tiers | Per-device + VM license | Per-device + appliance | Per-device + appliance | Per-device SaaS | Per-device + VM |\n"
            "| **Open Standards** | Full (RADIUS, TACACS+, SAML, OIDC) | Proprietary extensions | Standard + Aruba-specific | Proprietary agents | Standard | FortiGate-centric |\n\n"
            "---\n\n"
            "### Detailed Competitor Breakdown\n\n"
            "**Legacy NAC** (most direct competitor)\n"
            "- Market leader with largest install base\n"
            "- Heavyweight, complex, expensive — requires dedicated VMs and Cisco expertise\n"
            "- No AI capabilities, no natural language interface\n"
            "- NeuraNAC provides a zero-downtime migration path from NeuraNAC\n\n"
            "**Aruba ClearPass** (HPE/Aruba)\n"
            "- Strong in Aruba wireless environments\n"
            "- Good profiling and guest management\n"
            "- Limited to Aruba ecosystem, less flexible API\n"
            "- No AI security features, no cloud-native option\n\n"
            "**Forescout** (agentless NAC)\n"
            "- Unique agentless approach — no 802.1X required\n"
            "- Great device visibility and classification\n"
            "- Not a RADIUS server — relies on integration with switches\n"
            "- Good for OT/IoT environments\n"
            "- No AI chat interface\n\n"
            "**Portnox** (cloud-native NAC)\n"
            "- Closest architecture to NeuraNAC (cloud-native)\n"
            "- Simple, SaaS-delivered NAC\n"
            "- Less feature-rich than NeuraNAC (no AI security, limited segmentation)\n"
            "- Good for small/medium businesses\n\n"
            "**FortiNAC** (Fortinet)\n"
            "- Part of Fortinet Security Fabric\n"
            "- Best when used with FortiGate firewalls\n"
            "- Limited standalone NAC capabilities\n"
            "- No AI features, basic automation\n\n"
            "**SecureW2** (cloud RADIUS)\n"
            "- Cloud-managed RADIUS as a service\n"
            "- Great for cloud-only environments\n"
            "- Limited NAC features — primarily a RADIUS service\n"
            "- No posture, limited segmentation\n\n"
            "---\n\n"
            "### Why Choose NeuraNAC?\n\n"
            "1. **Only NAC with AI-powered chat interface** — manage your network with natural language\n"
            "2. **Shadow AI detection** — no other NAC vendor offers this\n"
            "3. **Cloud-native + on-prem** — flexible deployment (Portnox is cloud-only, NeuraNAC is on-prem-only)\n"
            "4. **Zero-downtime migration** — automated wizard, not manual XML imports\n"
            "5. **Modern developer experience** — full REST API, Helm charts, Docker, open standards\n"
            "6. **Active-Active HA** — no manual failover, automatic sync between nodes"
        ),
    },
    # ── Troubleshooting Knowledge ─────────────────────────────────────────
    {
        "id": "auth_failures",
        "title": "Authentication Failure Troubleshooting",
        "keywords": [
            "auth fail", "authentication failure", "access reject", "login fail",
            "cannot connect", "can't connect", "unable to connect", "denied",
            "rejected", "eap failure", "eap timeout", "wrong password",
            "credential", "invalid certificate",
        ],
        "content": (
            "### Troubleshooting Authentication Failures\n\n"
            "**Common Causes & Fixes:**\n\n"
            "**1. Wrong RADIUS Shared Secret**\n"
            "- Symptom: No response from RADIUS, \"Message-Authenticator invalid\"\n"
            "- Fix: Verify shared secret matches on both switch and NeuraNAC network device config\n\n"
            "**2. Certificate Issues (EAP-TLS)**\n"
            "- Symptom: EAP negotiation fails, \"TLS handshake failure\"\n"
            "- Fix: Check certificate validity, chain trust, expiry date\n"
            "- Command: *\"List certificates\"* to see expiry dates\n\n"
            "**3. User Not Found**\n"
            "- Symptom: Access-Reject, \"User not found in identity source\"\n"
            "- Fix: Verify user exists in the configured identity source (local DB, AD, LDAP)\n\n"
            "**4. Wrong Password**\n"
            "- Symptom: Access-Reject, \"Invalid credentials\"\n"
            "- Fix: Reset password, check CAPS lock, verify identity source\n\n"
            "**5. Policy Mismatch**\n"
            "- Symptom: User authenticates but gets wrong VLAN or no access\n"
            "- Fix: Review policy conditions — *\"Show policies\"* and check match order\n\n"
            "**6. Device Not Registered**\n"
            "- Symptom: Access-Reject for MAB, \"Unknown MAC address\"\n"
            "- Fix: Register the device — *\"Add endpoint AA:BB:CC:DD:EE:FF\"*\n\n"
            "**7. EAP Timeout**\n"
            "- Symptom: Supplicant times out during EAP exchange\n"
            "- Fix: Check network path between switch and NeuraNAC, verify port 1812/UDP is open\n\n"
            "**Diagnostic Commands:**\n"
            "- *\"Show RADIUS live log\"* — see real-time auth attempts\n"
            "- *\"Show failed sessions\"* — see recent rejections\n"
            "- *\"Why is user jdoe failing?\"* — AI-assisted diagnosis"
        ),
    },
    {
        "id": "capacity_planning",
        "title": "Capacity Planning & Performance",
        "keywords": [
            "capacity", "performance", "scale", "scaling", "throughput",
            "limit", "maximum", "concurrent",
            "sessions per second", "auth per second", "sizing",
        ],
        "content": (
            "### Capacity Planning & Performance\n\n"
            "**NeuraNAC Performance Benchmarks (Standalone):**\n"
            "| Metric | Value |\n"
            "|---|---|\n"
            "| RADIUS auth throughput | 10,000+ auth/sec |\n"
            "| Concurrent sessions | 500,000+ |\n"
            "| Endpoints in database | 1,000,000+ |\n"
            "| Policies evaluated | Sub-millisecond |\n"
            "| API response time | <50ms (p95) |\n\n"
            "**Scaling Options:**\n"
            "- **Vertical** — add more CPU/RAM to containers\n"
            "- **Horizontal** — deploy multiple RADIUS replicas behind a load balancer\n"
            "- **Multi-node** — twin-node architecture distributes load across sites\n\n"
            "**Resource Requirements:**\n"
            "| Deployment Size | Endpoints | Specs |\n"
            "|---|---|---|\n"
            "| Small | <1,000 | 4 vCPU, 8GB RAM, 50GB disk |\n"
            "| Medium | 1,000-10,000 | 8 vCPU, 16GB RAM, 100GB disk |\n"
            "| Large | 10,000-100,000 | 16 vCPU, 32GB RAM, 500GB disk |\n"
            "| Enterprise | 100,000+ | Multi-node K8s cluster |\n\n"
            "**NeuraNAC includes capacity forecasting** — it uses historical data to predict growth and "
            "recommend infrastructure scaling.\n\n"
            "Try: *\"Show capacity metrics\"* or *\"Show capacity forecast\"*"
        ),
    },
    {
        "id": "api_integration",
        "title": "API & Integrations",
        "keywords": [
            "api", "rest api", "integration", "webhook", "siem",
            "splunk", "elasticsearch", "servicenow", "pagerduty",
            "automation", "scripting", "sdk", "third-party",
        ],
        "content": (
            "### API & Integrations\n\n"
            "NeuraNAC provides a **comprehensive REST API** with 200+ endpoints across 30 routers.\n\n"
            "**API Authentication:**\n"
            "```\n"
            "POST /api/v1/auth/login\n"
            "{\"username\": \"admin\", \"password\": \"...\"}\n"
            "→ Returns JWT access_token\n"
            "```\n"
            "All subsequent requests: `Authorization: Bearer <token>`\n\n"
            "**Key API Domains:**\n"
            "- `/api/v1/policies/` — CRUD policies\n"
            "- `/api/v1/endpoints/` — manage endpoints\n"
            "- `/api/v1/network-devices/` — manage network devices\n"
            "- `/api/v1/sessions/` — query sessions\n"
            "- `/api/v1/ai/` — AI capabilities (chat, risk, anomaly, etc.)\n"
            "- `/api/v1/certificates/` — certificate management\n"
            "- `/api/v1/audit/` — audit log\n"
            "- `/api/v1/diagnostics/` — system health\n\n"
            "**Integrations:**\n"
            "- **SIEM** — forward logs to Splunk, Elasticsearch, QRadar\n"
            "- **Webhooks** — push events to any HTTP endpoint\n"
            "- **ServiceNow** — auto-create incidents\n"
            "- **PagerDuty** — alert escalation\n"
            "- **Prometheus/Grafana** — built-in metrics and dashboards\n"
            "- **NATS** — event-driven integrations\n\n"
            "**API Documentation:** Available at `http://localhost:8080/docs` (Swagger UI)"
        ),
    },
    {
        "id": "compliance_audit",
        "title": "Compliance & Audit",
        "keywords": [
            "compliance", "audit", "regulation", "gdpr", "hipaa", "pci",
            "sox", "nist", "iso 27001", "log", "audit trail", "report",
            "evidence", "governance", "forensic", "framework", "frameworks",
            "compliance framework", "compliance frameworks", "regulatory",
            "pci dss", "nist 800", "iso 27001", "support compliance",
        ],
        "content": (
            "### Compliance & Auditing\n\n"
            "NeuraNAC provides comprehensive auditing and compliance features.\n\n"
            "**Audit Trail:**\n"
            "- Every admin action is logged (create, update, delete, login, CoA)\n"
            "- Immutable audit log with timestamps, user, IP, action, and before/after data\n"
            "- Search and filter by user, action type, date range\n\n"
            "**Compliance Frameworks:**\n"
            "| Framework | NeuraNAC Support |\n"
            "|---|---|\n"
            "| **PCI DSS** | Network segmentation, access logging, encryption |\n"
            "| **HIPAA** | Access control, audit trail, encryption at rest/transit |\n"
            "| **NIST 800-53** | Authentication, authorization, continuous monitoring |\n"
            "| **ISO 27001** | Information security controls, access management |\n"
            "| **SOX** | Admin action audit trail, separation of duties |\n"
            "| **GDPR** | Data encryption, access logging, data retention policies |\n\n"
            "**Reporting:**\n"
            "- Authentication success/failure reports\n"
            "- Policy compliance reports\n"
            "- Device posture reports\n"
            "- Shadow AI usage reports\n"
            "- Risk score trend reports\n\n"
            "Try: *\"Show audit log\"* or *\"Show authentication report\"*"
        ),
    },
]


def score_article(article: dict, query_lower: str) -> float:
    """Score how relevant an article is to a query using keyword matching.

    Returns a float score — higher means more relevant.
    Uses a combination of exact keyword hits and partial stem matching.
    """
    score = 0.0
    query_words = set(query_lower.split())

    for keyword in article["keywords"]:
        kw_lower = keyword.lower()
        # Exact phrase match in query (highest weight)
        if kw_lower in query_lower:
            score += 3.0 + len(kw_lower) * 0.1  # longer matches score higher
        # Word-level overlap
        kw_words = set(kw_lower.split())
        overlap = query_words & kw_words
        if overlap:
            score += len(overlap) * 1.5

    # Bonus for title words appearing in query
    for word in article["title"].lower().split():
        if len(word) > 3 and word in query_lower:
            score += 2.0

    return score


def find_best_article(query: str, threshold: float = 3.0):
    """Find the best matching knowledge article for a query.

    Returns (article, score) or (None, 0) if no article scores above threshold.
    """
    query_lower = query.lower().strip()
    best_article = None
    best_score = 0.0

    for article in NAC_KNOWLEDGE_ARTICLES:
        s = score_article(article, query_lower)
        if s > best_score:
            best_score = s
            best_article = article

    if best_score >= threshold:
        return best_article, best_score
    return None, 0.0
