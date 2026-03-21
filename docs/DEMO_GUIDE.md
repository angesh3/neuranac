# NeuraNAC Demo Guide — Complete Use Case List & Step-by-Step Instructions

This document provides a comprehensive demo guide for the NeuraNAC (NeuraNAC) platform, including all supported use cases, step-by-step setup instructions, and detailed demo scripts for each feature.

---

## Table of Contents

1. [End-to-End Demo Topology](#end-to-end-demo-topology)
2. [Zero-Install Demo (Recommended)](#zero-install-demo-recommended)
3. [Supported Use Cases (Today)](#supported-use-cases-today)
4. [Step-by-Step Demo Setup](#step-by-step-demo-setup)
5. [Demo Scripts for Each Use Case](#demo-scripts-for-each-use-case)
6. [Recommended Demo Flow (30 Minutes)](#recommended-demo-flow-30-minutes)

---

## End-to-End Demo Topology

The diagram below shows every component running on your laptop during a demo, including all ports, protocols, and data flows. The **Topology View** page (`/topology`) in the Web Dashboard visualizes this exact architecture interactively.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  YOUR LAPTOP (macOS / Linux)                                                    │
│                                                                                 │
│  ╔═══════════════════════════════════════════════════════════════════════════╗   │
│  ║  ENDPOINTS / SIMULATED NADs                                              ║   │
│  ║  ┌───────────────┐  ┌──────────────┐  ┌──────────────┐                   ║   │
│  ║  │  radtest /    │  │  Go RADIUS   │  │  k6 Load     │                   ║   │
│  ║  │  FreeRADIUS   │  │  Generator   │  │  Test Runner │                   ║   │
│  ║  │  CLI          │  │  (PAP/MAB/   │  │  (API stress)│                   ║   │
│  ║  └───────┬───────┘  │  EAP/Acct)   │  └──────┬───────┘                   ║   │
│  ║          │          └──────┬───────┘          │                           ║   │
│  ╚══════════╪═════════════════╪══════════════════╪═══════════════════════════╝   │
│             │ RADIUS UDP      │ RADIUS UDP       │ HTTP REST                     │
│             │ 1812/1813       │ 1812/1813/2083   │ :8080                         │
│             ▼                 ▼                   ▼                               │
│  ╔═══════════════════════════════════════════════════════════════════════════╗   │
│  ║  NeuraNAC PLATFORM (Docker Compose)                                           ║   │
│  ║                                                                          ║   │
│  ║  ┌─────────────────┐  gRPC :8082  ┌──────────────────┐                  ║   │
│  ║  │  RADIUS Server  │─────────────►│  Policy Engine   │                  ║   │
│  ║  │  Go :1812/1813  │              │  Python :8082    │                  ║   │
│  ║  │  RadSec :2083   │◄─────────────│  (VLAN/SGT/ACL) │                  ║   │
│  ║  │  TACACS+ :49    │  Decision    └──────────────────┘                  ║   │
│  ║  │  CoA :3799      │                                                    ║   │
│  ║  └────────┬────────┘  HTTP :8081  ┌──────────────────┐                  ║   │
│  ║           │──────────────────────►│  AI Engine       │                  ║   │
│  ║           │  Inline profiling     │  Python :8081    │                  ║   │
│  ║           │  + risk scoring       │  (16 AI modules) │                  ║   │
│  ║           │                       │  NLP Chat Router │                  ║   │
│  ║           │                       └──────────────────┘                  ║   │
│  ║           │ NATS events                                                 ║   │
│  ║           ▼                                                             ║   │
│  ║  ┌─────────────────┐  REST :8080  ┌──────────────────┐                  ║   │
│  ║  │  API Gateway    │◄────────────►│  Web Dashboard   │                  ║   │
│  ║  │  Python :8080   │             │  React :3001     │                  ║   │
│  ║  │  (30 routers)   │             │  (33 pages)      │                  ║   │
│  ║  │  JWT + RBAC     │             │                  │                  ║   │
│  ║  │  /api/v1/*      │             │  Pages include:  │                  ║   │
│  ║  │  /api/v1/       │             │  • Dashboard     │                  ║   │
│  ║  │    topology/    │─ ─ ─ ─ ─ ─ ►│  • Topology ◄───│─ 4-tab view     ║   │
│  ║  │                 │  aggregated  │  • Sessions     │  Physical        ║   │
│  ║  │                 │  component   │  • Policies     │  Service Mesh    ║   │
│  ║  │                 │  health +    │  • NeuraNAC (6 sub)  │  Data Flow       ║   │
│  ║  │                 │  status data │  • AI Mode      │  Legacy NAC Integration ║   │
│  ║  └────────┬────────┘             └──────────────────┘                  ║   │
│  ║           │                                                             ║   │
│  ║  ┌────────┴──────────────────────────────────────────────────────┐      ║   │
│  ║  │  INFRASTRUCTURE                                               │      ║   │
│  ║  │  ┌────────────┐  ┌────────────┐  ┌────────────┐              │      ║   │
│  ║  │  │ PostgreSQL │  │   Redis    │  │   NATS     │              │      ║   │
│  ║  │  │ :5432      │  │   :6379    │  │   :4222    │              │      ║   │
│  ║  │  │ (65 tables)│  │   (cache)  │  │ (JetStream)│              │      ║   │
│  ║  │  └────────────┘  └────────────┘  └────────────┘              │      ║   │
│  ║  └───────────────────────────────────────────────────────────────┘      ║   │
│  ║                                                                          ║   │
│  ║  ┌───────────────────────────────────────────────────────────────┐      ║   │
│  ║  │  OBSERVABILITY                                                │      ║   │
│  ║  │  ┌────────────┐  ┌────────────┐                               │      ║   │
│  ║  │  │ Prometheus │  │  Grafana   │                               │      ║   │
│  ║  │  │ :9092      │  │  :3000     │                               │      ║   │
│  ║  │  └────────────┘  └────────────┘                               │      ║   │
│  ║  └───────────────────────────────────────────────────────────────┘      ║   │
│  ╚══════════════════════════════════════╤════════════════════════════╝      │
│                                         │                                   │
└─────────────────────────────────────────┼───────────────────────────────────┘
                                          │  ERS API :9060
                                          │  Event Stream :8910
                          Network (VPN/LAN)│  Bidirectional Sync
                                          ▼
                              ┌────────────────────────┐
                              │  Legacy NAC             │
                              │  x.x.x.x:443          │
                              │  ERS API :9060         │
                              │  Event Stream :8910   │
                              │                        │
                              │  Entities synced:      │
                              │  • Network Devices     │
                              │  • Endpoints           │
                              │  • Policies            │
                              │  • SGTs                │
                              └────────────────────────┘
```

### RADIUS Authentication Data Flow (9 Steps)

This is the exact flow visualized in the **Topology → Data Flow** tab:

```
  ┌──────────┐    802.1X/MAB     ┌──────────┐    RADIUS UDP    ┌──────────────┐
  │ Endpoint │ ─────────────────►│   NAD    │ ──────────────► │ RADIUS Server│
  │ (suppl.) │                   │ (switch) │    :1812         │ Go :1812     │
  └──────────┘                   └──────────┘                  └──────┬───────┘
                                                                      │
                    ┌─────────────────────────────────────────────────┤
                    │                                                 │
                    ▼                                                 ▼
            ┌──────────────┐                               ┌──────────────┐
            │ AI Engine    │  HTTP :8081                    │Policy Engine │
            │ (Profile +   │◄──────────────────────────────│ gRPC :8082   │
            │  Risk Score) │                               │ (Evaluate)   │
            └──────┬───────┘                               └──────┬───────┘
                   │ risk_score, anomaly_flag                     │ VLAN, SGT
                   ▼                                              ▼
            ┌──────────────┐    RADIUS Response          ┌──────────────┐
            │ PostgreSQL   │◄────────────────────────────│ RADIUS Server│
            │ (session log)│                             │ (build reply)│
            └──────────────┘                             └──────┬───────┘
                                                                │
                                          Accept/Reject/        │  CoA :3799
                                          Challenge             │  (if high risk)
                                                                ▼
                                                         ┌──────────────┐
                                                         │   NAD        │
                                                         │ (apply VLAN) │
                                                         └──────────────┘
```

### Topology View — What Each Tab Shows

| Tab                 | Data Sources                                   | Visualization                                                     |
| ------------------- | ---------------------------------------------- | ----------------------------------------------------------------- |
| **Physical**        | NADs, endpoints, services, infra health probes | Layered: Endpoints → NADs → NeuraNAC Services → Infrastructure         |
| **Service Mesh**    | Service health checks, latency, protocol edges | Component cards with connection table (protocol, direction)       |
| **Data Flow**       | Static 9-step RADIUS auth trace                | Sequential flow: Endpoint → NAD → RADIUS → Policy → AI → DB → CoA |
| **Legacy NAC Integration** | legacy connections, event stream, sync status     | Legacy NAC ↔ NeuraNAC data flow with ERS/Event Stream/Bidirectional sync     |

### API Endpoints for Topology

```bash
# Aggregated topology data (views: physical, logical, dataflow, legacy_nac)
GET /api/v1/topology/?view=physical

# Quick service health matrix
GET /api/v1/topology/health-matrix

# AI chat — ask about topology
POST /api/v1/ai/chat  {"message": "show network topology"}
POST /api/v1/ai/chat  {"message": "show radius auth flow"}
POST /api/v1/ai/chat  {"message": "show service health matrix"}
```

---

## Zero-Install Demo (Recommended)

The only prerequisite is **Docker Desktop** (8 GB RAM). All client-side tools are containerized inside a `demo-tools` container — no Go, Python, radtest, or k6 installation needed on your Mac.

```bash
# One command — sets up everything + opens interactive demo menu
./scripts/demo.sh

# Or step by step:
./scripts/demo.sh --setup              # Start NeuraNAC stack + build demo-tools container
./scripts/demo.sh --run                # Interactive demo menu (11 demos)
./scripts/demo.sh --run pap            # Quick RADIUS PAP test
./scripts/demo.sh --run full           # Run all demos in sequence
./scripts/demo.sh --run sanity         # Run 344 sanity tests
./scripts/demo.sh --shell              # Shell with all tools (radtest, go, k6, jq...)
./scripts/demo.sh --monitoring         # Include Prometheus + Grafana
./scripts/demo.sh --status             # Check container & service health
./scripts/demo.sh --stop               # Tear down everything
```

The `demo-tools` container includes:

| Tool                   | Purpose                                                |
| ---------------------- | ------------------------------------------------------ |
| `radtest` (FreeRADIUS) | RADIUS PAP/MAB authentication                          |
| Go 1.22                | RADIUS protocol test suite (PAP, MAB, EAP, Accounting) |
| k6                     | API load/stress testing                                |
| Python 3 + requests    | Sanity runner (407 tests)                              |
| curl, jq, openssl      | Ad-hoc API calls, JSON processing, TLS checks          |

> **Note:** The "Step-by-Step Demo Setup" section below is for users who prefer to install tools locally. If you use `./scripts/demo.sh`, skip directly to the [Demo Scripts](#demo-scripts-for-each-use-case).

---

## Supported Use Cases (Today)

### Category A: RADIUS Authentication (Data Plane)

| #   | Use Case                                   | Protocol        | Demo Method                 |
| --- | ------------------------------------------ | --------------- | --------------------------- |
| A1  | **PAP Authentication**                     | RADIUS UDP 1812 | `radtest` or Go test        |
| A2  | **EAP-TLS (Certificate-based 802.1X)**     | RADIUS UDP 1812 | Go EAP Identity test        |
| A3  | **EAP-TTLS**                               | RADIUS UDP 1812 | Go EAP test                 |
| A4  | **PEAP/MSCHAPv2**                          | RADIUS UDP 1812 | Go EAP test                 |
| A5  | **MAB (MAC Authentication Bypass)**        | RADIUS UDP 1812 | Go MAB test                 |
| A6  | **RADIUS Accounting (Start/Interim/Stop)** | RADIUS UDP 1813 | Go Accounting test          |
| A7  | **RadSec (RADIUS over TLS)**               | TLS TCP 2083    | `openssl s_client`          |
| A8  | **CoA (Change of Authorization)**          | RADIUS UDP 3799 | Auto-triggered on high risk |
| A9  | **TACACS+ Device Admin**                   | TCP 49          | API or telnet test          |

### Category B: Policy Engine

| #   | Use Case                                   | Demo Method                                                  |
| --- | ------------------------------------------ | ------------------------------------------------------------ |
| B1  | **Policy evaluation with VLAN assignment** | RADIUS auth → check response attributes                      |
| B2  | **SGT (Security Group Tag) assignment**    | RADIUS auth → check cisco-av-pair                            |
| B3  | **AI-augmented policy conditions**         | RADIUS auth with AI risk scoring                             |
| B4  | **Circuit breaker fallback**               | Stop policy-engine container, send RADIUS → falls back to DB |
| B5  | **NLP policy creation**                    | AI chat: *"Create a rule to allow employees on VLAN 100"*    |

### Category C: AI Engine (16 Modules)

| #   | Use Case                         | API / UI Demo                                                          |
| --- | -------------------------------- | ---------------------------------------------------------------------- |
| C1  | **AI Chat (NLP Action Router)**  | UI AI Mode toggle → type natural language                              |
| C2  | **Endpoint Profiling (ONNX)**    | `POST /api/v1/ai/profile` with MAC address                             |
| C3  | **Risk Scoring**                 | `POST /api/v1/ai/risk` or auto after RADIUS auth                       |
| C4  | **Shadow AI Detection**          | `POST /api/v1/ai/shadow` with DNS/SNI patterns                         |
| C5  | **NLP Policy Translation**       | `POST /api/v1/ai/nlp/translate`                                        |
| C6  | **Anomaly Detection**            | `POST /api/v1/ai/anomaly/analyze`                                      |
| C7  | **Policy Drift Detection**       | `POST /api/v1/ai/drift/analyze`                                        |
| C8  | **RAG Troubleshooter**           | `POST /api/v1/ai/rag/troubleshoot`                                     |
| C9  | **NL-to-SQL Queries**            | `POST /api/v1/ai/nl-sql/query`                                         |
| C10 | **Adaptive Risk Scoring**        | `POST /api/v1/ai/risk/feedback` → `GET /api/v1/ai/risk/thresholds`     |
| C11 | **TLS Fingerprinting (JA3/JA4)** | `POST /api/v1/ai/tls/analyze-ja3`                                      |
| C12 | **Capacity Planning**            | `POST /api/v1/ai/capacity/record` → `GET /api/v1/ai/capacity/forecast` |
| C13 | **Automated Playbooks**          | `GET /api/v1/ai/playbooks` → `POST .../execute`                        |
| C14 | **Model Registry (A/B testing)** | `POST /api/v1/ai/models/register` → create experiment                  |
| C15 | **Training Pipeline**            | `POST /api/v1/ai/training/sample` → `POST .../train`                   |

### Category D: Legacy NAC Integration

| #   | Use Case                              | Demo Method                                            |
| --- | ------------------------------------- | ------------------------------------------------------ |
| D1  | **Legacy Connection (ERS API)**          | UI: Legacy NAC > Create Connection > Test               |
| D2  | **Legacy NAC Version Detection**              | `POST /api/v1/legacy-nac/connections/{id}/detect-version`     |
| D3  | **Full Entity Sync (Legacy NAC → NeuraNAC)**   | `POST /api/v1/legacy-nac/connections/{id}/sync`               |
| D4  | **Bidirectional Sync (Legacy NAC ↔ NeuraNAC)** | `POST /api/v1/legacy-nac/connections/{id}/sync/bidirectional` |
| D5  | **Sync Scheduler**                    | Create schedules, run-due endpoint                     |
| D6  | **Event Stream Real-time Events**     | Connect event stream → simulate events → view          |
| D7  | **Sync Conflict Resolution**          | Simulate conflicts → view → resolve                    |
| D8  | **AI Policy Translation (NeuraNAC → NeuraNAC)** | Discover NeuraNAC policies → translate → apply              |
| D9  | **RADIUS Traffic Analysis**           | Create baseline snapshot → create current → compare    |
| D10 | **Zero-Touch Migration Wizard**       | 8-step wizard: preflight → cutover                     |
| D11 | **Multi-Connection Dashboard**             | `GET /api/v1/legacy-nac/multi-connection/overview`            |

### Category E: Web Dashboard (33 Pages) & Topology

| #   | Use Case                                   | Route                                                                                           |
| --- | ------------------------------------------ | ----------------------------------------------------------------------------------------------- |
| E1  | **Dashboard Overview**                     | `/`                                                                                             |
| E2  | **Network Topology (4-tab visualization)** | `/topology`                                                                                     |
| E3  | **Network Device (NAD) Management**        | `/network-devices`                                                                              |
| E4  | **Endpoint Inventory**                     | `/endpoints`                                                                                    |
| E5  | **Session Monitoring**                     | `/sessions`                                                                                     |
| E6  | **Policy Management**                      | `/policies`                                                                                     |
| E7  | **Certificate Management (CA + X.509)**    | `/certificates`                                                                                 |
| E8  | **TrustSec Segmentation (SGTs)**           | `/segmentation`                                                                                 |
| E9  | **Guest Portal Management**                | `/guest`                                                                                        |
| E10 | **Posture Assessment**                     | `/posture`                                                                                      |
| E11 | **AI Agent Registry**                      | `/ai/agents`                                                                                    |
| E12 | **AI Data Flow Policies**                  | `/ai/data-flow`                                                                                 |
| E13 | **Shadow AI Detection Page**               | `/ai/shadow`                                                                                    |
| E14 | **Identity Sources (AD/LDAP/SAML)**        | `/identity`                                                                                     |
| E15 | **Twin-Node Sync Status**                  | `/nodes`                                                                                        |
| E16 | **Audit Log (tamper-proof)**               | `/audit`                                                                                        |
| E17 | **Diagnostics & Troubleshooting**          | `/diagnostics`                                                                                  |
| E18 | **Privacy/GDPR Compliance**                | `/privacy`                                                                                      |
| E19 | **SIEM Forwarding Config**                 | `/siem`                                                                                         |
| E20 | **Webhook Management**                     | `/webhooks`                                                                                     |
| E21 | **License Management**                     | `/licenses`                                                                                     |
| E22 | **Settings**                               | `/settings`                                                                                     |
| E23 | **Legacy NAC (6 sub-pages)**                | `/legacy-nac`, `/legacy-nac/wizard`, `/legacy-nac/conflicts`, `/legacy-nac/event-stream`, `/legacy-nac/policies`, `/legacy-nac/radius-analysis` |
| E24 | **AI Mode (ChatGPT-like interface)**       | Toggle pill top-right                                                                           |

### Category F: Operations & Observability

| #   | Use Case                          | Demo Method                                   |
| --- | --------------------------------- | --------------------------------------------- |
| F1  | **Prometheus Metrics**            | `http://localhost:9092`                       |
| F2  | **Grafana Dashboard**             | `http://localhost:3000`                       |
| F3  | **NATS JetStream Monitoring**     | `http://localhost:8222`                       |
| F4  | **Health Checks (all services)**  | `curl localhost:{8080,8081,8082,9100}/health` |
| F5  | **DB Schema Validation**          | `GET /api/v1/diagnostics/db-schema-check`     |
| F6  | **Topology Health Matrix**        | `GET /api/v1/topology/health-matrix`          |
| F7  | **Sanity Test Suite (407 tests)** | `python3 scripts/sanity_runner.py`            |

---

## Step-by-Step Demo Setup

### Prerequisites

- **Docker Desktop** — at least 8 GB RAM allocated
- **Go 1.22+** — for the RADIUS traffic generator
- *(Optional)* `radtest` from FreeRADIUS — `brew install freeradius-server`
- *(Optional)* Legacy NAC 3.4+ accessible from your laptop (VPN/LAN) with ERS API enabled

### Step 1 — Start the NeuraNAC Stack

```bash
# One-command setup (recommended)
./scripts/setup.sh

# OR manually:
cp .env.example .env
docker compose -f deploy/docker-compose.yml up -d --build

# Run migrations
for f in database/migrations/V*.sql; do
  docker compose -f deploy/docker-compose.yml exec -T postgres psql -U neuranac -d neuranac < "$f"
done
docker compose -f deploy/docker-compose.yml exec -T postgres psql -U neuranac -d neuranac < database/seeds/seed_data.sql
```

To include monitoring (Prometheus + Grafana):

```bash
docker compose -f deploy/docker-compose.yml --profile monitoring up -d
```

### Step 2 — Verify All Services Are Healthy

```bash
# Health checks
curl -s http://localhost:8080/health | jq    # API Gateway
curl -s http://localhost:9100/health | jq    # RADIUS Server
curl -s http://localhost:8082/health | jq    # Policy Engine
curl -s http://localhost:8081/health | jq    # AI Engine

# DB Schema check (verifies all 65 tables)
curl -s http://localhost:8080/api/v1/diagnostics/db-schema-check | jq '.overall_status'

# Topology health matrix (all components at a glance)
curl -s http://localhost:8080/api/v1/topology/health-matrix | jq

# Open Web UI
open http://localhost:3001
```

### Seed Credentials

| Username   | Password     | Purpose                |
| ---------- | ------------ | ---------------------- |
| `testuser` | `testing123` | RADIUS PAP test user   |
| `admin`    | `admin123`   | RADIUS admin test user |

**NAD shared secret** for all test NADs: `testing123` (registered for `127.0.0.1` and `172.17.0.1`)

### Step 3 — Obtain a JWT Token (for API demos)

```bash
TOKEN=$(curl -s -X POST http://localhost:8080/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' | jq -r '.access_token')
echo "Token: $TOKEN"
```

---

## Demo Scripts for Each Use Case

### Demo A: RADIUS Authentication

```bash
# A1. PAP Authentication
radtest testuser testing123 127.0.0.1 0 testing123
# Expected: Access-Accept

# A2-A4. EAP Identity (triggers 802.1X flow)
cd tests/integration
go test -v -run "TestRADIUS_LiveEAPIdentity" -timeout 10s
# Expected: Access-Challenge (EAP negotiation started)

# A5. MAB (MAC Auth Bypass)
go test -v -run "TestRADIUS_LiveMABRequest" -timeout 10s
# Expected: Access-Accept or Access-Reject

# A6. RADIUS Accounting
go test -v -run "TestRADIUS_LiveAccountingRequest" -timeout 10s
# Expected: Accounting-Response

# A7. RadSec (verify TLS listener is up)
openssl s_client -connect localhost:2083 </dev/null 2>&1 | head -5

# Bulk traffic for dashboard activity
for i in $(seq 1 20); do
  radtest testuser testing123 127.0.0.1 0 testing123 2>&1 | tail -1
  sleep 0.3
done
```

**What to show:** Open http://localhost:3001/sessions after running traffic — live sessions appear.

### Demo B: Policy Engine

```bash
# B1/B2. Send RADIUS auth, check VLAN/SGT in response
radtest testuser testing123 127.0.0.1 0 testing123
# Check RADIUS server logs for VLAN/SGT assignment:
docker logs neuranac-radius --tail=20 | grep -E "VLAN|SGT|policy"

# B4. Circuit breaker demo
docker stop neuranac-policy
radtest testuser testing123 127.0.0.1 0 testing123  # Falls back to DB-based eval
docker start neuranac-policy

# B5. NLP policy creation (via AI chat — see Demo C1)
```

### Demo C: AI Engine

```bash
# C1. AI Chat (Action Router — 49 intents including topology)
curl -s -X POST http://localhost:8080/api/v1/ai/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message":"Show me all active sessions"}' | jq

curl -s -X POST http://localhost:8080/api/v1/ai/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message":"Show network topology"}' | jq

curl -s -X POST http://localhost:8080/api/v1/ai/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message":"Create a policy to allow employees on VLAN 100"}' | jq

# C2. Endpoint Profiling
curl -s -X POST http://localhost:8081/api/v1/profile \
  -H "Content-Type: application/json" \
  -d '{"mac_address":"AA:BB:CC:DD:EE:01","dhcp_hostname":"DESKTOP-ABC123","dhcp_options":"MSFT 5.0"}' | jq

# C3. Risk Scoring
curl -s -X POST http://localhost:8081/api/v1/risk \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","endpoint_mac":"AA:BB:CC:DD:EE:01","nas_ip":"10.0.0.1","eap_type":"eap-tls"}' | jq

# C4. Shadow AI Detection
curl -s -X POST http://localhost:8081/api/v1/shadow \
  -H "Content-Type: application/json" \
  -d '{"dns_queries":["api.openai.com","chat.openai.com"],"sni_values":["api.openai.com"]}' | jq

# C5. NLP Policy Translation
curl -s -X POST http://localhost:8081/api/v1/nlp/translate \
  -H "Content-Type: application/json" \
  -d '{"text":"Allow all employees using 802.1X to access VLAN 100 with SGT Employees"}' | jq

# C6. Anomaly Detection
curl -s -X POST http://localhost:8081/api/v1/anomaly/analyze \
  -H "Content-Type: application/json" \
  -d '{"endpoint_mac":"AA:BB:CC:DD:EE:01","username":"testuser","nas_ip":"10.0.0.1","auth_time_hour":3,"day_of_week":0}' | jq

# C7. Policy Drift
curl -s -X POST http://localhost:8081/api/v1/drift/analyze \
  -H "Content-Type: application/json" \
  -d '{"policy_id":"default-policy","expected_action":"permit","actual_action":"deny"}' | jq

# C8. RAG Troubleshooter
curl -s -X POST http://localhost:8080/api/v1/ai/rag/troubleshoot \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query":"Why are users failing EAP-TLS authentication?"}' | jq

# C9. NL-to-SQL
curl -s -X POST http://localhost:8080/api/v1/ai/nl-sql/query \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question":"How many active sessions are there?"}' | jq

# C10. Adaptive Risk (feedback loop)
curl -s -X POST http://localhost:8080/api/v1/ai/risk/feedback \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"score":75,"actual_outcome":"safe","operator_action":"allow"}' | jq

curl -s http://localhost:8080/api/v1/ai/risk/thresholds \
  -H "Authorization: Bearer $TOKEN" | jq

# C11. TLS Fingerprinting
curl -s -X POST http://localhost:8080/api/v1/ai/tls/analyze-ja3 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"ja3_hash":"e7d705a3286e19ea42f587b344ee6865"}' | jq

# C12. Capacity Planning
curl -s -X POST http://localhost:8080/api/v1/ai/capacity/record \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"metric":"auth_requests_per_second","value":150}' | jq

curl -s "http://localhost:8080/api/v1/ai/capacity/forecast?metric=auth_requests_per_second" \
  -H "Authorization: Bearer $TOKEN" | jq

# C13. Playbooks
curl -s http://localhost:8080/api/v1/ai/playbooks \
  -H "Authorization: Bearer $TOKEN" | jq '.playbooks[].name'

# C14. Model Registry
curl -s http://localhost:8080/api/v1/ai/models \
  -H "Authorization: Bearer $TOKEN" | jq

# C15. Training Pipeline
curl -s http://localhost:8080/api/v1/ai/training/stats \
  -H "Authorization: Bearer $TOKEN" | jq
```

**UI Demo for AI:** Open http://localhost:3001 → click the **AI/Classic toggle** (top-right) → type natural language queries like *"Show network topology"*, *"Show radius auth flow"*, or *"Navigate to topology"*.

### Demo D: Legacy NAC Integration

```bash
# D1. Create legacy connection (simulated in dev mode)
curl -s -X POST http://localhost:8080/api/v1/legacy-nac/connections \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name":"Lab NeuraNAC","hostname":"10.10.10.1","port":443,
    "username":"ersadmin","password":"NeuraNACPassword",
    "ers_enabled":true,"ers_port":9060,
    "event_stream_enabled":true,"verify_ssl":false,
    "deployment_mode":"coexistence"
  }' | jq
# Save the connection ID from the response:
CONN_ID="<id-from-response>"

# D2. Detect NeuraNAC Version
curl -s -X POST "http://localhost:8080/api/v1/legacy-nac/connections/$CONN_ID/detect-version" \
  -H "Authorization: Bearer $TOKEN" | jq

# D3. Full Entity Sync
curl -s -X POST "http://localhost:8080/api/v1/legacy-nac/connections/$CONN_ID/sync" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"entity_types":["all"],"sync_type":"full","direction":"legacy_to_neuranac"}' | jq

# D4. Bidirectional Sync
curl -s -X POST "http://localhost:8080/api/v1/legacy-nac/connections/$CONN_ID/sync/bidirectional" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"entity_types":["all"],"direction":"neuranac_to_legacy_nac"}' | jq

# D5. Create Sync Schedule
curl -s -X POST "http://localhost:8080/api/v1/legacy-nac/connections/$CONN_ID/schedules" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"entity_type":"network_device","interval_minutes":30,"sync_type":"incremental"}' | jq

# D6. Event Stream (connect + simulate event)
curl -s -X POST "http://localhost:8080/api/v1/legacy-nac/connections/$CONN_ID/event-stream/connect" \
  -H "Authorization: Bearer $TOKEN" | jq

curl -s -X POST "http://localhost:8080/api/v1/legacy-nac/connections/$CONN_ID/event-stream/simulate-event?event_type=session_created" \
  -H "Authorization: Bearer $TOKEN" | jq

curl -s "http://localhost:8080/api/v1/legacy-nac/connections/$CONN_ID/event-stream/events" \
  -H "Authorization: Bearer $TOKEN" | jq

# D7. Sync Conflicts (simulate + view + resolve)
curl -s -X POST "http://localhost:8080/api/v1/legacy-nac/connections/$CONN_ID/conflicts/simulate" \
  -H "Authorization: Bearer $TOKEN" | jq

curl -s "http://localhost:8080/api/v1/legacy-nac/connections/$CONN_ID/conflicts" \
  -H "Authorization: Bearer $TOKEN" | jq

# D8. AI Policy Translation
curl -s "http://localhost:8080/api/v1/legacy-nac/connections/$CONN_ID/policies/discover" \
  -H "Authorization: Bearer $TOKEN" | jq '.policies[].name'

curl -s -X POST "http://localhost:8080/api/v1/legacy-nac/connections/$CONN_ID/policies/translate" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"policy_name":"Corp-Wired-Dot1x","use_ai":true}' | jq

curl -s -X POST "http://localhost:8080/api/v1/legacy-nac/connections/$CONN_ID/policies/translate-all" \
  -H "Authorization: Bearer $TOKEN" | jq

# D9. RADIUS Traffic Analysis
curl -s -X POST "http://localhost:8080/api/v1/legacy-nac/connections/$CONN_ID/radius-analysis/snapshot" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"snapshot_name":"NeuraNAC Baseline","snapshot_type":"baseline_legacy_nac","capture_duration_minutes":60}' | jq

# D10. Zero-Touch Migration Wizard
curl -s -X POST "http://localhost:8080/api/v1/legacy-nac/connections/$CONN_ID/wizard/start" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"run_name":"Sprint Demo Migration"}' | jq
# Save RUN_ID from response, then execute each step:
RUN_ID="<run-id-from-response>"
for step in $(seq 1 8); do
  echo "--- Executing Step $step ---"
  curl -s -X POST "http://localhost:8080/api/v1/legacy-nac/connections/$CONN_ID/wizard/$RUN_ID/execute-step" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"action":"next"}' | jq '.step_name, .result'
done

# D11. Multi-NeuraNAC Dashboard
curl -s http://localhost:8080/api/v1/legacy-nac/multi-connection/overview \
  -H "Authorization: Bearer $TOKEN" | jq
```

**UI Demo for Legacy NAC:** Open http://localhost:3001/legacy-nac → follow the onboarding checklist → navigate through all 6 Legacy NAC sub-pages. Then open `/topology` → **Legacy NAC Integration** tab to see the Legacy NAC ↔ NeuraNAC data flow diagram.

### Demo E: Web Dashboard & Topology Tour

Open http://localhost:3001 and walk through:

1. **Dashboard** (`/`) — health cards, metrics overview
2. **Network Topology** (`/topology`) — 4-tab interactive visualization:
   - **Physical** — Endpoints → NADs → NeuraNAC Services → Infrastructure (layered view with health badges)
   - **Service Mesh** — All internal component connections with protocols, latencies, and edge table
   - **Data Flow** — 9-step RADIUS authentication request trace (see diagram above)
   - **Legacy NAC Integration** — Legacy NAC ↔ NeuraNAC integration points, sync entities, ERS/Event Stream/Bidir arrows
3. **Network Devices** (`/network-devices`) — see seeded `localhost-test` NAD
4. **Sessions** (`/sessions`) — shows live sessions after RADIUS traffic
5. **Endpoints** (`/endpoints`) — devices that have authenticated
6. **Policies** (`/policies`) — policy rule management
7. **Segmentation** (`/segmentation`) — SGT management
8. **Certificates** (`/certificates`) — CA and X.509 certificate management
9. **Guest Portal** (`/guest`) — guest access configuration
10. **AI Agents** (`/ai/agents`) — AI agent identity registry
11. **Shadow AI** (`/ai/shadow`) — shadow AI detection results
12. **AI Data Flow** (`/ai/data-flow`) — AI data flow policy management
13. **Legacy NAC** (collapsible sidebar group) — all 6 NeuraNAC sub-pages
14. **AI Mode** — click the toggle pill (top-right) → ChatGPT-like interface
15. **Diagnostics** (`/diagnostics`) — troubleshooting tools
16. **Audit** (`/audit`) — tamper-proof audit log
17. **Nodes** (`/nodes`) — twin-node replication status

### Demo F: Operations, Topology & Observability

```bash
# F1. Prometheus
open http://localhost:9092
# Example query: neuranac_radius_auth_requests_total

# F2. Grafana
open http://localhost:3000
# Login: admin / changeme_grafana_admin
# Pre-provisioned "NeuraNAC" dashboard available

# F3. NATS JetStream
open http://localhost:8222

# F4. All health endpoints
for port in 8080 8081 8082 9100; do
  echo "Port $port: $(curl -s http://localhost:$port/health | jq -r '.status // .service')"
done

# F5. DB Schema Validation (verifies all 65 tables)
curl -s http://localhost:8080/api/v1/diagnostics/db-schema-check | jq '.overall_status'

# F6. Topology API — aggregated component view
curl -s http://localhost:8080/api/v1/topology/?view=physical | jq '.summary'
curl -s http://localhost:8080/api/v1/topology/?view=logical | jq '.edges[:3]'
curl -s http://localhost:8080/api/v1/topology/?view=dataflow | jq '.layers.steps[] | .step, .component, .action'
curl -s http://localhost:8080/api/v1/topology/?view=legacy_nac | jq '.layers.integration_points'
curl -s http://localhost:8080/api/v1/topology/health-matrix | jq .

# F7. Full Sanity Suite (407 tests)
python3 scripts/sanity_runner.py

# Run only topology tests (10 tests)
python3 scripts/sanity_runner.py --phase topology
```

---

## Per-Deployment-Scenario Walkthroughs

These walkthroughs cover the 4 supported deployment topologies end-to-end.

### S1: NeuraNAC + Hybrid (Cloud + On-Prem)

**Setup:**
```bash
# Configure .env
DEPLOYMENT_MODE=hybrid
NeuraNAC_ENABLED=true
NEURANAC_SITE_TYPE=onprem
NEURANAC_PEER_API_URL=http://api-gateway-cloud:8080
FEDERATION_SHARED_SECRET=$(openssl rand -hex 32)

# Launch both sites + bridge connector
cd deploy
docker compose -f docker-compose.yml -f docker-compose.hybrid.yml --profile legacy_nac up -d
```

**Verify:**
```bash
# On-prem API health (port 8080)
curl -s http://localhost:8080/health | jq '.deployment_mode, .legacy_nac_enabled'
# Cloud API health (port 9080)
curl -s http://localhost:9080/health | jq '.deployment_mode, .site_type'
# Bridge Connector
curl -s http://localhost:8090/health | jq
# UI config shows NeuraNAC nav + hybrid badge
curl -s http://localhost:8080/api/v1/config/ui | jq '.legacyNacEnabled, .deploymentMode'
```

**Demo flow:**
1. Login to on-prem dashboard at `http://localhost:3001` → verify "Scenario 1: Hybrid + NeuraNAC" label
2. Navigate to **Site Management** → see both sites, bridge connector table visible
3. Navigate to **Legacy NAC** pages → create connection, trigger sync
4. Open cloud dashboard at `http://localhost:3002` → confirm data federation
5. Send RADIUS auth → check `sessions` table has `site_id` stamped

---

### S2: Cloud Only (No NeuraNAC)

**Setup:**
```bash
DEPLOYMENT_MODE=standalone
NeuraNAC_ENABLED=false
NEURANAC_SITE_TYPE=cloud

cd deploy && docker compose up -d
```

**Verify:**
```bash
curl -s http://localhost:8080/health | jq '.deployment_mode, .site_type'
curl -s http://localhost:8080/api/v1/config/ui | jq '.legacyNacEnabled'
# Should return false
```

**Demo flow:**
1. Login → verify "Scenario 2: Cloud Standalone" label
2. Navigate to **NeuraNAC** pages → see "Legacy NAC Integration Not Enabled" banner
3. **Site Management** → single site, no connectors table
4. All non-NeuraNAC features fully functional (RADIUS, policies, AI, etc.)

---

### S3: On-Prem Only (No NeuraNAC)

**Setup:**
```bash
DEPLOYMENT_MODE=standalone
NeuraNAC_ENABLED=false
NEURANAC_SITE_TYPE=onprem

cd deploy && docker compose up -d
```

**Verify:**
```bash
curl -s http://localhost:8080/health | jq '.deployment_mode, .site_type'
# standalone, onprem
```

**Demo flow:**
1. Login → verify "Scenario 3: On-Prem Standalone" label
2. Same as S2 but with `onprem` site type shown in Site Management
3. Twin-node sync between Node A / Node B available for HA

---

### S4: Hybrid No NeuraNAC (Cloud + On-Prem)

**Setup:**
```bash
DEPLOYMENT_MODE=hybrid
NeuraNAC_ENABLED=false
NEURANAC_SITE_TYPE=onprem
NEURANAC_PEER_API_URL=http://api-gateway-cloud:8080
FEDERATION_SHARED_SECRET=$(openssl rand -hex 32)

cd deploy
docker compose -f docker-compose.yml -f docker-compose.hybrid.yml up -d
```

**Verify:**
```bash
# On-prem
curl -s http://localhost:8080/health | jq '.deployment_mode, .legacy_nac_enabled'
# hybrid, false
# Cloud
curl -s http://localhost:9080/health | jq '.site_type'
# cloud
```

**Demo flow:**
1. Login → verify "Scenario 4: Hybrid (No NeuraNAC)" label
2. **Site Management** → two sites visible, NO connectors table
3. NeuraNAC nav pages → "Legacy NAC Integration Not Enabled" banner
4. Federation: query `X-NeuraNAC-Site: peer` and `X-NeuraNAC-Site: all` headers
5. RADIUS sessions stamped with correct `site_id` on each side

---

## Hybrid Architecture Demo Scenarios

### Scenario 1 — Multi-Site Federation (X-NeuraNAC-Site Header)

```bash
# 1. Check deployment mode
curl -s http://localhost:8080/api/v1/nodes/sync-status | jq

# 2. List nodes on the local site
TOKEN=$(curl -s -X POST http://localhost:8080/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' | jq -r '.access_token')

curl -s http://localhost:8080/api/v1/nodes \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-NeuraNAC-Site: local" | jq

# 3. Query peer site (requires DEPLOYMENT_MODE=hybrid + NEURANAC_PEER_API_URL)
curl -s http://localhost:8080/api/v1/nodes \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-NeuraNAC-Site: peer" | jq

# 4. Fan-out to all sites (merges local + peer results)
curl -s http://localhost:8080/api/v1/nodes \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-NeuraNAC-Site: all" | jq
```

### Scenario 2 — Bridge Connector Registration (On-Prem Profile)

```bash
# 1. Start with NeuraNAC profile
docker compose -f deploy/docker-compose.yml --profile legacy_nac up -d

# 2. Check Bridge Connector health
curl -s http://localhost:8090/health | jq

# 3. Check connector status
curl -s http://localhost:8090/status | jq

# 4. List registered connectors from API Gateway
curl -s http://localhost:8080/api/v1/connectors \
  -H "Authorization: Bearer $TOKEN" | jq

# 5. Test ERS relay (simulated mode)
curl -s http://localhost:8090/relay/ers/test | jq
```

### Scenario 3 — Site Management

```bash
# 1. List all sites
curl -s http://localhost:8080/api/v1/sites \
  -H "Authorization: Bearer $TOKEN" | jq

# 2. Check deployment config
curl -s http://localhost:8080/api/v1/config/ui | jq
```

### Scenario 4 — Federation Circuit Breaker

```bash
# When peer is unreachable, the circuit breaker opens after 3 failures.
# Subsequent requests get 503 with retry_after_seconds until the breaker resets (30s).
curl -s http://localhost:8080/api/v1/nodes \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-NeuraNAC-Site: peer" | jq
# Expected: {"error": "Peer site unreachable", ...}
# After 3 failures: {"error": "Peer site circuit breaker open", "retry_after_seconds": ...}
```

---

## Recommended Demo Flow (30 Minutes)

| Time      | Scene                  | What to Demo                                                  | Method                  |
| --------- | ---------------------- | ------------------------------------------------------------- | ----------------------- |
| 0-2 min   | **Stack Startup**      | `./scripts/setup.sh`, verify health                           | Terminal                |
| 2-5 min   | **Topology View**      | Walk all 4 tabs: Physical → Service Mesh → Data Flow → NeuraNAC    | `/topology` page        |
| 5-7 min   | **Dashboard Tour**     | Overview, sidebar navigation, key pages                       | http://localhost:3001   |
| 7-10 min  | **RADIUS Auth**        | PAP + MAB + accounting                                        | `radtest` + Go tests    |
| 10-12 min | **Session View**       | Live sessions appear in UI after auth traffic                 | `/sessions` page        |
| 12-15 min | **AI Mode**            | Toggle AI, ask *"Show network topology"*, *"Show sessions"*   | AI chat interface       |
| 15-17 min | **Shadow AI**          | Detect unauthorized AI services                               | `POST /shadow` API call |
| 17-19 min | **Risk Scoring**       | Show risk levels, auto-quarantine on critical                 | `POST /risk` API call   |
| 19-23 min | **Legacy NAC Integration**    | Create connection, sync, event stream events                  | `/legacy-nac` pages      |
| 23-25 min | **Policy Translation** | Discover Legacy NAC policies → AI translate → apply              | `/legacy-nac/policies` page |
| 25-27 min | **Migration Wizard**   | Walk through 8-step zero-touch migration                      | `/legacy-nac/wizard` page |
| 27-30 min | **Monitoring**         | Grafana dashboard, Prometheus queries, topology health matrix | http://localhost:3000   |

---

## Quick Reference — All Demo URLs

| Service           | URL                                                 | Purpose                         |
| ----------------- | --------------------------------------------------- | ------------------------------- |
| Web Dashboard     | http://localhost:3001                               | Main UI (33 pages)              |
| Topology View     | http://localhost:3001/topology                      | 4-tab environment visualization |
| API Swagger Docs  | http://localhost:8080/api/docs                      | Interactive API reference       |
| Topology API      | http://localhost:8080/api/v1/topology/              | Aggregated component data       |
| Health Matrix     | http://localhost:8080/api/v1/topology/health-matrix | Service health at a glance      |
| RADIUS Auth       | `localhost:1812/udp`                                | RADIUS authentication           |
| RADIUS Accounting | `localhost:1813/udp`                                | RADIUS accounting               |
| RadSec (TLS)      | `localhost:2083/tcp`                                | RADIUS over TLS                 |
| TACACS+           | `localhost:49/tcp`                                  | Device admin AAA                |
| CoA               | `localhost:3799/udp`                                | Change of Authorization         |
| Prometheus        | http://localhost:9092                               | Metrics collection              |
| Grafana           | http://localhost:3000                               | Monitoring dashboards           |
| NATS Monitor      | http://localhost:8222                               | Message bus status              |

## Seed Credentials Summary

| Username   | Password                 | Purpose                |
| ---------- | ------------------------ | ---------------------- |
| `testuser` | `testing123`             | RADIUS PAP test user   |
| `admin`    | `admin123`               | RADIUS admin test user |
| `admin`    | `changeme_grafana_admin` | Grafana dashboard      |

**NAD shared secret** for all test NADs: `testing123`

---

## Troubleshooting

| Issue                    | Fix                                                                                                                                  |                                         |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------- |
| RADIUS no response       | Check `docker logs neuranac-radius` — verify NAD IP is registered in `network_devices` table                                              |                                         |
| legacy connection refused   | Ensure ERS is enabled on NeuraNAC, check firewall/VPN connectivity                                                                        |                                         |
| Port 1812 already in use | Stop local FreeRADIUS: `sudo launchctl unload /Library/LaunchDaemons/*radius*`                                                       |                                         |
| Port 49 requires root    | macOS restricts ports < 1024. Remap in docker-compose: change `"49:49"` to `"10049:49"`                                              |                                         |
| DB seed fails            | Verify: `docker compose -f deploy/docker-compose.yml exec -T postgres psql -U neuranac -d neuranac -c "SELECT count(*) FROM network_devices;"` |                                         |
| Services unhealthy       | Check logs: `docker compose -f deploy/docker-compose.yml logs --tail=50 <service-name>`                                              |                                         |
| Topology shows unhealthy | Run `curl localhost:8080/api/v1/topology/health-matrix \                                                                             | jq` to identify which component is down |
| AI Engine unavailable    | Check `docker logs neuranac-ai` — ensure port 8081 is not in use by another process                                                       |                                         |
| No JWT token             | Re-run the auth/login step — tokens expire after the configured TTL                                                                  |                                         |
