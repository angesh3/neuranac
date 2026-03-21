# NeuraNAC Development Phases — Planning to Production

This document details all 17 phases of NeuraNAC development, from initial scaffold through production-ready hardening and legacy NAC integration. Each phase describes the objectives, deliverables, key technical decisions, and files created or modified.

---

## Phase Overview

| #   | Phase                       | Status      | Key Deliverable                                                           |
| --- | --------------------------- | ----------- | ------------------------------------------------------------------------- |
| P1  | Scaffold & Infrastructure   | ✅ Complete | Docker Compose, Dockerfiles, project structure                            |
| P2  | Database & Data Model       | ✅ Complete | 65 tables (V001+V002+V003+V004), ORM models, seed data                    |
| P3A | RADIUS Core                 | ✅ Complete | PAP auth with real user lookup + bcrypt                                   |
| P3B | RADIUS Full Protocol        | ✅ Complete | EAP-TLS/TTLS/PEAP state machines, TACACS+, AI agent auth, CoA             |
| P4  | Policy Engine + API         | ✅ Complete | Full CRUD, 14 operators, gRPC wiring                                      |
| P5  | Identity & Certificates     | ✅ Complete | LDAP/AD sync, X.509 cert gen, SAML SSO, OAuth2                            |
| P6  | Endpoints & Profiling       | ✅ Complete | AI profiling, MAC lookup, NAD auto-discovery                              |
| P7  | Network Segmentation        | ✅ Complete | SGT CRUD, adaptive policy matrix, VLAN assignment                         |
| P8  | Guest & BYOD                | ✅ Complete | Guest portals, sponsor groups, BYOD cert provisioning                     |
| P9  | Posture Assessment          | ✅ Complete | 8 check types, real evaluation, DB storage                                |
| P10 | Sync Engine                 | ✅ Complete | DB-backed journal, peer connection, sync status                           |
| P11 | Full REST API               | ✅ Complete | 23 routers including SIEM, webhooks, privacy, NeuraNAC                         |
| P12 | Web Dashboard               | ✅ Complete | 23 React pages with real content                                          |
| P13 | Context Bus & Integrations  | ✅ Complete | SIEM syslog/CEF, SOAR webhooks, diagnostics                               |
| P14 | Monitoring & Observability  | ✅ Complete | Prometheus metrics, Grafana dashboard, audit reports                      |
| P15 | AI Engine                   | ✅ Complete | 7 modules: profiler, risk, shadow, NLP, troubleshooter, anomaly, drift    |
| P16 | Hardening, Testing & Docs   | ✅ Complete | 80+ tests, security middleware, CI/CD, documentation                      |
| P17 | Legacy NAC Integration & Migration | ✅ Complete | Legacy ERS API + Event Stream adapter, 4 DB tables, dashboard, migration framework |

---

## Phase 1: Scaffold & Infrastructure

**Objective:** Set up the monorepo structure, Docker containers, and development tooling.

**Deliverables:**
- Monorepo directory structure (`services/`, `web/`, `proto/`, `database/`, `deploy/`)
- 6 Dockerfiles (one per service) with multi-stage builds
- `docker-compose.yml` with 9 services (3 infrastructure + 6 application)
- `Makefile` for common operations (build, test, lint, proto, docker)
- `.env.example` with all environment variables documented
- `scripts/setup.sh` — one-command dev environment setup
- `.gitignore` configured for Go, Python, Node, IDE files
- Port mapping strategy to avoid conflicts

**Key Decisions:**
- Go for data-plane services (RADIUS, Sync) — performance critical, low latency
- Python FastAPI for control-plane services — rapid development, rich ecosystem
- React 18 + TypeScript + Vite for dashboard — modern, fast HMR
- NATS JetStream over Kafka — simpler operations, sufficient for event volumes
- PostgreSQL over CockroachDB — mature ecosystem, JSONB support
- Redis for caching + rate limiting — proven, low-latency

**Files Created:**
```
deploy/docker-compose.yml
services/radius-server/Dockerfile
services/api-gateway/Dockerfile
services/policy-engine/Dockerfile
services/ai-engine/Dockerfile
services/sync-engine/Dockerfile
web/Dockerfile
Makefile
.env.example
.gitignore
scripts/setup.sh
```

---

## Phase 2: Database & Data Model

**Objective:** Design and implement the complete database schema supporting multi-tenancy, privacy, and AI-aware features.

**Deliverables:**
- `V001_initial_schema.sql` — 45+ tables with indexes
- Multi-tenant architecture with `tenant_id` on all business tables
- UUID primary keys using `uuid-ossp` extension
- JSONB columns for flexible configuration storage
- Seed data for default tenant, test users, NADs, feature flags
- Alembic migration framework for Python services

**Schema Domains (45+ tables):**
1. **Core:** tenants, admin_roles, admin_users, audit_logs, bootstrap_state
2. **Licensing:** licenses, feature_flags
3. **Network:** network_devices
4. **Identity:** identity_sources, internal_users, user_groups, group_memberships
5. **Certificates:** certificate_authorities, certificates
6. **Endpoints:** endpoints, endpoint_profiles
7. **Policy:** policy_sets, policy_rules, auth_profiles
8. **Segmentation:** security_group_tags, sgacls, policy_matrix
9. **Sessions:** sessions, accounting_records
10. **Guest/BYOD:** guest_portals, guest_accounts, byod_registrations
11. **Posture:** posture_policies, posture_results
12. **Sync:** sync_journal, sync_state
13. **AI:** ai_agents, ai_services, ai_data_flow_policies, ai_risk_scores, ai_shadow_detections
14. **Data Retention:** data_retention_policies
15. **Privacy:** privacy_subjects, privacy_consent, data_export_requests

**Files Created:**
```
database/migrations/V001_initial_schema.sql
database/seeds/seed_data.sql
services/api-gateway/app/models/
services/api-gateway/app/database/session.py
services/api-gateway/app/database/redis.py
services/api-gateway/app/bootstrap.py
services/api-gateway/alembic.ini
services/api-gateway/alembic/env.py
```

---

## Phase 3A: RADIUS Core Authentication

**Objective:** Implement the foundational RADIUS protocol handling with PAP authentication.

**Deliverables:**
- UDP listener on :1812 (auth) and :1813 (accounting)
- RADIUS packet encode/decode (RFC 2865)
- RADIUS dictionary with 50+ standard attributes
- PAP authentication with real user lookup from PostgreSQL
- bcrypt password verification
- Access-Accept / Access-Reject response building
- Session creation on successful auth
- NATS event publishing for auth events

**Key Technical Details:**
- Shared secret decryption for User-Password attribute
- Proper RADIUS authenticator calculation
- Connection pooling to PostgreSQL and Redis
- Structured logging with `zap`

**Files Created:**
```
services/radius-server/cmd/server/main.go
services/radius-server/internal/config/config.go
services/radius-server/internal/handler/handler.go
services/radius-server/internal/radius/server.go
services/radius-server/internal/radius/dictionary.go
services/radius-server/internal/store/store.go
services/radius-server/go.mod
```

---

## Phase 3B: RADIUS Full Protocol Suite

**Objective:** Implement all enterprise-grade RADIUS authentication methods and extensions.

**Deliverables:**

### EAP-TLS (RFC 5216)
- Full state machine: `Start → ServerHello → ClientCert → Verify → Success`
- X.509 certificate validation against stored CAs
- TLS fragment reassembly for large certificates
- Session key derivation for MPPE keys

### EAP-TTLS
- Outer TLS tunnel establishment
- Inner PAP/MSCHAPv2 authentication within tunnel
- Cryptobinding verification

### PEAP (Protected EAP)
- TLS tunnel with server-side certificate
- MSCHAPv2 inner authentication
- Session resumption support

### TACACS+
- TCP listener on :49
- Authentication (ASCII, PAP, CHAP)
- Authorization (command sets, privilege levels)
- Accounting (start, stop, update)
- Obfuscation per RFC 8907

### AI Agent Authentication
- Detection of `agent:` prefix in username
- Lookup in `ai_agents` table
- Delegation scope and bandwidth limit enforcement
- AI-specific VLAN/SGT assignment

### Change of Authorization (CoA)
- Disconnect-Request (RFC 5176) sender
- Triggered when risk score > 70
- NAS-IP and session identification
- UDP :3799 response listener

### RadSec (RADIUS over TLS)
- TLS listener on :2083 (RFC 6614)
- Certificate-based mutual authentication
- Full RADIUS protocol over TCP/TLS stream

**Files Modified/Created:**
```
services/radius-server/internal/handler/handler.go  (EAP state machines, AI agent auth)
services/radius-server/internal/store/store.go      (GetAIAgent, EvaluatePolicy)
services/radius-server/internal/coa/coa.go          (CoA sender)
services/radius-server/internal/radsec/radsec.go    (RadSec listener)
services/radius-server/internal/tacacs/tacacs.go    (TACACS+ handler)
```

---

## Phase 4: Policy Engine + API

**Objective:** Build the policy evaluation engine with gRPC interface and full CRUD REST API.

**Deliverables:**
- `PolicyEvaluator` with 14 comparison operators
- gRPC server (:9091) for RADIUS server integration
- REST API (:8082) for admin evaluation and management
- Policy loading from PostgreSQL (`policy_sets` + `policy_rules`)
- AI-aware conditions (risk score, shadow AI, agent type)
- Hot-reload of policies via `/api/v1/reload`

**14 Operators:**
`equals`, `not_equals`, `contains`, `starts_with`, `ends_with`, `in`, `not_in`, `matches` (regex), `greater_than`, `less_than`, `between`, `is_true`, `is_false`

**gRPC Integration:**
- Generated protobuf stubs from `proto/policy.proto`
- Fallback `GenericRpcHandler` when stubs not available
- Request/response with tenant isolation

**Files Created:**
```
services/policy-engine/app/main.py
services/policy-engine/app/engine.py
services/policy-engine/app/grpc_server.py
services/policy-engine/requirements.txt
services/policy-engine/Dockerfile
proto/policy.proto
```

---

## Phase 5: Identity Sources & Certificates

**Objective:** Integrate all enterprise identity sources and implement certificate lifecycle management.

**Deliverables:**

### Identity Sources
- **Active Directory / LDAP** — Bind, search, user/group sync, test connection
- **SAML 2.0 SSO** — AuthnRequest generation, ACS endpoint for response parsing
- **OAuth2** — Authorization code flow initiate + callback with token exchange
- **Internal DB** — Local user/password management with bcrypt

### Certificate Management
- X.509 CA hierarchy management
- Certificate generation (RSA/EC keys, configurable validity)
- Certificate listing with expiry tracking
- Support for server, client, and CA certificate types

**Files Created/Modified:**
```
services/api-gateway/app/routers/identity_sources.py  (SAML + OAuth2 flows)
services/api-gateway/app/routers/certificates.py
```

---

## Phase 6: Endpoints & Device Profiling

**Objective:** Build the endpoint inventory with AI-powered device classification and NAD auto-discovery.

**Deliverables:**
- Endpoint CRUD with MAC, IP, OS, vendor, status tracking
- AI profiling integration (calls AI Engine `/api/v1/profile`)
- MAC address normalization and lookup
- **NAD Auto-Discovery:**
  - Subnet scanning (CIDR-based)
  - Port probing (RADIUS 1812, SNMP 161, SSH 22, HTTP 80/443)
  - OUI-based vendor guessing from MAC prefix
  - Automatic NAD registration from discovered devices

**Files Created/Modified:**
```
services/api-gateway/app/routers/endpoints.py
services/api-gateway/app/routers/network_devices.py  (auto-discovery)
```

---

## Phase 7: Network Segmentation

**Objective:** Implement TrustSec-style segmentation with SGTs and adaptive policy matrix.

**Deliverables:**
- Security Group Tag (SGT) CRUD with tag value, name, description
- SGT ACL management (source SGT → destination SGT → action)
- Adaptive policy matrix (returns full SGT-to-SGT mapping)
- AI-aware matrix that factors risk scores into segmentation decisions
- VLAN assignment tied to authentication results via policy engine

**Files Created:**
```
services/api-gateway/app/routers/segmentation.py
```

---

## Phase 8: Guest & BYOD

**Objective:** Full guest lifecycle and BYOD device onboarding.

**Deliverables:**

### Guest Portals
- Customizable portal CRUD (branding, fields, terms)
- **Bot detection:** honeypot fields, timing analysis, header verification
- Guest account creation with random password generation
- Sponsor groups with approval workflows
- Account expiry enforcement

### BYOD
- Self-registration portal
- Certificate provisioning for BYOD devices
- Device type detection and policy assignment

**Files Created:**
```
services/api-gateway/app/routers/guest.py
```

---

## Phase 9: Posture Assessment

**Objective:** Real-time endpoint compliance evaluation with 8 check types.

**Deliverables:**
- Posture policy definition (which checks to enforce)
- Real-time assessment endpoint
- **8 Check Types:**
  1. `antivirus` — AV installed and up-to-date
  2. `firewall` — Host firewall enabled
  3. `disk_encryption` — Full disk encryption (BitLocker/FileVault)
  4. `os_patch` — OS patch level within threshold
  5. `screen_lock` — Screen lock timeout configured
  6. `jailbroken` — Jailbreak/root detection
  7. `certificate` — Valid client certificate present
  8. `agent_version` — Posture agent meets minimum version
- Result storage in `posture_results` table
- CoA trigger for non-compliant endpoints (move to remediation VLAN)

**Files Created/Modified:**
```
services/api-gateway/app/routers/posture.py
```

---

## Phase 10: Sync Engine

**Objective:** Bidirectional configuration replication between twin nodes for on-premises HA.

**Deliverables:**
- gRPC server (:9090) for peer communication
- DB-backed `sync_journal` — tracks all config changes
- Journal processor — polls undelivered entries, streams to peer
- Peer connection management with automatic reconnection
- Health HTTP server (:9100) with `/health` and `/sync/status`
- Manual sync trigger via `/sync/trigger`
- Conflict resolution (last-writer-wins with timestamp comparison)

**Sync Status Response:**
```json
{
  "node_id": "twin-a",
  "peer_connected": true,
  "peer_node_id": "twin-b",
  "pending_outbound": 0,
  "pending_inbound": 0,
  "last_sync_at": "2026-02-20T21:55:00Z",
  "bytes_synced": 1048576,
  "uptime_seconds": 3600
}
```

**Files Created/Modified:**
```
services/sync-engine/cmd/sync/main.go
services/sync-engine/go.mod
services/sync-engine/Dockerfile
proto/sync.proto
```

---

## Phase 11: Full REST API

**Objective:** Complete all 22 REST API routers for comprehensive platform management.

**Deliverables (22 routers):**

| Router           | File                  | Key Endpoints                                    |
| ---------------- | --------------------- | ------------------------------------------------ |
| Authentication   | `auth.py`             | login, refresh, logout, me                       |
| Policies         | `policies.py`         | CRUD for policy sets, rules, auth profiles       |
| Network Devices  | `network_devices.py`  | CRUD + auto-discovery                            |
| Endpoints        | `endpoints.py`        | CRUD + AI profiling                              |
| Sessions         | `sessions.py`         | List, filter, terminate                          |
| Identity Sources | `identity_sources.py` | CRUD + test + sync + SAML + OAuth                |
| Certificates     | `certificates.py`     | CA CRUD, cert generation, expiry check           |
| Segmentation     | `segmentation.py`     | SGT CRUD, ACLs, policy matrix                    |
| Guest            | `guest.py`            | Portals, accounts, sponsors                      |
| Posture          | `posture.py`          | Policies, assessment, results                    |
| AI Agents        | `ai_agents.py`        | Agent CRUD, revocation                           |
| AI Data Flow     | `ai_data_flow.py`     | Data flow policies, services                     |
| Nodes            | `nodes.py`            | Node listing, sync status                        |
| Admin            | `admin.py`            | Users, roles, tenants                            |
| Licenses         | `licenses.py`         | License CRUD                                     |
| Audit            | `audit.py`            | Audit log queries, reports                       |
| Diagnostics      | `diagnostics.py`      | System status, connectivity test, support bundle |
| Privacy          | `privacy.py`          | Subjects, consent, exports, erasure              |
| SIEM             | `siem.py`             | SIEM target CRUD, forwarding config              |
| Webhooks         | `webhooks.py`         | Webhook endpoint CRUD, test delivery             |
| Setup            | `setup.py`            | First-time setup wizard                          |
| Metrics          | `metrics.py`          | Prometheus /metrics endpoint                     |

---

## Phase 12: Web Dashboard

**Objective:** Build a production-quality React dashboard with 20+ pages covering all platform features.

**Deliverables:**
- React 18 + TypeScript + Vite + Tailwind CSS
- Protected routes with JWT authentication
- Sidebar navigation with 17 menu items
- Real-time data fetching with React Query

**Pages (20+):**

| Page             | File                     | Features                                       |
| ---------------- | ------------------------ | ---------------------------------------------- |
| Login            | `LoginPage.tsx`          | JWT authentication, remember me                |
| Dashboard        | `DashboardPage.tsx`      | Stats cards, session table, health polling     |
| Policies         | `PoliciesPage.tsx`       | Policy set/rule CRUD, condition builder        |
| Network Devices  | `NetworkDevicesPage.tsx` | NAD listing, add/edit, auto-discovery trigger  |
| Endpoints        | `EndpointsPage.tsx`      | Device inventory, profile status, OS breakdown |
| Sessions         | `SessionsPage.tsx`       | Active sessions, search, terminate             |
| Identity Sources | `IdentityPage.tsx`       | Connector CRUD, test, sync                     |
| Certificates     | `CertificatesPage.tsx`   | CA tree, cert listing, generate                |
| Segmentation     | `SegmentationPage.tsx`   | SGT CRUD, matrix view                          |
| Guest & BYOD     | `GuestPage.tsx`          | Portals, guest accounts, sponsor groups        |
| Posture          | `PosturePage.tsx`        | Policies, assessment results                   |
| AI Agents        | `AIAgentsPage.tsx`       | Agent registry, status, revocation             |
| AI Data Flow     | `AIDataFlowPage.tsx`     | Data flow policies, service inventory          |
| Shadow AI        | `ShadowAIPage.tsx`       | Detection logs, service signatures             |
| Twin Nodes       | `NodesPage.tsx`          | Node status, sync health, failover             |
| Audit Log        | `AuditPage.tsx`          | Searchable audit trail, export                 |
| Settings         | `SettingsPage.tsx`       | System configuration                           |
| Diagnostics      | `DiagnosticsPage.tsx`    | System status, connectivity test               |
| Privacy          | `PrivacyPage.tsx`        | GDPR/CCPA subjects, consent, exports, erasure  |
| Setup Wizard     | `SetupWizardPage.tsx`    | First-time configuration flow                  |
| Help Docs        | `HelpDocsPage.tsx`       | Searchable public-facing documentation         |
| AI Help          | `AIHelpPage.tsx`         | AI-assisted troubleshooting chatbot            |

---

## Phase 13: Context Bus & Integrations

**Objective:** Connect NeuraNAC to external security and operations systems.

**Deliverables:**

### SIEM Integration (`siem.py`)
- Syslog forwarding (RFC 5424)
- CEF (Common Event Format) for ArcSight/QRadar/Sentinel
- Configurable targets (host, port, protocol, format)
- Event filtering by severity and type
- Test connectivity endpoint

### Webhooks (`webhooks.py`)
- Webhook endpoint CRUD (URL, secret, events)
- HMAC-SHA256 payload signing
- Retry with exponential backoff
- SOAR playbook triggers on high-risk events
- Test delivery endpoint

### Diagnostics (`diagnostics.py`)
- System status check (all service health)
- Connectivity test (ping, port probe)
- AI troubleshooting integration
- Support bundle generation

---

## Phase 14: Monitoring & Observability

**Objective:** Production-grade monitoring with metrics, dashboards, and alerting.

**Deliverables:**

### Prometheus Metrics
- `metrics.py` middleware — request count, latency histograms, error rates
- `/metrics` endpoint in Prometheus exposition format
- Custom metrics: active sessions, auth success/failure rate, policy evaluation time

### Grafana Dashboard
- `monitoring/grafana-dashboard.json` — pre-built dashboard
- Panels: request rate, latency P50/P95/P99, error rate, active sessions
- Service health matrix

### Prometheus Configuration
- `monitoring/prometheus.yml` — scrape configs for all services
- 15-second scrape interval
- Job definitions for api-gateway, policy-engine, ai-engine

### Audit Reports
- Tamper-proof hash chain on audit log entries
- Audit report generation with date range filtering
- Admin action tracking with before/after state

---

## Phase 15: AI Engine

**Objective:** Build 7 AI/ML modules for intelligent network access control.

**Deliverables:**

### Module 1: Endpoint Profiler
- ONNX Runtime model for device classification
- Rule-based fallback when model not loaded
- Features: MAC OUI, DHCP hostname, HTTP user-agent, vendor

### Module 2: Risk Scorer
- **4-dimensional scoring** (0-100 composite):
  - Behavioral: failed auth count, time patterns
  - Identity: unknown user, missing groups
  - Endpoint: posture status, local LLM detection
  - AI Activity: shadow AI, delegation depth, data upload volume
- Risk levels: low (<30), medium (30-59), high (60-79), critical (80-100)
- Risk factors list with category and score contribution

### Module 3: Shadow AI Detector
- 14+ built-in signatures: OpenAI, Anthropic, Google AI, Hugging Face, Cohere, Stability AI, Midjourney, GitHub Copilot, Amazon Bedrock, Azure OpenAI, Replicate, Ollama, LM Studio, LocalAI
- Pattern matching on DNS, HTTP headers, TLS SNI
- Approved vs. unauthorized service classification
- Detection event logging to database

### Module 4: NLP Policy Assistant
- Natural language → policy rule translation
- LLM integration (Ollama/OpenAI compatible)
- Template-based fallback for common patterns
- Example: "Block all guest users after 6pm" → policy rule JSON

### Module 5: AI Troubleshooter
- Root-cause analysis for authentication failures
- Correlates: user, device, NAD, policy, posture, time
- Suggests remediation steps
- Historical pattern analysis

### Module 6: Anomaly Detector
- Baseline learning from historical authentication patterns
- Deviation scoring against baselines
- Alerts on: unusual auth times, new device locations, auth volume spikes
- Per-user and per-NAD anomaly tracking

### Module 7: Policy Drift Detector
- Compares current policy config against stored baselines
- Detects: added/removed rules, changed conditions, priority shifts
- Drift severity scoring
- Recommendation for policy reconciliation

---

## Phase 16: Hardening, Testing & Documentation

### Phase 16A: Test Suite

**79 tests across all services:**

| Service       | Test File            | Tests | Coverage                                                                        |
| ------------- | -------------------- | ----- | ------------------------------------------------------------------------------- |
| RADIUS Server | `dictionary_test.go` | 17    | PAP verify, MAC normalize, EAP parse, VSA parse, packet encode                  |
| Sync Engine   | `main_test.go`       | 5     | Health endpoint, sync status, no peer, defaults                                 |
| API Gateway   | `test_auth.py`       | 7     | Password hash, tokens, health, login, logout                                    |
| API Gateway   | `test_policies.py`   | 4     | List policies, endpoints, devices, sessions                                     |
| API Gateway   | `test_routers.py`    | 18    | All router endpoints (identity, certs, SGT, guest, posture, AI, privacy, audit) |
| Policy Engine | `test_engine.py`     | 15    | All 14 operators + case insensitivity                                           |
| AI Engine     | `test_risk.py`       | 7     | Low/high/medium risk, cap at 100, factors                                       |
| AI Engine     | `test_shadow.py`     | 6     | OpenAI, Copilot, local LLM, approved, no match                                  |

### Phase 16B: Security Hardening

- **SecurityHeadersMiddleware** (`security.py`)
  - Content-Security-Policy, X-Frame-Options: DENY, HSTS, X-Content-Type-Options, Referrer-Policy
- **InputValidationMiddleware** (`validation.py`)
  - Request body size limit (10MB)
  - SQL injection pattern detection (UNION, SELECT, DROP, etc.)
  - XSS pattern detection (<script>, onerror, javascript:)
  - Path traversal detection
  - Helper functions: `sanitize_string`, `validate_mac`, `validate_ip`, `validate_subnet`
- **Rate Limiting** — Redis token bucket, configurable per-tenant

### Phase 16C: CI/CD Pipeline

**GitHub Actions workflow (`.github/workflows/ci.yml`):**
1. **Lint** — Go vet, Python flake8/black, ESLint
2. **Test** — Go tests, Python pytest, TypeScript build
3. **Security Scan** — Trivy (container), TruffleHog (secrets), pip-audit (dependencies)
4. **Build & Push** — Docker images for all 6 services with layer caching

### Phase 16D: Documentation

- `README.md` — Comprehensive product overview, architecture, quick start
- `docs/ARCHITECTURE.md` — System diagrams, data flow, integration patterns
- `docs/PHASES.md` — This document (all 16 phases)
- `docs/WORKFLOWS.md` — NAD configuration E2E, all product workflows
- `docs/TESTING_REPORT.md` — Test results, scale & performance benchmarks
- `docs/DEPLOYMENT.md` — Deployment guide, Helm charts, 7 runbooks, env vars
- Dashboard help pages — Public-facing docs + AI-assisted troubleshooting

---

## Phase 17: Legacy NAC Integration & Migration Framework

**Objective:** Enable NeuraNAC to operate alongside an existing Legacy NAC 3.4+ deployment (coexistence), gradually migrate NADs from Legacy NAC to NeuraNAC, or run fully standalone — all from the same codebase.

### 17A: Architecture Decision — API-Based Sync (Not Node-Level)

**Key Decision:** NeuraNAC does **not** join the NeuraNAC cluster as a PSN/PAN node. NeuraNAC's internal node sync is proprietary and undocumented. Instead, NeuraNAC connects to NeuraNAC via:

1. **ERS REST API** (port 9060) — Bulk read of network devices, internal users, endpoints, identity groups, SGTs, authorization profiles
2. **Event Stream** (port 8910, STOMP/WebSocket) — Real-time session events, TrustSec SXP updates, threat context
3. **MnT API** (port 443) — Active session list, historical session data

This approach keeps NeuraNAC and NeuraNAC fully independent — either can be removed without affecting the other.

### 17B: Database Schema

**New tables added to `V001_initial_schema.sql`:**

| Table             | Purpose                                                  | Key Columns                                                 |
| ----------------- | -------------------------------------------------------- | ----------------------------------------------------------- |
| `legacy_nac_connections` | NeuraNAC PPAN connection config (hostname, credentials, mode) | `hostname`, `ers_port`, `event_stream_enabled`, `deployment_mode` |
| `legacy_nac_sync_state`  | Per-entity sync status and progress                      | `entity_type`, `last_sync_status`, `items_synced`           |
| `legacy_nac_sync_log`    | Audit trail of all sync operations                       | `sync_type`, `status`, `items_created`, `duration_ms`       |
| `legacy_nac_entity_map`  | NeuraNAC ID ↔ NeuraNAC ID mapping for synced entities              | `legacy_nac_id`, `neuranac_id`, `sync_hash`                             |

**Deployment modes:**
- `coexistence` — NeuraNAC + NeuraNAC run side by side, NeuraNAC is source of truth
- `migration` — Actively moving NADs from Legacy NAC to NeuraNAC
- `readonly` — NeuraNAC decommissioned, connection kept for reference
- (No legacy connection = `standalone` mode)

### 17C: NeuraNAC Adapter (API Router)

**File:** `services/api-gateway/app/routers/legacy_nac.py`

**Legacy ERS Client class** (`NeuraNACERSClient`):
- `test_connection()` — Verify ERS API reachability and auth
- `get_network_devices(page, size)` — `GET /ers/config/networkdevice`
- `get_internal_users(page, size)` — `GET /ers/config/internaluser`
- `get_endpoints(page, size)` — `GET /ers/config/endpoint`
- `get_identity_groups(page, size)` — `GET /ers/config/identitygroup`
- `get_sgts(page, size)` — `GET /ers/config/sgt`
- `get_active_sessions()` — `GET /admin/API/mnt/Session/ActiveList`

**API Endpoints (23rd router, `/api/v1/legacy-nac/`):**

| Method | Path                                 | Description                               |
| ------ | ------------------------------------ | ----------------------------------------- |
| GET    | `/connections`                       | List all legacy connections                  |
| POST   | `/connections`                       | Register new legacy connection               |
| GET    | `/connections/{id}`                  | Connection details                        |
| PUT    | `/connections/{id}`                  | Update connection config                  |
| DELETE | `/connections/{id}`                  | Remove connection                         |
| POST   | `/connections/{id}/test`             | Test ERS API connectivity                 |
| GET    | `/connections/{id}/sync-status`      | Per-entity sync status                    |
| POST   | `/connections/{id}/sync`             | Trigger full/incremental sync             |
| GET    | `/connections/{id}/sync-log`         | Sync history audit trail                  |
| GET    | `/connections/{id}/entity-map`       | NeuraNAC ↔ NeuraNAC entity mapping                  |
| GET    | `/connections/{id}/migration-status` | Migration phase progress                  |
| POST   | `/connections/{id}/migration`        | Execute migration action                  |
| GET    | `/connections/{id}/preview/{type}`   | Preview NeuraNAC entities before sync          |
| GET    | `/summary`                           | Overall legacy NAC integration dashboard summary |

### 17D: Dashboard Page

**File:** `web/src/pages/removed.tsx`

- Summary cards: connections count, syncs in 24h, entities mapped, active migrations
- Connection list with status icons (connected/disconnected/error)
- Add Connection form (hostname, ERS creds, Event Stream toggle, deployment mode)
- Connection detail panel with 4 tabs:
  - **Overview** — Entity sync cards with status badges
  - **Sync Status** — Table with detailed per-entity sync metrics
  - **Sync Log** — Historical sync operations with duration and counts
  - **Migration** — 5-phase migration workflow with action buttons

**Navigation:** Added "Legacy NAC Integration" with `Link2` icon to sidebar, positioned between Shadow AI and Twin Nodes.

### 17E: Three Deployment Models

| Model           | Customer Profile         | NeuraNAC Behavior                                |
| --------------- | ------------------------ | ------------------------------------------- |
| **Standalone**  | No NeuraNAC, greenfield       | Full NAC — no adapter needed                |
| **Coexistence** | NeuraNAC 3.4+ in production   | API sync, both handle RADIUS for their NADs |
| **Migration**   | NeuraNAC planned decommission | 5-phase cutover from Legacy NAC to NeuraNAC             |

**Migration Phases:**
1. **Sync Data** — Full sync of all entities from NeuraNAC
2. **Validate** — Verify data integrity, compare policy counts
3. **Pilot NADs** — Move 1-2 non-critical NADs to NeuraNAC RADIUS
4. **Full Cutover** — Migrate remaining NADs
5. **Decommission** — Set legacy connection to readonly, decommission NeuraNAC

### 17F: Files Created / Modified

**New files:**
- `services/api-gateway/app/routers/legacy_nac.py` — legacy NAC integration router (500+ lines)
- `web/src/pages/removed.tsx` — Dashboard page (400+ lines)
- `docs/NeuraNAC_INTEGRATION.md` — Comprehensive wiki for tech leads

**Modified files:**
- `database/migrations/V001_initial_schema.sql` — Added 4 NeuraNAC tables + indexes
- `services/api-gateway/app/main.py` — Registered NeuraNAC router
- `services/api-gateway/app/routers/__init__.py` — Added NeuraNAC to exports
- `services/api-gateway/tests/test_routers.py` — Added NeuraNAC endpoint tests
- `web/src/App.tsx` — Added `/legacy-nac` route
- `web/src/components/Layout.tsx` — Added Legacy NAC Integration nav item
- `docs/PHASES.md` — Added Phase 17
- `docs/ARCHITECTURE.md` — Added legacy NAC integration diagrams
- `docs/WORKFLOWS.md` — Added NeuraNAC coexistence + migration workflows
- `docs/TESTING_REPORT.md` — Added legacy NAC integration test results
- `README.md` — Updated capabilities, API endpoints, project structure
