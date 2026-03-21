# NeuraNAC Codebase Audit — Purely From Code Analysis

**Date:** 2026-03-04 (Updated: 2026-03-05)  
**Method:** Direct source code inspection only (no documentation referenced)

---

## 1. GA Readiness (From Code)

### Implemented and Functional:

| Area                   | Evidence                                                               | Status                             |
| ---------------------- | ---------------------------------------------------------------------- | ---------------------------------- |
| RADIUS Auth (PAP, MAB) | `handler.go` — full flow with bcrypt verify, endpoint lookup           | ✅ Production-ready                |
| EAP State Machine      | `handler.go` + `eaptls/` — Identity→Challenge→Success, real crypto/tls | ✅ Real TLS handshake via net.Pipe |
| TACACS+                | `tacacs.go` — encrypted TCP, auth/author/acct, bcrypt                  | ✅ Basic flow works                |
| Policy Engine          | `engine.py` — 12 operators, tenant-scoped, priority-ordered            | ✅ Functional                      |
| gRPC Integration       | `grpc_server.py` — Evaluate + BatchEvaluate, dual-mode                 | ✅                                 |
| API Gateway            | `main.py` — 30 routers, 11 middleware, JWT RS256                       | ✅ Comprehensive                   |
| Multi-Tenant           | V006 migration + `tenant_helper.py` — row-level isolation              | ✅                                 |
| AI Engine              | 16 modules, API key rotation, DI container                             | ✅ Feature-rich                    |
| NeuraNAC Coexistence        | `legacy_nac_enhanced.py` + V002 — sync, Event Stream, migration                     | ✅ Full CRUD                       |
| Hybrid Federation      | `federation.py` — HMAC-SHA256, replay protection, circuit breaker      | ✅                                 |
| NeuraNAC Bridge             | 3 adapters (NeuraNAC, NeuraNAC-to-NeuraNAC, REST), pluggable pattern                  | ✅                                 |
| Web Dashboard          | 33 pages, AI mode toggle, NeuraNAC guard                                    | ✅                                 |
| Monitoring             | 18 Prometheus counters + 3 histograms + Grafana                        | ✅                                 |
| CI/CD                  | 11 jobs: lint, test, security, build, SBOM                             | ✅                                 |

### Incomplete/Simulated in Code:

| Gap                   | What's There                                                                             | Status                     |
| --------------------- | ---------------------------------------------------------------------------------------- | -------------------------- |
| EAP-TLS TLS Handshake | `eaptls/eaptls.go` — real `crypto/tls` via `net.Pipe`, cipher negotiation, cert exchange | ✅ FIXED                   |
| PEAP/TTLS Inner Auth  | `mschapv2/mschapv2.go` — full RFC 2759 with NT hash, DES, inline MD4                     | ✅ FIXED                   |
| RadSec                | `radsec.go` — TLS listener reads/parses/handles RADIUS packets (was already working)     | ✅ Was implemented         |
| CoA Sending           | `handler.go` — real UDP CoA via `CoASenderInterface` + NATS event stream                 | ✅ FIXED                   |
| LDAP/AD               | `ldap_connector.py` — connection pooling, bind auth, group search, nested groups         | ✅ FIXED                   |
| Guest Portal          | `guest.py` — captive portal, BYOD registration, sponsor groups (was already working)     | ✅ Was implemented         |
| CHAP Auth             | `handler.go:handleCHAP()` — RFC 2865 MD5 verification                                    | ✅ FIXED                   |
| Data Retention        | `data_purge.py` — 10 retention policies, batched deletes, scheduler                      | ✅ FIXED                   |
| Posture               | Schema with conditions, grace periods                                                    | ⚠️ No agent communication |
| K8s Operator          | Go binary with CRD skeleton                                                              | ⚠️ Stub only              |

### Hardcoded Dev Values:

| File                   | Value                                                          | Risk   |
| ---------------------- | -------------------------------------------------------------- | ------ |
| `config.py:45`         | `api_secret_key = "dev_secret_key_change_in_production_min32"` | HIGH   |
| `config.py:48`         | `jwt_secret_key = "dev_jwt_secret..."`                         | HIGH   |
| `ai-engine main.py:57` | `AI_ENGINE_API_KEY = "neuranac_ai_dev_key_change_in_production"`    | HIGH   |
| `config.py:31,37`      | Default DB/Redis passwords `neuranac_dev_password`                  | MEDIUM |

**GA Score: ~88% for production NAC, ~95% for demo/POC**

---

## 2. NAC Features From Code

### Authentication (from `handler.go`, `tacacs.go`)

- **PAP** — Full: User-Password extraction, bcrypt verify against `internal_users`
- **MAB** — Full: MAC normalization, endpoint lookup, auto-register
- **EAP-TLS** — Full: State machine + real `crypto/tls` handshake via `eaptls/` package
- **EAP-TTLS** — Full: Outer tunnel + MSCHAPv2 inner auth via `mschapv2/` package
- **PEAP** — Full: Same as TTLS with MSCHAPv2
- **CHAP** — Full: RFC 2865 MD5(ident + password + challenge) verification
- **TACACS+ Auth** — Full: Username/password, multi-step prompt, bcrypt
- **TACACS+ Author** — Basic: Privilege level based (0-14 read-only, 15 full)
- **TACACS+ Acct** — Basic: Start/Stop logging
- **AI Agent Auth** — Vendor-Specific attr 26 validates agent status

### Policy & Authorization (from `engine.py`, `policy.proto`)

- 12 condition operators (equals, contains, regex, in, between, etc.)
- 5 decision types: permit, deny, quarantine, redirect, continue
- Authorization profiles: VLAN, SGT, DACL, iPSK, CoA, bandwidth, redirect, session timeout, vendor attrs
- gRPC with circuit breaker (5 failures → 30s open) + DB fallback
- Tenant-scoped, priority-ordered evaluation

### Segmentation (from V001 schema)

- Security Groups (SGTs) with tag values and `is_ai_sgt` flag
- Adaptive policies (source SGT → dest SGT → action) — TrustSec matrix
- VLANs (site-scoped), ACLs (JSONB entries)

### AI-Aware NAC (from `handler.go`, AI Engine)

- Inline profiling (async goroutine, 3s timeout)
- Inline risk scoring (synchronous; critical → quarantine)
- Policy drift recording
- Anomaly detection (time/day behavioral baseline; anomalous → quarantine)
- Shadow AI detection, TLS fingerprinting (JA3/JA4)
- NL-to-SQL, adaptive risk, capacity planning, playbooks, model registry

### Certificate Management

- Hierarchical CA, cert lifecycle (issue, revoke, CRL, OCSP)
- Per-tenant ECDSA P-256 certs with SPIFFE URIs
- mTLS for bridge trust

### Legacy NAC Integration

- Connection management, bidirectional sync, entity mapping (SHA-256 change detection)
- Event Stream consumption (simulated mode), migration wizard, policy translation
- Sync scheduling, conflict resolution, RADIUS traffic analysis

---

## 3. Architecture (From Code)

**7 Microservices:**

| Service       | Language            | Port(s)                     | Role                                |
| ------------- | ------------------- | --------------------------- | ----------------------------------- |
| API Gateway   | Python/FastAPI      | 8080                        | REST API, 30 routers, 11 middleware |
| RADIUS Server | Go                  | 1812/1813/2083/49/3799/9100 | RADIUS/TACACS+ auth                 |
| Policy Engine | Python/FastAPI+gRPC | 8082/9091                   | Rule evaluation                     |
| AI Engine     | Python/FastAPI      | 8081                        | 16 ML modules                       |
| Sync Engine   | Go/gRPC             | 9090/9100                   | Multi-site replication              |
| NeuraNAC Bridge    | Python/FastAPI      | 8090                        | Pluggable adapter bridge            |
| Web           | React/TypeScript    | 3001/80                     | 33-page SPA + AI mode               |

**Infrastructure:** PostgreSQL 16 (67 tables), Redis 7, NATS JetStream

**Communication:** gRPC (RADIUS↔Policy, Sync↔Sync), HTTP REST, NATS pub/sub, WebSocket (browser push)

**Middleware Stack (order matters):** CORS → LogCorrelation → OTelTracing → SecurityHeaders → PrometheusMetrics → InputValidation → RateLimit → APIKey → Auth → BridgeTrust → Tenant → Federation

---

## 4. End-to-End Data Flow

### RADIUS Auth Flow (from `handler.go`):

1. Switch → RADIUS Server (UDP 1812) Access-Request
2. `HandleRadius()`: NAD lookup → shared secret verify → detect auth type
3. EAP/MAB/PAP handler executes (state machine for EAP)
4. AI Agent check if Vendor-Specific attr present
5. Policy eval via gRPC (circuit breaker + DB fallback) → VLAN, SGT, decision
6. AI inline: profiling (async), risk scoring, drift recording, anomaly detection
7. Build Access-Accept (VLAN + SGT attrs) or Access-Reject
8. Post: Real UDP CoA to NAS (disconnect/reauth) + NATS event, session event, metrics

### API Request Flow:

1. Browser → API Gateway :8080 with Bearer JWT
2. Middleware chain: auth → rate limit → tenant → federation
3. Router → SQLAlchemy async → PostgreSQL → JSON response

### Sync Flow:

1. DB change → sync_journal row
2. Sync Engine polls undelivered changes
3. gRPC stream to peer (mTLS + gzip)
4. Peer applies, resolves conflicts (vector clocks)

---

## 5. Deployment Architecture

### Docker Compose: 7 app services + 3 infra + 4 monitoring + 1 demo

### Helm/K8s:
- 11 templates, 4 deployment overlays (onprem/cloud × standalone/hybrid)
- Resource limits defined per service (RADIUS: 500m-2000m CPU, 512Mi-2Gi RAM)
- NetworkPolicies, health probes, HPA template

### CI/CD (11 GitHub Actions jobs):
lint → test-go → test-python → test-web → validate-helm → integration → e2e → load-test → security-scan → build-images (SBOM)

---

## 6. Scale & Performance

| Aspect               | Detail                                                                   |
| -------------------- | ------------------------------------------------------------------------ |
| **Connection Pools** | RADIUS: pgx min=5/max=50, Redis pool=50; Policy: asyncpg 2-10            |
| **Rate Limiting**    | Redis sliding window: auth=30/min, AI=200/min, default=100/min           |
| **Circuit Breakers** | Policy gRPC: 5 failures→30s; Federation: 3 failures→30s                  |
| **Timeouts**         | AI calls: 3s; Federation proxy: 10s; EAP state TTL: 60s                  |
| **Metrics**          | 18 counters + 2 gauges + 3 histograms (Prometheus)                       |
| **Replicas**         | Helm: RADIUS=2, API=2, Policy=2, AI=1, Sync=1, Bridge=1                  |
| **Concern**          | AI risk/anomaly calls are synchronous — adds latency to auth             |
| **HPA**              | 3 HPAs configured (API GW, RADIUS, AI) with scale-up/down policies       |
| **Observability**    | Loki + Promtail log aggregation, OTel collector with tail-based sampling |
| **Concern**          | No DB read replicas, no Redis HA                                         |

---

## 7. Demo Capability

**Available:** `setup.sh`, `demo.sh`, demo-tools container, sanity runner (377+ tests), seed data, setup wizard UI, AI mode toggle, simulated NeuraNAC bridge

**Can Demo:** PAP/MAB auth, policy evaluation, AI chat, migration wizard, multi-site federation, session monitoring, topology view

**Cannot Demo:** Physical NAD integration (needs hardware), posture agent validation

---

## 8. Production Deployment Readiness

**Ready:** Dockerfiles (multi-stage, non-root), Helm charts, secret rotation script, health probes, monitoring (25 alerts), structured logging, CI/CD, backup/restore, NetworkPolicies, mTLS

**Not Ready:** No DB HA/replication, no Redis HA, hardcoded dev secrets (must override), no API TLS (needs external termination), `sslmode=disable` default (configurable via env), K8s operator is stub

**Now Ready:** Log aggregation (Loki+Promtail config), distributed tracing (OTel collector), HPA autoscaling (3 HPAs), request body size limits middleware, AI circuit breaker degradation

---

## 9. Quality Summary

| Metric                | Value                                          |
| --------------------- | ---------------------------------------------- |
| Unit tests            | ~558 across all services                       |
| CI coverage threshold | 70% (enforced)                                 |
| Integration tests     | 5 files (Python + Go)                          |
| E2E tests             | 10 Playwright specs                            |
| Load tests            | 1 k6 script                                    |
| Sanity tests          | 377+ scenarios                                 |
| Linting               | ruff (Python), golangci-lint (Go), ESLint (TS) |
| Security scanning     | Trivy + TruffleHog + pip-audit                 |

---

## 10. Critical Gaps

### Protocol Gaps — ALL FIXED:
1. **Real TLS in EAP-TLS** — ✅ `eaptls/eaptls.go` with `crypto/tls` handshaker, cipher negotiation, cert exchange
2. **MSCHAPv2 for PEAP/TTLS** — ✅ `mschapv2/mschapv2.go` with full RFC 2759 crypto, inline MD4, DES
3. **CoA packet sending** — ✅ `handler.go` wired to `CoASenderInterface`, real UDP + NATS events
4. **RadSec processing** — ✅ Was already implemented (`radsec.go` reads/parses/handles packets)
5. **LDAP/AD connector** — ✅ `ldap_connector.py` with pooling, bind auth, group search, nested groups

### Feature Gaps — MOSTLY FIXED:
- ✅ Guest portal (captive portal, BYOD, sponsor groups — was already implemented)
- ✅ CHAP authentication (RFC 2865 MD5 verification in `handler.go`)
- ✅ Data purge jobs (`data_purge.py` with 10 retention policies + scheduler)
- ⚠️ Posture agent (schema exists, no agent communication)
- ⚠️ EAP-FAST/SIM/AKA (not needed for most enterprise deployments)

### Operational Gaps — MOSTLY FIXED:
- ✅ Log aggregation config (`promtail-config.yml` → Loki)
- ✅ Tracing collector config (`otel-collector-config.yml` with tail sampling)
- ✅ HPA autoscaling (3 HPAs in `hpa.yaml`)
- ✅ DB SSL mode (configurable via `POSTGRES_SSL_MODE` env)
- ✅ Request body size limits (`request_limits.py` middleware)
- ✅ AI graceful degradation (circuit breaker in `ai_client.go`)
- ⚠️ No DB HA/replication, no Redis HA (requires infrastructure changes)

---

## 11. Bottom Line

The NeuraNAC codebase is a **comprehensive NAC platform architecture** with strong API design, multi-tenancy, AI integration, migration, and hybrid federation. The middleware stack, policy engine, monitoring, and CI/CD are production-grade.

**All 5 protocol gaps have been fixed.** The RADIUS server now has real `crypto/tls` for EAP-TLS, full MSCHAPv2 for PEAP/TTLS, real UDP CoA sending, CHAP support, and an LDAP/AD connector. Operational gaps (observability, autoscaling, request limits, AI degradation) have also been addressed.

**Remaining items for full production:** DB HA/replication, Redis HA, posture agent, K8s operator. These are infrastructure-level items that require environment-specific decisions rather than code changes.

### New Files Created:
| File                                           | Purpose                                                 |
| ---------------------------------------------- | ------------------------------------------------------- |
| `radius-server/internal/eaptls/eaptls.go`      | Real TLS handshaker using `crypto/tls` + `net.Pipe`     |
| `radius-server/internal/mschapv2/mschapv2.go`  | Full RFC 2759 MSCHAPv2 with inline MD4                  |
| `api-gateway/app/services/ldap_connector.py`   | LDAP/AD connector with pooling, bind auth, group search |
| `api-gateway/app/services/data_purge.py`       | Data retention purge service with 10 policies           |
| `api-gateway/app/middleware/request_limits.py` | Request body size + pagination limits middleware        |
| `deploy/monitoring/promtail-config.yml`        | Promtail log collection for Loki                        |
| `deploy/monitoring/otel-collector-config.yml`  | OTel Collector with tail-based sampling                 |

### Modified Files:
| File                 | Change                                                           |
| -------------------- | ---------------------------------------------------------------- |
| `handler.go`         | CoASenderInterface, SetCoASender(), handleCHAP(), wired real CoA |
| `ai_client.go`       | Circuit breaker (3 fails → 30s open, auto-recover)               |
| `coa.go`             | Removed circular import (handler param from ListenForResponses)  |
| `cmd/server/main.go` | Wire CoA sender into handler on startup                          |
| `go.mod`             | Added `golang.org/x/text` as direct dependency                   |
