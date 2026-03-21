# NeuraNAC Architecture & Design

This document provides a comprehensive technical view of the NeuraNAC (NeuraNAC) architecture, including system topology, data flow patterns, integration points, and internal component design.

---

## Table of Contents

1. [High-Level System Architecture](#1-high-level-system-architecture)
2. [Component Architecture](#2-component-architecture)
3. [Data Flow Diagrams](#3-data-flow-diagrams)
4. [Integration Architecture](#4-integration-architecture)
5. [Database Schema Design](#5-database-schema-design)
6. [Security Architecture](#6-security-architecture)
7. [Deployment Architecture](#7-deployment-architecture)
8. [Network Topology](#8-network-topology)
9. [Legacy NAC Integration Architecture](#9-legacy-nac-integration-architecture)

---

## 1. High-Level System Architecture

NeuraNAC follows a **microservices architecture** with clear separation between the data plane (RADIUS/TACACS+), control plane (API/Policy/AI), synchronization layer, and presentation layer.

```mermaid
graph TB
    subgraph Clients["Client Layer"]
        BROWSER["Admin Browser<br/>React Dashboard :3001"]
        RESTCLI["REST API Clients<br/>Automation / Scripts"]
        SUPPLICANT["802.1X Supplicants<br/>Endpoints / Devices"]
        NETADMIN["Network Admins<br/>SSH / Console"]
    end

    subgraph Edge["Network Edge"]
        SWITCH["Switches<br/>(Cisco, Aruba, Juniper)"]
        WLC["Wireless Controllers<br/>(Cisco WLC, Aruba)"]
        VPN["VPN Concentrators<br/>(ASA, Palo Alto)"]
        FWALL["Firewalls<br/>(Cisco, Fortinet)"]
    end

    subgraph NeuraNAC["NeuraNAC Platform"]
        direction TB
        subgraph DP["Data Plane (Go)"]
            RADIUS["RADIUS Server<br/>:1812/:1813 UDP"]
            RADSEC["RadSec<br/>:2083 TLS"]
            TACACS["TACACS+<br/>:49 TCP"]
            COA["CoA Sender<br/>:3799 UDP"]
        end

        subgraph CP["Control Plane (Python)"]
            APIGW["API Gateway<br/>FastAPI :8080"]
            POLICY["Policy Engine<br/>gRPC :9091 + REST :8082"]
            AIENG["AI Engine<br/>7 Modules :8081"]
        end

        subgraph SL["Sync Layer (Go)"]
            SYNCA["Sync Engine A<br/>gRPC :9090"]
            SYNCB["Sync Engine B<br/>gRPC :9090"]
        end

        subgraph INFRA["Infrastructure"]
            PG[("PostgreSQL 16<br/>45+ Tables")]
            RD[("Redis 7<br/>Cache + Rate Limit")]
            NT["NATS JetStream<br/>Event Bus"]
        end
    end

    subgraph External["External Integrations"]
        AD["Active Directory"]
        LDAP["LDAP Server"]
        SAML["SAML IdP"]
        OAUTH["OAuth2 Provider"]
        SIEM["SIEM<br/>(Splunk, QRadar)"]
        SOAR["SOAR Platform"]
        PROM["Prometheus"]
        GRAF["Grafana"]
    end

    SUPPLICANT -->|"EAP/802.1X"| SWITCH
    SUPPLICANT -->|"EAP/802.1X"| WLC
    NETADMIN -->|"SSH/Console"| FWALL
    SWITCH -->|"RADIUS"| RADIUS
    WLC -->|"RADIUS"| RADIUS
    VPN -->|"RADIUS"| RADIUS
    SWITCH -->|"RadSec"| RADSEC
    FWALL -->|"TACACS+"| TACACS
    COA -->|"Disconnect-Request"| SWITCH
    RADIUS -->|"gRPC"| POLICY
    RADIUS --> PG
    RADIUS --> RD
    RADIUS --> NT
    POLICY --> PG
    APIGW --> PG
    APIGW --> RD
    APIGW -->|"REST"| POLICY
    APIGW -->|"REST"| AIENG
    BROWSER -->|"HTTPS"| APIGW
    RESTCLI -->|"HTTPS"| APIGW
    SYNCA <-->|"Bidirectional gRPC"| SYNCB
    APIGW -->|"LDAP Bind"| AD
    APIGW -->|"LDAP Bind"| LDAP
    APIGW -->|"SAML AuthnReq"| SAML
    APIGW -->|"OAuth2 Code"| OAUTH
    APIGW -->|"Syslog/CEF"| SIEM
    APIGW -->|"Webhook"| SOAR
    PROM -->|"Scrape /metrics"| APIGW
    GRAF -->|"Query"| PROM
```

---

## 2. Component Architecture

### 2.1 RADIUS Server (Go)

The RADIUS server is the core data-plane component handling all network authentication.

```mermaid
graph LR
    subgraph RADServer["RADIUS Server"]
        LISTENER["UDP Listener<br/>:1812 Auth / :1813 Acct"]
        HANDLER["Request Handler"]
        
        subgraph AuthMethods["Authentication Methods"]
            PAP["PAP Handler<br/>bcrypt verify"]
            EAPTLS["EAP-TLS<br/>RFC 5216 State Machine"]
            EAPTTLS["EAP-TTLS<br/>Tunneled Auth"]
            PEAP["PEAP<br/>MSCHAPv2 Inner"]
            MAB["MAB<br/>MAC Lookup"]
            AIAUTH["AI Agent Auth<br/>Token + Scope"]
        end

        STORE["DataStore<br/>PG + Redis + NATS"]
        GRPC_CLIENT["gRPC Client<br/>→ Policy Engine"]
        COA_SEND["CoA Sender<br/>Disconnect-Request"]
    end

    LISTENER --> HANDLER
    HANDLER --> PAP
    HANDLER --> EAPTLS
    HANDLER --> EAPTTLS
    HANDLER --> PEAP
    HANDLER --> MAB
    HANDLER --> AIAUTH
    PAP --> STORE
    EAPTLS --> STORE
    MAB --> STORE
    AIAUTH --> STORE
    HANDLER --> GRPC_CLIENT
    GRPC_CLIENT -->|"EvaluatePolicy"| PE_EXT["Policy Engine :9091"]
    HANDLER --> COA_SEND
    COA_SEND -->|"UDP :3799"| NAD_EXT["NAD"]
```

**Key files:**
- `cmd/server/main.go` — Entry point, listener setup, health endpoint
- `internal/handler/handler.go` — Request dispatch, EAP state machines, auth result building
- `internal/store/store.go` — PostgreSQL, Redis, NATS connections + data queries
- `internal/radius/server.go` — UDP packet I/O, RADIUS protocol decode/encode
- `internal/coa/coa.go` — CoA Disconnect-Request sender
- `internal/radsec/radsec.go` — RADIUS over TLS listener
- `internal/tacacs/tacacs.go` — TACACS+ protocol handler

### 2.2 API Gateway (Python FastAPI)

The API Gateway is the central REST API serving 22 routers through a layered middleware stack.

```mermaid
graph TB
    REQ["Incoming HTTP Request"] --> MW1["CORS Middleware"]
    MW1 --> MW2["Security Headers<br/>(OWASP)"]
    MW2 --> MW3["Prometheus Metrics"]
    MW3 --> MW4["Input Validation<br/>(SQL Injection + XSS)"]
    MW4 --> MW5["Rate Limiter<br/>(Redis Token Bucket)"]
    MW5 --> MW6["Auth Middleware<br/>(JWT Decode)"]
    MW6 --> MW7["Tenant Middleware<br/>(Context Isolation)"]
    MW7 --> ROUTER["Router Dispatch"]

    subgraph Routers["22 Routers"]
        R1["auth.py"]
        R2["policies.py"]
        R3["network_devices.py"]
        R4["endpoints.py"]
        R5["sessions.py"]
        R6["identity_sources.py"]
        R7["certificates.py"]
        R8["segmentation.py"]
        R9["guest.py"]
        R10["posture.py"]
        R11["ai_agents.py"]
        R12["ai_data_flow.py"]
        R13["nodes.py"]
        R14["admin.py"]
        R15["licenses.py"]
        R16["audit.py"]
        R17["diagnostics.py"]
        R18["privacy.py"]
        R19["siem.py"]
        R20["webhooks.py"]
        R21["setup.py"]
        R22["metrics.py"]
    end

    ROUTER --> Routers
    Routers --> DB[("PostgreSQL")]
    Routers --> CACHE[("Redis")]
    Routers --> BUS["NATS Events"]
```

### 2.3 Policy Engine

```mermaid
graph LR
    subgraph PolicyEngine["Policy Engine"]
        REST["REST API :8082<br/>/health, /evaluate, /reload"]
        GRPC["gRPC Server :9091<br/>PolicyService"]
        EVAL["PolicyEvaluator"]
        
        subgraph Operators["14 Comparison Operators"]
            OP1["equals / not_equals"]
            OP2["contains / starts_with / ends_with"]
            OP3["in / not_in"]
            OP4["matches (regex)"]
            OP5["greater_than / less_than"]
            OP6["between"]
            OP7["is_true / is_false"]
        end
    end

    RADIUS_IN["RADIUS Server<br/>(gRPC Call)"] -->|"EvaluateRequest"| GRPC
    API_IN["API Gateway<br/>(REST Call)"] -->|"POST /evaluate"| REST
    GRPC --> EVAL
    REST --> EVAL
    EVAL --> Operators
    EVAL --> DB_PE[("PostgreSQL<br/>policy_sets + policy_rules")]
    EVAL -->|"PolicyDecision"| RESULT["Result:<br/>VLAN, SGT, ACL,<br/>CoA Action"]
```

### 2.4 AI Engine — 7 Module Architecture

```mermaid
graph TB
    subgraph AIEngine["AI Engine :8081"]
        PROFILER["Endpoint Profiler<br/>ONNX Runtime + Rules<br/>/api/v1/profile"]
        RISK["Risk Scorer<br/>4-Dimensional Scoring<br/>/api/v1/risk"]
        SHADOW["Shadow AI Detector<br/>14+ Signatures<br/>/api/v1/shadow"]
        NLP["NLP Policy Assistant<br/>LLM Integration<br/>/api/v1/nlp/translate"]
        TROUBLESHOOT["AI Troubleshooter<br/>Root Cause Analysis<br/>/api/v1/troubleshoot"]
        ANOMALY["Anomaly Detector<br/>Baseline + Deviation<br/>/api/v1/anomaly/analyze"]
        DRIFT["Policy Drift Detector<br/>Config Change Detection<br/>/api/v1/drift/analyze"]
    end

    subgraph RiskDimensions["Risk Score Dimensions"]
        B["Behavioral<br/>(Failed auths, patterns)"]
        I["Identity<br/>(Unknown user, no groups)"]
        E["Endpoint<br/>(Posture, local LLM)"]
        A["AI Activity<br/>(Shadow AI, delegation depth, data upload)"]
    end

    RISK --> B
    RISK --> I
    RISK --> E
    RISK --> A
```

### 2.5 Sync Engine — Twin-Node Replication

```mermaid
graph LR
    subgraph NodeA["Twin Node A"]
        SYNCA["Sync Engine A<br/>gRPC :9090"]
        PGA[("PostgreSQL A")]
        JOURNALA["Sync Journal A"]
    end

    subgraph NodeB["Twin Node B"]
        SYNCB["Sync Engine B<br/>gRPC :9090"]
        PGB[("PostgreSQL B")]
        JOURNALB["Sync Journal B"]
    end

    PGA --> JOURNALA
    JOURNALA -->|"Outbound Changes"| SYNCA
    SYNCA <-->|"Bidirectional gRPC Stream<br/>with Conflict Resolution"| SYNCB
    SYNCB -->|"Apply Inbound"| PGB
    PGB --> JOURNALB
    JOURNALB -->|"Outbound Changes"| SYNCB
```

**Sync workflow:**
1. Any DB write creates a journal entry with table name, row ID, operation, and timestamp
2. Sync engine polls journal for undelivered entries
3. Entries are streamed to peer via bidirectional gRPC
4. Peer applies changes with last-writer-wins conflict resolution
5. Health endpoint reports sync lag, pending entries, and peer connection state

---

## 3. Data Flow Diagrams

### 3.1 802.1X Authentication Flow (EAP-TLS)

```mermaid
sequenceDiagram
    participant EP as Endpoint (Supplicant)
    participant NAD as Switch / WLC
    participant RAD as NeuraNAC RADIUS
    participant PE as Policy Engine
    participant AI as AI Engine
    participant DB as PostgreSQL

    EP->>NAD: EAPOL-Start
    NAD->>RAD: Access-Request (EAP-Identity)
    RAD->>RAD: Parse EAP Type → TLS
    
    loop EAP-TLS Handshake (RFC 5216)
        RAD->>NAD: Access-Challenge (EAP-TLS ServerHello)
        NAD->>EP: EAP-Request (TLS)
        EP->>NAD: EAP-Response (ClientCert + Verify)
        NAD->>RAD: Access-Request (EAP-TLS Fragment)
    end

    RAD->>DB: Validate Client Certificate
    RAD->>DB: Lookup Endpoint (MAC)
    RAD->>PE: gRPC EvaluatePolicy(identity, device, posture)
    PE->>DB: Load Policy Sets + Rules
    PE->>PE: Match Conditions (14 operators)
    PE-->>RAD: PolicyDecision {VLAN=100, SGT=15, permit}
    
    RAD->>AI: Risk Score Request
    AI-->>RAD: {total_score: 12, risk_level: "low"}
    
    alt Risk Score > 70
        RAD->>NAD: Access-Accept (Quarantine VLAN)
        RAD->>NAD: CoA Disconnect-Request (delayed)
    else Risk Score ≤ 70
        RAD->>NAD: Access-Accept (VLAN=100, SGT=15)
    end

    NAD->>EP: Port Authorized
    RAD->>DB: Create Session Record
    RAD->>NATS: Publish auth.success event
```

### 3.2 PAP Authentication Flow

```mermaid
sequenceDiagram
    participant NAD as Switch / WLC
    participant RAD as NeuraNAC RADIUS
    participant DB as PostgreSQL
    participant PE as Policy Engine

    NAD->>RAD: Access-Request (User-Name, User-Password)
    RAD->>RAD: Decrypt Password (RADIUS shared secret)
    RAD->>DB: SELECT * FROM internal_users WHERE username = ?
    RAD->>RAD: bcrypt.verify(password, hash)
    
    alt Password Valid
        RAD->>PE: gRPC EvaluatePolicy(username, groups, device)
        PE-->>RAD: {VLAN=200, SGT=10}
        RAD->>NAD: Access-Accept + VLAN + SGT attributes
        RAD->>DB: INSERT INTO sessions (status='active')
    else Password Invalid
        RAD->>NAD: Access-Reject
        RAD->>DB: UPDATE internal_users SET failed_attempts++
    end
```

### 3.3 AI Agent Authentication Flow

```mermaid
sequenceDiagram
    participant AGENT as AI Agent
    participant NAD as Network Switch
    participant RAD as NeuraNAC RADIUS
    participant DB as PostgreSQL
    participant PE as Policy Engine

    AGENT->>NAD: 802.1X EAP-Start
    NAD->>RAD: Access-Request (User-Name="agent:ml-pipeline-01")
    RAD->>RAD: Detect "agent:" prefix
    RAD->>DB: SELECT * FROM ai_agents WHERE name='ml-pipeline-01'
    
    alt Agent Found & Active
        RAD->>DB: Check delegation_scope, bandwidth_limit
        RAD->>PE: EvaluatePolicy(agent_type, model_type, data_classification)
        PE-->>RAD: {VLAN=300, SGT=50, bandwidth=1000Mbps}
        RAD->>NAD: Access-Accept + AI-specific attributes
        RAD->>DB: Create AI session record
    else Agent Not Found
        RAD->>NAD: Access-Reject
        RAD->>DB: Log unauthorized AI agent attempt
    end
```

### 3.4 Guest Portal Flow

```mermaid
sequenceDiagram
    participant GUEST as Guest Device
    participant NAD as Switch
    participant RAD as NeuraNAC RADIUS
    participant API as API Gateway
    participant DB as PostgreSQL

    GUEST->>NAD: Connect (no 802.1X)
    NAD->>RAD: Access-Request (MAB)
    RAD->>DB: MAC not found
    RAD->>NAD: Access-Accept (Guest VLAN, redirect ACL)
    
    GUEST->>API: GET /guest/portal/:id (Captive Portal)
    API->>API: Bot Detection (honeypot, timing, header analysis)
    GUEST->>API: POST /guest/register (name, email, sponsor)
    API->>DB: Create guest_account (random password, expiry)
    API-->>GUEST: Credentials displayed
    
    GUEST->>NAD: Re-authenticate with guest credentials
    NAD->>RAD: Access-Request (PAP)
    RAD->>DB: Verify guest credentials
    RAD->>NAD: Access-Accept (Guest-Authorized VLAN)
```

### 3.5 Posture Assessment Flow

```mermaid
sequenceDiagram
    participant EP as Endpoint
    participant NAD as Switch
    participant RAD as NeuraNAC RADIUS
    participant API as API Gateway
    participant DB as PostgreSQL

    EP->>NAD: 802.1X Auth (succeeds)
    NAD->>RAD: Access-Accept (Posture-Pending VLAN)
    
    EP->>API: POST /api/v1/posture/assess {mac, checks: [...]}
    
    API->>API: Evaluate 8 Check Types
    Note over API: antivirus, firewall, disk_encryption,<br/>os_patch, screen_lock, jailbroken,<br/>certificate, agent_version
    
    API->>DB: Store posture_results
    
    alt All Checks Pass
        API->>RAD: CoA → Move to Production VLAN
        API-->>EP: {status: "compliant", vlan: 100}
    else Some Checks Fail
        API->>RAD: CoA → Move to Remediation VLAN
        API-->>EP: {status: "noncompliant", failed: ["antivirus"]}
    end
```

### 3.6 SIEM Integration Flow

```mermaid
graph LR
    subgraph NeuraNAC_Events["NeuraNAC Event Sources"]
        AUTH["Auth Events"]
        POLICY["Policy Decisions"]
        POSTURE["Posture Results"]
        AI["AI Detections"]
        AUDIT["Audit Actions"]
    end

    subgraph Forwarding["SIEM Router (siem.py)"]
        FORMAT["Format: Syslog / CEF"]
        FILTER["Filter by severity/type"]
        TRANSPORT["Transport: UDP/TCP/TLS"]
    end

    subgraph Targets["SIEM Targets"]
        SPLUNK["Splunk"]
        QRADAR["IBM QRadar"]
        SENTINEL["Azure Sentinel"]
        ELK["Elastic / ELK"]
    end

    AUTH --> FORMAT
    POLICY --> FORMAT
    POSTURE --> FORMAT
    AI --> FORMAT
    AUDIT --> FORMAT
    FORMAT --> FILTER
    FILTER --> TRANSPORT
    TRANSPORT --> SPLUNK
    TRANSPORT --> QRADAR
    TRANSPORT --> SENTINEL
    TRANSPORT --> ELK
```

---

## 4. Integration Architecture

### 4.1 Identity Source Integration

```mermaid
graph TB
    subgraph NeuraNAC_IDP["NeuraNAC Identity Integration"]
        ROUTER["identity_sources.py Router"]
        
        subgraph Connectors["Identity Connectors"]
            AD_CONN["Active Directory<br/>LDAP Bind + Search<br/>User/Group Sync"]
            LDAP_CONN["LDAP Server<br/>Bind + Search<br/>Attribute Mapping"]
            SAML_CONN["SAML 2.0 SSO<br/>AuthnRequest Generation<br/>ACS Response Parsing"]
            OAUTH_CONN["OAuth2<br/>Authorization Code Flow<br/>Token Exchange"]
            INT_CONN["Internal DB<br/>bcrypt Password<br/>Local Users"]
        end
    end

    AD_EXT["Active Directory Server"] <-->|"LDAPS :636"| AD_CONN
    LDAP_EXT["LDAP Server"] <-->|"LDAP :389"| LDAP_CONN
    SAML_EXT["SAML IdP (Okta, Azure AD)"] <-->|"HTTPS POST"| SAML_CONN
    OAUTH_EXT["OAuth Provider (Google, GitHub)"] <-->|"HTTPS"| OAUTH_CONN
    PG_EXT[("PostgreSQL")] <--> INT_CONN

    ROUTER --> AD_CONN
    ROUTER --> LDAP_CONN
    ROUTER --> SAML_CONN
    ROUTER --> OAUTH_CONN
    ROUTER --> INT_CONN
```

### 4.2 NAD Integration Matrix

| Vendor        | Device Types                        | RADIUS | TACACS+ | RadSec | CoA | MAB | 802.1X | SNMPv3 |
| ------------- | ----------------------------------- | ------ | ------- | ------ | --- | --- | ------ | ------ |
| **Cisco**     | Catalyst, Nexus, WLC, ASA, ISR      | ✅     | ✅      | ✅     | ✅  | ✅  | ✅     | ✅     |
| **Aruba/HPE** | CX, Instant AP, Mobility Controller | ✅     | ✅      | ✅     | ✅  | ✅  | ✅     | ✅     |
| **Juniper**   | EX, QFX, SRX, Mist AP               | ✅     | ✅      | ✅     | ✅  | ✅  | ✅     | ✅     |
| **Fortinet**  | FortiSwitch, FortiGate, FortiAP     | ✅     | ❌      | ❌     | ✅  | ✅  | ✅     | ✅     |
| **Palo Alto** | PA Series (VPN/Firewall)            | ✅     | ✅      | ❌     | ✅  | ❌  | ✅     | ❌     |
| **Meraki**    | MS Switches, MR APs                 | ✅     | ❌      | ❌     | ✅  | ✅  | ✅     | ❌     |
| **Ruckus**    | ICX, SmartZone, Unleashed           | ✅     | ❌      | ❌     | ✅  | ✅  | ✅     | ✅     |
| **Dell**      | PowerSwitch (OS10)                  | ✅     | ✅      | ❌     | ✅  | ✅  | ✅     | ✅     |
| **Generic**   | Any RADIUS-compliant device         | ✅     | —       | —      | ⚠️ | ✅  | ✅     | —      |

> ⚠️ CoA support varies by vendor implementation. NeuraNAC sends standard RFC 5176 Disconnect-Request.

### 4.3 Event Bus (NATS JetStream) Topics

| Subject               | Publisher     | Subscribers             | Payload                               |
| --------------------- | ------------- | ----------------------- | ------------------------------------- |
| `neuranac.auth.success`    | RADIUS Server | API GW, AI Engine, SIEM | Session ID, username, NAS-IP, VLAN    |
| `neuranac.auth.failure`    | RADIUS Server | API GW, AI Engine, SIEM | Username, NAS-IP, reason              |
| `neuranac.auth.accounting` | RADIUS Server | API GW                  | Session ID, acct-type, bytes in/out   |
| `neuranac.policy.decision` | Policy Engine | API GW, SIEM            | Policy ID, result, attributes         |
| `neuranac.ai.risk`         | AI Engine     | RADIUS Server, API GW   | Endpoint MAC, risk score, level       |
| `neuranac.ai.shadow`       | AI Engine     | API GW, SIEM            | Detection details, service name       |
| `neuranac.posture.result`  | API Gateway   | RADIUS Server           | Endpoint MAC, compliance status       |
| `neuranac.coa.trigger`     | API Gateway   | RADIUS Server           | NAS-IP, session ID, action            |
| `neuranac.sync.change`     | Sync Engine   | Peer Sync Engine        | Table, row ID, operation, data        |
| `neuranac.audit.action`    | API Gateway   | SIEM                    | Admin user, action, resource, details |

---

## 5. Database Schema Design

### 5.1 Schema Overview

NeuraNAC uses a single PostgreSQL 16 database with **45+ tables** organized into functional domains:

```mermaid
erDiagram
    tenants ||--o{ admin_users : has
    tenants ||--o{ network_devices : has
    tenants ||--o{ identity_sources : has
    tenants ||--o{ policy_sets : has
    tenants ||--o{ endpoints : has
    tenants ||--o{ sessions : has
    tenants ||--o{ ai_agents : has

    policy_sets ||--o{ policy_rules : contains
    policy_rules }o--|| auth_profiles : references

    identity_sources ||--o{ internal_users : stores
    endpoints ||--o{ posture_results : assessed_by
    sessions }o--|| endpoints : for
    sessions }o--|| network_devices : via

    ai_agents ||--o{ ai_data_flow_policies : governed_by
    ai_agents ||--o{ ai_risk_scores : scored_by
    
    endpoints ||--o{ ai_shadow_detections : flagged_by

    privacy_subjects ||--o{ privacy_consent : has
    privacy_subjects ||--o{ data_export_requests : requests
```

### 5.2 Table Domains

| Domain             | Tables                                                  | Key Purpose                              |
| ------------------ | ------------------------------------------------------- | ---------------------------------------- |
| **Core**           | `tenants`, `admin_roles`, `admin_users`, `audit_logs`   | Multi-tenancy, RBAC, audit trail         |
| **Licensing**      | `licenses`, `feature_flags`                             | License management, feature toggles      |
| **Network**        | `network_devices`                                       | NAD inventory (IP, vendor, secret, CoA)  |
| **Identity**       | `identity_sources`, `internal_users`, `user_groups`     | Identity providers, local users, groups  |
| **Certificates**   | `certificate_authorities`, `certificates`               | X.509 CA hierarchy, expiry tracking      |
| **Endpoints**      | `endpoints`, `endpoint_profiles`                        | Device inventory, AI-generated profiles  |
| **Policy**         | `policy_sets`, `policy_rules`, `auth_profiles`          | Policy evaluation rules, result profiles |
| **Segmentation**   | `security_group_tags`, `sgacls`, `policy_matrix`        | TrustSec SGTs, ACLs, adaptive matrix     |
| **Sessions**       | `sessions`, `accounting_records`                        | Active/historical RADIUS sessions        |
| **Guest/BYOD**     | `guest_portals`, `guest_accounts`, `byod_registrations` | Guest lifecycle, BYOD cert provisioning  |
| **Posture**        | `posture_policies`, `posture_results`                   | Compliance checks, assessment results    |
| **Sync**           | `sync_journal`, `sync_state`                            | Change tracking, replication state       |
| **AI**             | `ai_agents`, `ai_data_flow_policies`, `ai_risk_scores`  | AI governance, risk scores, shadow AI    |
| **Data Retention** | `data_retention_policies`                               | Automated data lifecycle management      |
| **Privacy**        | `privacy_subjects`, `privacy_consent`, `data_exports`   | GDPR/CCPA compliance                     |

---

## 6. Security Architecture

```mermaid
graph TB
    subgraph Perimeter["Security Perimeter"]
        TLS["TLS 1.2+ Termination"]
        RATE["Rate Limiter<br/>(Redis Token Bucket)"]
        VALIDATE["Input Validation<br/>(SQLi + XSS Detection)"]
    end

    subgraph AuthZ["Authentication & Authorization"]
        JWT["JWT Tokens<br/>(Access + Refresh)"]
        RBAC["Role-Based Access Control<br/>(admin, operator, viewer)"]
        TENANT["Tenant Isolation<br/>(Row-Level Filtering)"]
    end

    subgraph DataProtection["Data Protection"]
        BCRYPT["bcrypt Password Hashing"]
        AUDIT_CHAIN["Audit Log Hash Chain<br/>(Tamper Detection)"]
        PRIVACY["GDPR/CCPA<br/>(Erasure + Portability)"]
    end

    subgraph Headers["OWASP Security Headers"]
        CSP["Content-Security-Policy"]
        HSTS["Strict-Transport-Security"]
        XFRAME["X-Frame-Options: DENY"]
        XCTYPE["X-Content-Type-Options: nosniff"]
        REFERRER["Referrer-Policy: strict-origin"]
    end

    TLS --> RATE --> VALIDATE --> JWT --> RBAC --> TENANT
```

**Middleware stack order (applied to every request):**
1. CORS — Cross-origin resource sharing
2. Security Headers — OWASP recommended headers
3. Prometheus Metrics — Request counting and latency
4. Input Validation — SQL injection, XSS pattern detection, body size limits
5. Rate Limiter — Per-IP token bucket (configurable)
6. JWT Authentication — Token decode, user context extraction
7. Tenant Isolation — Tenant ID from JWT injected into DB queries

---

## 7. Deployment Architecture

### 7.1 Development (Docker Compose)

```mermaid
graph TB
    subgraph DockerCompose["docker-compose.yml — 9 Containers"]
        PG["neuranac-postgres<br/>PostgreSQL 16 Alpine"]
        RD["neuranac-redis<br/>Redis 7 Alpine"]
        NT["neuranac-nats<br/>NATS 2.10 Alpine"]
        RAD["neuranac-radius<br/>Go Binary"]
        API["neuranac-api<br/>Python + uvicorn"]
        POL["neuranac-policy<br/>Python + uvicorn"]
        AIE["neuranac-ai<br/>Python + uvicorn"]
        SYN["neuranac-sync<br/>Go Binary"]
        WEB["neuranac-web<br/>nginx + React Build"]
    end

    PG -.->|"healthcheck"| RAD
    PG -.->|"healthcheck"| API
    PG -.->|"healthcheck"| POL
    RD -.->|"healthcheck"| RAD
    RD -.->|"healthcheck"| API
    NT -.->|"healthcheck"| RAD
    NT -.->|"healthcheck"| SYN
    API -.->|"depends_on"| WEB
```

### 7.2 Production (Kubernetes + Helm)

```mermaid
graph TB
    subgraph K8s["Kubernetes Cluster"]
        subgraph NS["Namespace: neuranac"]
            ING["Ingress Controller<br/>(nginx / ALB)"]
            
            subgraph Deployments["Deployments"]
                RAD_D["radius-server<br/>Replicas: 2"]
                API_D["api-gateway<br/>Replicas: 3"]
                POL_D["policy-engine<br/>Replicas: 2"]
                AI_D["ai-engine<br/>Replicas: 2"]
                SYN_D["sync-engine<br/>Replicas: 1 per node"]
                WEB_D["web<br/>Replicas: 2"]
            end
            
            subgraph Services["ClusterIP Services"]
                RAD_S["radius-svc"]
                API_S["api-svc"]
                POL_S["policy-svc"]
                AI_S["ai-svc"]
                SYN_S["sync-svc"]
                WEB_S["web-svc"]
            end
        end
        
        subgraph External_DB["External (Managed)"]
            PG_EXT["PostgreSQL<br/>(RDS / CloudSQL)"]
            RD_EXT["Redis<br/>(ElastiCache / Memorystore)"]
            NT_EXT["NATS<br/>(Self-hosted or Synadia)"]
        end
    end

    ING --> WEB_S
    ING --> API_S
    RAD_S --> PG_EXT
    API_S --> PG_EXT
    API_S --> RD_EXT
```

### 7.3 On-Premises Twin-Node HA

```mermaid
graph LR
    subgraph SiteA["Site A (Primary)"]
        NeuraNACA["NeuraNAC Node A<br/>(All services)"]
        PGA[("PostgreSQL A")]
    end

    subgraph SiteB["Site B (Secondary)"]
        NeuraNACB["NeuraNAC Node B<br/>(All services)"]
        PGB[("PostgreSQL B")]
    end

    NeuraNACA <-->|"gRPC Sync :9090<br/>Bidirectional Replication"| NeuraNACB
    PGA <-->|"Sync Journal"| NeuraNACA
    PGB <-->|"Sync Journal"| NeuraNACB

    LB["Load Balancer / DNS"] --> NeuraNACA
    LB --> NeuraNACB
```

---

## 8. Network Topology

### Typical Enterprise Deployment

```mermaid
graph TB
    subgraph Campus["Campus Network"]
        subgraph Access["Access Layer"]
            SW1["Access Switch 1<br/>(Cisco Catalyst)"]
            SW2["Access Switch 2<br/>(Aruba CX)"]
            AP1["Wireless AP<br/>(Cisco/Aruba)"]
        end
        
        subgraph Distribution["Distribution Layer"]
            DSW["Distribution Switch"]
        end
    end

    subgraph DC["Data Center / Cloud"]
        subgraph NeuraNAC_DC["NeuraNAC Platform"]
            RAD_DC["RADIUS :1812"]
            API_DC["API :8080"]
            DASH["Dashboard :3001"]
        end
        
        subgraph Identity["Identity"]
            AD_DC["Active Directory"]
        end
    end

    subgraph Endpoints["Endpoints"]
        LAPTOP["Corporate Laptops<br/>(802.1X EAP-TLS)"]
        PRINTER["Printers / IoT<br/>(MAB)"]
        PHONE["IP Phones<br/>(CDP/LLDP + MAB)"]
        GUEST_DEV["Guest Devices<br/>(Captive Portal)"]
        AI_AGENT["AI Agents / ML Workloads<br/>(Agent Auth)"]
    end

    LAPTOP -->|"EAP-TLS"| SW1
    PRINTER -->|"MAB"| SW1
    PHONE -->|"MAB + CDP"| SW2
    GUEST_DEV -->|"HTTP Redirect"| AP1
    AI_AGENT -->|"Agent Auth"| SW2
    
    SW1 -->|"RADIUS"| RAD_DC
    SW2 -->|"RADIUS"| RAD_DC
    AP1 -->|"RADIUS"| RAD_DC
    RAD_DC -->|"LDAP"| AD_DC
    DSW --> SW1
    DSW --> SW2
    DSW --> AP1
```

---

## 9. Legacy NAC Integration Architecture

NeuraNAC can operate alongside Legacy NAC 3.4+ via API-based synchronization. This is **not** a node-level join — NeuraNAC connects to NeuraNAC's public APIs (ERS, Event Stream, MnT) to share context and enable migration.

### 9.1 NeuraNAC Coexistence Topology

```mermaid
graph TB
    subgraph NeuraNAC_Cluster["Legacy NAC Cluster"]
        PPAN["Primary PAN<br/>:443 / :9060"]
        PSN["Policy Service Node<br/>RADIUS :1812"]
        MNT["MnT Node<br/>Monitoring"]
        EVENT_STREAM["Event Stream Controller<br/>:8910"]
    end

    subgraph NeuraNAC_Platform["NeuraNAC Platform"]
        NeuraNAC_ADAPTER["NeuraNAC Adapter<br/>(legacy_nac router)"]
        API_GW["API Gateway<br/>:8080"]
        RADIUS["RADIUS Server<br/>:1812"]
        AI_ENG["AI Engine<br/>:8081"]
        PG["PostgreSQL<br/>65 tables"]
        WEB["Dashboard<br/>:3001"]
    end

    subgraph NADs["Network Access Devices"]
        NeuraNAC_NADS["NeuraNAC-Managed NADs"]
        NeuraNAC_NADS["NeuraNAC-Managed NADs"]
    end

    NeuraNAC_NADS -->|"RADIUS"| PSN
    NeuraNAC_NADS -->|"RADIUS"| RADIUS

    NeuraNAC_ADAPTER -->|"ERS REST API<br/>GET /ers/config/*"| PPAN
    NeuraNAC_ADAPTER -->|"Event Stream STOMP/WS<br/>Session events"| EVENT_STREAM
    NeuraNAC_ADAPTER -->|"MnT API<br/>Active sessions"| MNT
    NeuraNAC_ADAPTER --> PG
    NeuraNAC_ADAPTER --> API_GW
    WEB --> API_GW
    AI_ENG --> PG
```

### 9.2 Legacy Sync Data Flow

```mermaid
sequenceDiagram
    participant ADMIN as NeuraNAC Admin
    participant API as API Gateway
    participant NeuraNAC as NeuraNAC PPAN
    participant DB as PostgreSQL

    ADMIN->>API: POST /api/v1/legacy-nac/connections (hostname, creds)
    API->>DB: INSERT legacy_nac_connections
    API->>DB: INSERT legacy_nac_sync_state (6 entity types)
    API-->>ADMIN: Connection created

    ADMIN->>API: POST /api/v1/legacy-nac/connections/{id}/test
    API->>NeuraNAC: GET /ers/config/networkdevice?size=1
    NeuraNAC-->>API: 200 OK
    API->>DB: UPDATE connection_status = 'connected'
    API-->>ADMIN: Connected

    ADMIN->>API: POST /api/v1/legacy-nac/connections/{id}/sync
    API->>DB: INSERT legacy_nac_sync_log (status=started)
    
    loop For each entity type
        API->>NeuraNAC: GET /ers/config/{type}?page=N&size=100
        NeuraNAC-->>API: {SearchResult: {resources: [...]}}
        API->>DB: UPSERT into NeuraNAC tables
        API->>DB: UPSERT legacy_nac_entity_map (legacy_nac_id → neuranac_id)
        API->>DB: UPDATE legacy_nac_sync_state (items_synced)
    end
    
    API->>DB: UPDATE legacy_nac_sync_log (status=success)
    API-->>ADMIN: Sync complete (316 entities)
```

### 9.3 NeuraNAC Entity Mapping

| Legacy ERS Endpoint                   | NeuraNAC Target Table         | Sync Direction | Key Fields              |
| ---------------------------------- | ------------------------ | -------------- | ----------------------- |
| `/ers/config/networkdevice`        | `network_devices`        | NeuraNAC → NeuraNAC      | IP, name, RADIUS config |
| `/ers/config/internaluser`         | `admin_users`            | NeuraNAC → NeuraNAC      | username, group         |
| `/ers/config/endpoint`             | `endpoints`              | NeuraNAC → NeuraNAC      | MAC, profile            |
| `/ers/config/identitygroup`        | `identity_sources`       | NeuraNAC → NeuraNAC      | name, parent            |
| `/ers/config/sgt`                  | `security_group_tags`    | NeuraNAC → NeuraNAC      | name, value             |
| `/ers/config/authorizationprofile` | `authorization_profiles` | NeuraNAC → NeuraNAC      | VLAN, DACL, SGT         |

### 9.4 Database Tables (Legacy NAC Integration)

```mermaid
erDiagram
    legacy_nac_connections {
        UUID id PK
        UUID tenant_id FK
        VARCHAR hostname
        INT ers_port
        BOOLEAN event-stream_enabled
        VARCHAR deployment_mode
        VARCHAR connection_status
    }

    legacy_nac_sync_state {
        UUID id PK
        UUID connection_id FK
        VARCHAR entity_type
        VARCHAR last_sync_status
        INT items_synced
        INT items_total
    }

    legacy_nac_sync_log {
        UUID id PK
        UUID connection_id FK
        VARCHAR sync_type
        VARCHAR status
        INT items_created
        INT duration_ms
    }

    legacy_nac_entity_map {
        UUID id PK
        UUID connection_id FK
        VARCHAR entity_type
        VARCHAR legacy_nac_id
        UUID neuranac_id
        VARCHAR sync_hash
    }

    legacy_nac_connections ||--o{ legacy_nac_sync_state : "has sync state"
    legacy_nac_connections ||--o{ legacy_nac_sync_log : "has sync logs"
    legacy_nac_connections ||--o{ legacy_nac_entity_map : "has entity mappings"
```

> **Full design document:** See [NeuraNAC_INTEGRATION.md](NeuraNAC_INTEGRATION.md) for the complete technical design, migration runbook, Event Stream integration details, and FAQ for tech leads.
