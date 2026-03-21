import { useState, useMemo } from 'react';
import { Search, Book, Shield, Router, Monitor, Users, Bot, Server, Lock, Activity, ClipboardCheck, Network, Wrench, ChevronDown, ChevronRight } from 'lucide-react';

interface DocSection {
  id: string;
  title: string;
  icon: any;
  articles: DocArticle[];
}

interface DocArticle {
  id: string;
  title: string;
  content: string;
  tags: string[];
}

const helpSections: DocSection[] = [
  {
    id: 'getting-started',
    title: 'Getting Started',
    icon: Book,
    articles: [
      {
        id: 'what-is-neuranac',
        title: 'What is NeuraNAC?',
        content: `NeuraNAC (NeuraNAC) is an enterprise-grade, AI-powered Network Access Control (NAC) platform. It provides centralized authentication, authorization, and accounting (AAA) for wired, wireless, and VPN network access.

Key capabilities:
• 802.1X Authentication — PAP, EAP-TLS, EAP-TTLS, PEAP
• TACACS+ — Device administration AAA
• AI Agent Governance — Authenticate and monitor AI/ML workloads
• Shadow AI Detection — Detect unauthorized AI services
• Policy-Driven Segmentation — VLAN and SGT assignment based on identity, device, and risk
• Posture Assessment — 8 compliance check types
• Guest & BYOD — Captive portals, sponsor groups, certificate provisioning
• Twin-Node HA — Bidirectional replication for on-premises deployments`,
        tags: ['overview', 'introduction', 'nac', 'features'],
      },
      {
        id: 'quick-start',
        title: 'Quick Start Guide',
        content: `1. Start all services:
   cd deploy && docker compose up -d

2. Check service health:
   curl http://localhost:8080/health

3. Get admin credentials from logs:
   docker logs neuranac-api | grep "Default admin"

4. Login to the dashboard:
   Open http://localhost:3001 in your browser

5. Add your first Network Access Device:
   Navigate to Network Devices → Add Device

6. Create an authentication policy:
   Navigate to Policies → Create Policy Set

7. Test RADIUS authentication:
   radtest testuser testing123 localhost 0 testing123`,
        tags: ['setup', 'install', 'first-time', 'quick start'],
      },
      {
        id: 'service-ports',
        title: 'Service Ports Reference',
        content: `API Gateway:        8080  (HTTP REST API)
Web Dashboard:      3001  (HTTP)
RADIUS Auth:        1812  (UDP)
RADIUS Accounting:  1813  (UDP)
RadSec:             2083  (TCP/TLS)
TACACS+:            49    (TCP)
CoA:                3799  (UDP)
Policy Engine API:  8082  (HTTP)
Policy Engine gRPC: 9091  (gRPC)
AI Engine:          8081  (HTTP)
Sync Engine gRPC:   9090  (gRPC)
Sync Engine Health: 9100  (HTTP)
PostgreSQL:         5432  (TCP)
Redis:              6379  (TCP)
NATS:               4222  (TCP)
NATS Monitor:       8222  (HTTP)
Prometheus:         9092  (HTTP)
Grafana:            3000  (HTTP)`,
        tags: ['ports', 'services', 'network', 'configuration'],
      },
    ],
  },
  {
    id: 'authentication',
    title: 'Authentication',
    icon: Shield,
    articles: [
      {
        id: 'auth-methods',
        title: 'Supported Authentication Methods',
        content: `NeuraNAC supports the following authentication methods:

PAP (Password Authentication Protocol):
  Used for: Legacy devices, VPN concentrators
  How it works: Username + password sent in RADIUS Access-Request
  Security: Password encrypted using RADIUS shared secret

EAP-TLS (RFC 5216):
  Used for: Corporate laptops with machine certificates
  How it works: Full TLS handshake with mutual certificate validation
  Security: Strongest — both client and server authenticated via certificates

EAP-TTLS (RFC 5281):
  Used for: BYOD devices with username/password
  How it works: Outer TLS tunnel (server cert only), inner PAP/MSCHAPv2
  Security: Strong — credentials protected by TLS tunnel

PEAP (Protected EAP):
  Used for: Windows domain machines
  How it works: TLS tunnel with MSCHAPv2 inner authentication
  Security: Strong — similar to EAP-TTLS

MAB (MAC Authentication Bypass):
  Used for: Headless devices (printers, IP phones, IoT)
  How it works: Switch sends MAC address as username
  Security: Low — MAC addresses can be spoofed; combine with profiling`,
        tags: ['radius', 'eap', 'pap', 'tls', 'peap', 'mab', '802.1x'],
      },
      {
        id: 'ai-agent-auth',
        title: 'AI Agent Authentication',
        content: `NeuraNAC provides first-class authentication for AI/ML agents:

1. Register the AI agent:
   Dashboard → AI Agents → Add Agent
   Configure: name, type, delegation scope, model type, bandwidth limit

2. Agent authenticates via RADIUS:
   Username format: "agent:<agent-name>"
   Example: "agent:ml-pipeline-01"

3. NeuraNAC evaluates:
   • Agent exists and is active
   • Delegation scope is appropriate
   • Bandwidth limits are set
   • Data classification permissions checked

4. Policy applied:
   • AI-specific VLAN assigned
   • SGT tag applied
   • Bandwidth enforcement via RADIUS attributes

5. Ongoing monitoring:
   • Shadow AI detector watches for unauthorized AI traffic
   • Risk scorer factors AI activity into composite score
   • Data flow policies enforce egress rules`,
        tags: ['ai', 'agent', 'ml', 'authentication', 'governance'],
      },
      {
        id: 'tacacs',
        title: 'TACACS+ Device Administration',
        content: `TACACS+ provides device administration AAA for network equipment:

Configuration:
  Server: NeuraNAC RADIUS Server (port 49/TCP)
  Shared secret: Configured per-device

Supported operations:
  • Authentication — Verify admin credentials (ASCII, PAP, CHAP)
  • Authorization — Command-level authorization with privilege levels
  • Accounting — Track admin commands and session activity

NAD Configuration (Cisco IOS):
  tacacs server NeuraNAC
    address ipv4 <NeuraNAC_IP>
    key <shared-secret>
    port 49

  aaa authentication login default group tacacs+ local
  aaa authorization exec default group tacacs+ local
  aaa accounting exec default start-stop group tacacs+`,
        tags: ['tacacs', 'device admin', 'authorization', 'commands'],
      },
    ],
  },
  {
    id: 'network-devices',
    title: 'Network Devices',
    icon: Router,
    articles: [
      {
        id: 'add-nad',
        title: 'Adding a Network Access Device',
        content: `To add a NAD to NeuraNAC:

1. Navigate to Network Devices in the sidebar
2. Click "Add Device"
3. Fill in the required fields:
   • Name: Descriptive name (e.g., "access-switch-01")
   • IP Address: Management IP of the device
   • Device Type: switch, wireless_controller, vpn, firewall, router
   • Vendor: cisco, aruba, juniper, fortinet, paloalto, meraki, etc.
   • Shared Secret: RADIUS shared secret (min 16 chars recommended)
   • CoA Port: Change of Authorization port (default: 3799)
4. Click Save

Via API:
  POST /api/v1/network-devices/
  Body: { "name": "...", "ip_address": "...", "shared_secret": "..." }

Important: The shared secret must match exactly on both NeuraNAC and the NAD.`,
        tags: ['nad', 'switch', 'add device', 'shared secret', 'configuration'],
      },
      {
        id: 'supported-vendors',
        title: 'Supported NAD Vendors',
        content: `NeuraNAC supports any RADIUS-compliant network device. Tested vendors:

Full Support (RADIUS + TACACS+ + CoA + 802.1X + MAB):
  • Cisco Catalyst 9000/3000/2960 series
  • Cisco ISR 4000, ASR 1000
  • Aruba/HPE CX 6000/8000
  • Juniper EX2300/EX3400/EX4300
  • Dell PowerSwitch S/N/Z series

RADIUS + CoA + 802.1X (no TACACS+):
  • Cisco Meraki MS switches, MR APs
  • Cisco WLC 9800/5520
  • Fortinet FortiSwitch, FortiGate, FortiAP
  • Ruckus ICX, SmartZone
  • Extreme x435/x440/x465
  • Allied Telesis x530/x930

RadSec Support:
  • Cisco Catalyst, ISR, ASR
  • Aruba CX
  • Juniper EX, QFX

Any device supporting standard RADIUS (RFC 2865) will work for basic authentication.`,
        tags: ['vendors', 'cisco', 'aruba', 'juniper', 'fortinet', 'compatibility'],
      },
      {
        id: 'auto-discovery',
        title: 'NAD Auto-Discovery',
        content: `NeuraNAC can automatically discover network devices on a subnet:

1. Navigate to Network Devices
2. Click "Auto-Discover" or use the API:
   POST /api/v1/network-devices/discover
   Body: { "subnet": "10.10.1.0/24" }

The discovery process:
  1. Scans the subnet for live hosts (NeuraNACP/ARP)
  2. Probes common ports: RADIUS (1812), SNMP (161), SSH (22), HTTP (80/443)
  3. Guesses vendor from MAC OUI prefix
  4. Returns a list of discovered devices

Review the results and import the devices you want to manage.
Each imported device still needs a shared secret configured.`,
        tags: ['discovery', 'scan', 'subnet', 'auto', 'find devices'],
      },
    ],
  },
  {
    id: 'policies',
    title: 'Policy Management',
    icon: Shield,
    articles: [
      {
        id: 'create-policy',
        title: 'Creating Authentication Policies',
        content: `Policies determine what happens when a device or user authenticates.

Structure:
  Policy Set → contains → Policy Rules → references → Auth Profiles

Creating a Policy Set:
  1. Navigate to Policies
  2. Click "Create Policy Set"
  3. Set name, description, and priority (lower = higher priority)
  4. Add conditions that match incoming requests
  5. Configure the result (VLAN, SGT, ACL, session timeout)

Conditions use 14 operators:
  equals, not_equals, contains, starts_with, ends_with,
  in, not_in, matches (regex), greater_than, less_than,
  between, is_true, is_false

Example policies:
  • "Employees get VLAN 100": User-Group contains "employees" → VLAN 100
  • "Printers get VLAN 300": Endpoint-Profile equals "printer" → VLAN 300
  • "High risk → quarantine": Risk-Score greater_than 70 → VLAN 999`,
        tags: ['policy', 'rules', 'conditions', 'vlan', 'sgt', 'create'],
      },
      {
        id: 'nlp-policy',
        title: 'Natural Language Policy Creation',
        content: `NeuraNAC's AI Engine can translate natural language to policy rules:

API: POST http://localhost:8081/api/v1/nlp/translate
Body: { "text": "Block guest users after 6pm" }

The AI will generate:
  {
    "conditions": [
      {"attribute": "User-Group", "operator": "equals", "value": "guest"},
      {"attribute": "Time-Of-Day", "operator": "greater_than", "value": "18:00"}
    ],
    "result": { "action": "deny" }
  }

Requirements:
  • LLM endpoint configured (Ollama or OpenAI compatible)
  • Set LLM_API_URL and LLM_MODEL environment variables
  • Falls back to template matching if LLM unavailable`,
        tags: ['nlp', 'natural language', 'ai', 'policy creation', 'translate'],
      },
    ],
  },
  {
    id: 'endpoints',
    title: 'Endpoints & Profiling',
    icon: Monitor,
    articles: [
      {
        id: 'endpoint-profiling',
        title: 'AI Endpoint Profiling',
        content: `NeuraNAC uses AI to automatically classify devices connecting to the network:

How it works:
  1. Device connects and authenticates (802.1X or MAB)
  2. NeuraNAC collects: MAC address, DHCP hostname, HTTP user-agent, vendor OUI
  3. AI Profiler analyzes attributes using ONNX ML model
  4. If model not loaded, rule-based fallback classifies by OUI + hostname patterns
  5. Device profile stored: type, OS, vendor, confidence score

Profile types: workstation, laptop, printer, phone, camera, iot_sensor, server, 
               network_device, medical_device, industrial, unknown

Policy integration:
  Use "Endpoint-Profile" in policy conditions to segment by device type.
  Example: Endpoint-Profile equals "printer" → VLAN 300 (IoT segment)`,
        tags: ['profiling', 'classification', 'ai', 'device type', 'onnx', 'ml'],
      },
    ],
  },
  {
    id: 'guest-byod',
    title: 'Guest & BYOD',
    icon: Users,
    articles: [
      {
        id: 'guest-portal',
        title: 'Setting Up Guest Access',
        content: `1. Create a Guest Portal:
   Dashboard → Guest & BYOD → Create Portal
   Configure: name, branding, required fields, terms of service

2. Configure redirect policy:
   Create a policy that assigns unregistered devices to Guest VLAN
   with HTTP redirect to the portal URL

3. Guest registration flow:
   • Guest connects to network
   • Redirected to captive portal
   • Fills registration form (name, email, company)
   • Bot detection validates the submission
   • Account created with random password + expiry
   • Guest re-authenticates with new credentials

4. Sponsor approval (optional):
   Enable sponsor approval in portal settings
   Sponsors receive email notification
   Guest access activated after sponsor approves

Account expiry: Configurable per-portal (1 hour to 30 days)`,
        tags: ['guest', 'portal', 'captive', 'registration', 'sponsor', 'wifi'],
      },
      {
        id: 'byod-onboarding',
        title: 'BYOD Device Onboarding',
        content: `BYOD (Bring Your Own Device) workflow:

1. User connects personal device to BYOD SSID
2. Unknown MAC → assigned to onboarding VLAN
3. Redirected to BYOD registration portal
4. User authenticates with corporate credentials
5. NeuraNAC detects device type (OS, platform)
6. Certificate provisioned to the device
7. Device profile created in NeuraNAC
8. Device re-authenticates using provisioned certificate (EAP-TLS)
9. Policy assigns appropriate VLAN based on user + device

Prerequisites:
  • Certificate Authority configured in NeuraNAC
  • BYOD portal created
  • Redirect policy for unknown devices
  • EAP-TLS policy for certificate-based auth`,
        tags: ['byod', 'personal device', 'onboarding', 'certificate', 'provisioning'],
      },
    ],
  },
  {
    id: 'ai-features',
    title: 'AI & Security',
    icon: Bot,
    articles: [
      {
        id: 'shadow-ai',
        title: 'Shadow AI Detection',
        content: `NeuraNAC detects unauthorized AI service usage on the network:

Built-in signatures (14+):
  • OpenAI (ChatGPT, API)
  • Anthropic (Claude)
  • Google AI (Gemini, PaLM)
  • Hugging Face
  • GitHub Copilot
  • Amazon Bedrock
  • Azure OpenAI
  • Ollama, LM Studio, LocalAI (local LLMs)

Detection methods:
  • DNS query pattern matching
  • HTTP header analysis
  • TLS SNI (Server Name Indication)
  • Port scanning for local LLM servers

Response actions:
  • Alert — Dashboard notification + SIEM event
  • Quarantine — CoA to restricted VLAN
  • Block — SOAR webhook to firewall

Configure at: Dashboard → AI Data Flow → Policies`,
        tags: ['shadow ai', 'detection', 'openai', 'unauthorized', 'governance'],
      },
      {
        id: 'risk-scoring',
        title: 'Risk Scoring',
        content: `NeuraNAC calculates a real-time composite risk score (0-100) for every session:

Four dimensions:
  1. Behavioral (0-25): Failed auth attempts, unusual patterns
  2. Identity (0-25): Unknown user, missing groups, weak identity source
  3. Endpoint (0-25): Posture status, local LLM running
  4. AI Activity (uncapped): Shadow AI detected, delegation depth, data upload volume

Risk levels:
  • Low: 0-29 → Normal access
  • Medium: 30-59 → Enhanced monitoring
  • High: 60-79 → Restricted access, admin alert
  • Critical: 80-100 → Automatic quarantine (CoA)

Policy integration:
  Use "Risk-Score greater_than 70" in policy conditions
  Automatic CoA triggered when score exceeds threshold

API: POST http://localhost:8081/api/v1/risk
Body: { "username": "...", "posture_status": "...", "shadow_ai_detected": true }`,
        tags: ['risk', 'scoring', 'behavioral', 'threat', 'anomaly'],
      },
      {
        id: 'anomaly-detection',
        title: 'Anomaly Detection',
        content: `NeuraNAC learns authentication baselines and alerts on deviations:

Monitored patterns:
  • Authentication times (unusual hours)
  • Device locations (new NAD for known user)
  • Auth volume (spike in attempts)
  • Failed auth rates (brute force detection)
  • New device types (unknown profile)

How it works:
  1. Baseline period: NeuraNAC learns normal patterns over 7-30 days
  2. Deviation detection: New authentications compared against baseline
  3. Anomaly score: How far the event deviates from normal
  4. Alert: High anomaly scores trigger dashboard alerts + SIEM events

API: POST http://localhost:8081/api/v1/anomaly/analyze
Body: { "endpoint_mac": "AA:BB:CC:DD:EE:FF", "username": "jdoe", "nas_ip": "10.0.0.1" }`,
        tags: ['anomaly', 'baseline', 'detection', 'unusual', 'alert'],
      },
    ],
  },
  {
    id: 'posture',
    title: 'Posture Assessment',
    icon: ClipboardCheck,
    articles: [
      {
        id: 'posture-checks',
        title: 'Posture Check Types',
        content: `NeuraNAC evaluates 8 endpoint compliance check types:

1. antivirus — AV software installed and up-to-date
2. firewall — Host firewall enabled and active
3. disk_encryption — Full disk encryption (BitLocker, FileVault)
4. os_patch — Operating system patches within threshold
5. screen_lock — Screen lock timeout configured (max minutes)
6. jailbroken — Jailbreak/root detection for mobile devices
7. certificate — Valid client certificate present
8. agent_version — Posture agent meets minimum version

Compliance flow:
  1. Endpoint authenticates → assigned to posture-pending VLAN
  2. Posture agent reports device status
  3. NeuraNAC evaluates all configured checks
  4. Compliant → CoA to production VLAN
  5. Non-compliant → CoA to remediation VLAN + user notification

API: POST /api/v1/posture/assess
Body: { "mac": "AA:BB:CC:DD:EE:FF", "checks": [...] }`,
        tags: ['posture', 'compliance', 'antivirus', 'firewall', 'encryption', 'assessment'],
      },
    ],
  },
  {
    id: 'segmentation',
    title: 'Network Segmentation',
    icon: Network,
    articles: [
      {
        id: 'sgt-overview',
        title: 'Security Group Tags (SGT)',
        content: `NeuraNAC implements TrustSec-style micro-segmentation:

Security Group Tags (SGTs):
  • Numeric tags (e.g., 10=Employees, 20=Contractors, 30=IoT)
  • Assigned to endpoints during authentication
  • Used by switches/firewalls for traffic enforcement

Adaptive Policy Matrix:
  • Defines which SGTs can communicate
  • Example: Employees(10) → IoT(30): permit
  • Example: Contractors(20) → IoT(30): deny

Configuration:
  1. Create SGTs: Dashboard → Segmentation → Create SGT
  2. Define ACLs: Source SGT → Destination SGT → Action
  3. Policy assigns SGT during auth: Policy result includes SGT value
  4. Switches enforce using downloaded matrix

VLAN Assignment:
  VLANs are assigned via RADIUS attributes in Access-Accept:
  Tunnel-Type = VLAN, Tunnel-Medium-Type = IEEE-802, Tunnel-Private-Group-Id = <VLAN>`,
        tags: ['sgt', 'trustsec', 'vlan', 'segmentation', 'matrix', 'micro-segmentation'],
      },
    ],
  },
  {
    id: 'sync-ha',
    title: 'High Availability',
    icon: Server,
    articles: [
      {
        id: 'twin-node',
        title: 'Twin-Node Architecture',
        content: `NeuraNAC supports on-premises HA with twin-node bidirectional replication:

Architecture:
  • Node A (Primary) ←→ Node B (Secondary)
  • Both nodes are active and can handle authentications
  • Configuration changes replicate in real-time via gRPC

Sync mechanism:
  1. Any config change creates a journal entry in PostgreSQL
  2. Sync Engine polls for undelivered journal entries
  3. Entries streamed to peer via bidirectional gRPC
  4. Peer applies changes with last-writer-wins conflict resolution

Setup:
  Node A: Set NEURANAC_NODE_ID=twin-a, SYNC_PEER_ADDRESS=node-b:9090
  Node B: Set NEURANAC_NODE_ID=twin-b, SYNC_PEER_ADDRESS=node-a:9090

Monitoring:
  curl http://node-a:9100/sync/status
  → { "peer_connected": true, "pending_outbound": 0 }

NAD Configuration:
  Configure both nodes as RADIUS servers on each NAD (primary + secondary)`,
        tags: ['ha', 'high availability', 'sync', 'twin', 'replication', 'failover'],
      },
    ],
  },
  {
    id: 'integrations',
    title: 'Integrations',
    icon: Activity,
    articles: [
      {
        id: 'siem-integration',
        title: 'SIEM Integration',
        content: `NeuraNAC forwards security events to SIEM platforms:

Supported formats:
  • Syslog (RFC 5424)
  • CEF (Common Event Format)

Supported platforms:
  • Splunk
  • IBM QRadar
  • Microsoft Sentinel
  • Elastic / ELK Stack
  • ArcSight

Configuration:
  Dashboard → Settings or API:
  POST /api/v1/siem/targets
  Body: {
    "name": "Splunk",
    "host": "splunk.example.com",
    "port": 514,
    "protocol": "tcp",
    "format": "cef",
    "event_types": ["auth.success", "auth.failure", "ai.shadow_detected"]
  }

Event types: auth.success, auth.failure, policy.decision, posture.noncompliant,
             ai.shadow_detected, coa.triggered, audit.action`,
        tags: ['siem', 'splunk', 'qradar', 'sentinel', 'logging', 'cef', 'syslog'],
      },
      {
        id: 'identity-sources',
        title: 'Identity Source Configuration',
        content: `NeuraNAC supports multiple identity sources:

Active Directory / LDAP:
  • Bind + search for user authentication
  • Group membership sync
  • Test connection before saving

SAML 2.0 SSO:
  • AuthnRequest generation
  • ACS (Assertion Consumer Service) endpoint
  • IdP certificate validation
  • Attribute mapping (email, groups, display name)

OAuth2:
  • Authorization code flow
  • Token exchange
  • UserInfo endpoint integration
  • Supports: Google, GitHub, Azure AD, Okta, etc.

Internal Database:
  • Local user/password management
  • bcrypt password hashing
  • Failed attempt tracking + account lockout

Configure at: Dashboard → Identity Sources → Add Source`,
        tags: ['identity', 'ldap', 'active directory', 'saml', 'oauth', 'sso'],
      },
    ],
  },
  {
    id: 'troubleshooting',
    title: 'Troubleshooting',
    icon: Wrench,
    articles: [
      {
        id: 'auth-failures',
        title: 'Debugging Authentication Failures',
        content: `Common causes and solutions:

"Access-Reject" response:
  1. Check credentials: Verify username/password in identity source
  2. Check NAD registration: Is the NAD IP registered in NeuraNAC?
  3. Check shared secret: Must match exactly on both sides
  4. Check policy: Does a matching policy exist?
  5. Check logs: docker logs neuranac-radius | grep "auth"

"No response" from RADIUS:
  1. Network connectivity: Can NAD reach NeuraNAC on port 1812/UDP?
  2. Firewall rules: Is UDP 1812 allowed?
  3. Service running: curl http://localhost:9100/health (RADIUS health)
  4. Check RADIUS listener: docker logs neuranac-radius | grep "listening"

EAP-TLS failures:
  1. Certificate expired: Check cert validity dates
  2. CA not trusted: Ensure client's CA is imported into NeuraNAC
  3. Wrong cert type: Client cert must have "client" usage
  4. TLS version: Ensure TLS 1.2+ is used

CoA not working:
  1. Check CoA port: NAD must listen on port 3799/UDP
  2. Check shared secret: CoA uses same shared secret as RADIUS
  3. Session exists: CoA requires an active session ID

AI Troubleshooter:
  POST http://localhost:8081/api/v1/troubleshoot
  Body: { "username": "jdoe", "nas_ip": "10.0.0.1", "error": "Access-Reject" }`,
        tags: ['troubleshoot', 'debug', 'auth failure', 'reject', 'timeout', 'error'],
      },
      {
        id: 'service-health',
        title: 'Service Health Checks',
        content: `Check health of all NeuraNAC services:

API Gateway:     curl http://localhost:8080/health
AI Engine:       curl http://localhost:8081/health
Policy Engine:   curl http://localhost:8082/health
Sync Engine:     curl http://localhost:9100/health
NATS:            curl http://localhost:8222/healthz

Full system status:
  curl http://localhost:8080/api/v1/diagnostics/system-status

Container logs:
  docker logs neuranac-api       # API Gateway
  docker logs neuranac-radius    # RADIUS Server
  docker logs neuranac-policy    # Policy Engine
  docker logs neuranac-ai        # AI Engine
  docker logs neuranac-sync      # Sync Engine

Database health:
  docker exec neuranac-postgres pg_isready -U neuranac

Redis health:
  docker exec neuranac-redis redis-cli -a neuranac_dev_password ping`,
        tags: ['health', 'status', 'monitoring', 'logs', 'diagnostics'],
      },
    ],
  },
  {
    id: 'privacy',
    title: 'Privacy & Compliance',
    icon: Lock,
    articles: [
      {
        id: 'gdpr-ccpa',
        title: 'GDPR & CCPA Compliance',
        content: `NeuraNAC includes built-in privacy compliance features:

GDPR Article 17 — Right to Erasure:
  • Data subjects can request deletion of personal data
  • Dashboard → Privacy → Right to Erasure
  • API: DELETE /api/v1/privacy/subjects/{id}/erase

GDPR Article 20 — Data Portability:
  • Export personal data in machine-readable format
  • Dashboard → Privacy → Data Export Requests
  • API: POST /api/v1/privacy/exports

Consent Management:
  • Track consent records per data subject
  • Record: purpose, given date, revocation
  • Dashboard → Privacy → Consent Records

Data Retention:
  • Configurable retention policies per data type
  • Automated purging of expired data
  • Audit trail of all deletions

API endpoints:
  GET /api/v1/privacy/subjects — List data subjects
  GET /api/v1/privacy/consent — List consent records
  GET /api/v1/privacy/exports — List export requests
  POST /api/v1/privacy/exports — Create export request
  DELETE /api/v1/privacy/subjects/{id}/erase — Right to erasure`,
        tags: ['gdpr', 'ccpa', 'privacy', 'erasure', 'consent', 'compliance', 'data export'],
      },
    ],
  },
];

export default function HelpDocsPage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set(['getting-started']));
  const [selectedArticle, setSelectedArticle] = useState<DocArticle | null>(helpSections[0].articles[0]);

  const filteredSections = useMemo(() => {
    if (!searchQuery.trim()) return helpSections;
    const q = searchQuery.toLowerCase();
    return helpSections
      .map((section) => ({
        ...section,
        articles: section.articles.filter(
          (a) =>
            a.title.toLowerCase().includes(q) ||
            a.content.toLowerCase().includes(q) ||
            a.tags.some((t) => t.includes(q))
        ),
      }))
      .filter((s) => s.articles.length > 0);
  }, [searchQuery]);

  const toggleSection = (id: string) => {
    setExpandedSections((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const totalArticles = helpSections.reduce((sum, s) => sum + s.articles.length, 0);

  return (
    <div className="flex h-[calc(100vh-3rem)] -m-6">
      {/* Sidebar */}
      <div className="w-80 border-r border-border bg-card flex flex-col">
        <div className="p-4 border-b border-border">
          <h1 className="text-lg font-bold text-foreground mb-3">Help & Documentation</h1>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <input
              type="text"
              placeholder={`Search ${totalArticles} articles...`}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-3 py-2 bg-background border border-border rounded-md text-sm text-foreground placeholder-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary"
            />
          </div>
        </div>
        <nav className="flex-1 overflow-y-auto p-2">
          {filteredSections.map((section) => {
            const Icon = section.icon;
            const isExpanded = expandedSections.has(section.id) || searchQuery.trim().length > 0;
            return (
              <div key={section.id} className="mb-1">
                <button
                  onClick={() => toggleSection(section.id)}
                  className="w-full flex items-center gap-2 px-3 py-2 text-sm font-medium text-foreground hover:bg-accent rounded-md"
                >
                  {isExpanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                  <Icon className="h-4 w-4 text-muted-foreground" />
                  <span>{section.title}</span>
                  <span className="ml-auto text-xs text-muted-foreground">{section.articles.length}</span>
                </button>
                {isExpanded && (
                  <div className="ml-5 pl-2 border-l border-border">
                    {section.articles.map((article) => (
                      <button
                        key={article.id}
                        onClick={() => setSelectedArticle(article)}
                        className={`w-full text-left px-3 py-1.5 text-sm rounded-md mb-0.5 ${
                          selectedArticle?.id === article.id
                            ? 'bg-primary/10 text-primary font-medium'
                            : 'text-muted-foreground hover:bg-accent hover:text-foreground'
                        }`}
                      >
                        {article.title}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
          {filteredSections.length === 0 && (
            <div className="p-4 text-center text-muted-foreground text-sm">
              No articles found for "{searchQuery}"
            </div>
          )}
        </nav>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {selectedArticle ? (
          <div className="max-w-3xl mx-auto p-8">
            <h1 className="text-2xl font-bold text-foreground mb-4">{selectedArticle.title}</h1>
            <div className="flex gap-2 mb-6 flex-wrap">
              {selectedArticle.tags.map((tag) => (
                <span
                  key={tag}
                  onClick={() => setSearchQuery(tag)}
                  className="px-2 py-0.5 bg-primary/10 text-primary text-xs rounded-full cursor-pointer hover:bg-primary/20"
                >
                  {tag}
                </span>
              ))}
            </div>
            <div className="prose prose-invert max-w-none">
              <pre className="whitespace-pre-wrap font-sans text-sm text-foreground leading-relaxed bg-transparent p-0 border-0">
                {selectedArticle.content}
              </pre>
            </div>
          </div>
        ) : (
          <div className="flex items-center justify-center h-full text-muted-foreground">
            <div className="text-center">
              <Book className="h-12 w-12 mx-auto mb-3 opacity-50" />
              <p>Select an article from the sidebar</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
