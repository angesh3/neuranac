# Changelog

All notable changes to the NeuraNAC (Identity & Context Manager) project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-03-03

### Added

#### Hybrid Multi-Site Architecture (4 Deployment Scenarios)
- **S1: NeuraNAC + Hybrid** — On-prem + cloud with NeuraNAC Connector, federation, HMAC-SHA256 auth
- **S2: Cloud only** — Standalone cloud deployment, no NeuraNAC
- **S3: On-prem only** — Standalone on-prem twin-node HA, no NeuraNAC
- **S4: Hybrid no NeuraNAC** — Cross-site federation without NeuraNAC dependency
- Federation Middleware — HMAC-SHA256 signed inter-site requests, 60s replay protection, circuit breaker
- NeuraNAC Connector service — On-prem NeuraNAC proxy with registration, heartbeat, outbound WS tunnel
- Site management API (`/api/v1/sites`, `/api/v1/connectors`, `/api/v1/config/ui`)
- NeuraNACGuard component — Route-level legacy NAC page guarding based on `legacyNacEnabled`
- Site/deployment awareness in RADIUS Server (`NEURANAC_SITE_ID`, `NEURANAC_SITE_TYPE`, `DEPLOYMENT_MODE`)
- Site/deployment awareness in Policy Engine (site context in evaluation)
- Helm overlay values for all 4 scenarios (`values-onprem-hybrid.yaml`, `values-cloud-standalone.yaml`, etc.)
- Docker Compose hybrid overlay (`docker-compose.hybrid.yml`)
- `setup.sh` auto-detects hybrid/NeuraNAC mode and adds `--profile legacy_nac`

#### Testing & Validation
- 407 sanity tests (30 new per-scenario S1–S4 validation tests)
- Unit tests for RADIUS `SiteID`/`SiteType`/`DeploymentMode` config loading
- Unit tests for Policy Engine site context initialization
- 5 per-scenario federation integration tests
- Federation startup validation (warns on missing/weak secrets in hybrid mode)

#### Observability
- 25 alerting rules across 5 groups (added `neuranac_federation_alerts` group)
- Federation alerts: peer unreachable, signature rejected, latency, NeuraNAC Connector down, sync replication lag
- All federation alerts include `site_id` label for multi-site correlation

#### Documentation
- `docs/DEPLOYMENT.md` — 4-scenario deployment guide with Docker Compose and Helm commands
- `docs/DEMO_GUIDE.md` — Per-scenario demo walkthroughs (S1–S4)
- `docs/GA_READINESS_REPORT.md` — Updated to ~95% confidence with scenario coverage matrix
- `docs/HYBRID_ARCHITECTURE_REPORT.md` — ASCII architecture diagram, env var table, design decisions
- Updated `README.md` — Hybrid topology diagrams, scenario table, 65-table schema, v1.0.0 version

### Changed
- Version bumped to **1.0.0** (API Gateway FastAPI metadata + startup log)
- Database schema: 65 tables (added V003 singleton rows, V004 hybrid tables: `neuranac_sites`, `neuranac_connectors`, `neuranac_node_registry`, `neuranac_deployment_config`)
- Alerting rules expanded from 20 → 25 (5 federation alerts with `site_id` labels)
- Sanity tests expanded from 377 → 407 (30 deployment scenario tests)

---

## [0.1.0] - 2026-02-28

### Added

#### Core Services
- **RADIUS Server** — Full RADIUS authentication (EAP-TLS, EAP-TTLS, PEAP, PAP, MAB), accounting, CoA, and RadSec (TLS 1.3, mutual auth)
- **API Gateway** — FastAPI-based REST API with JWT auth, rate limiting, RBAC, input validation, security headers, and metrics
- **Policy Engine** — gRPC-based policy evaluation with NATS live reload, mTLS support, circuit breaker fallback
- **AI Engine** — Inline profiling, risk scoring, anomaly detection, NL-to-SQL, RAG troubleshooter, playbooks, model registry, A/B testing
- **Sync Engine** — Twin-node gRPC replication with journal-based sync, cursor pagination, hub-spoke topology, mTLS
- **Web Dashboard** — React + TypeScript + TailwindCSS with AI mode toggle, NeuraNAC integration pages, onboarding checklist

#### NeuraNAC Integration
- 6 NeuraNAC pages: Integration overview, Migration Wizard, Sync Conflicts, RADIUS Analysis, Event Stream, Policy Translation
- Real-time event stream WebSocket consumer with STOMP protocol and auto-reconnect
- Shared NeuraNAC connection store with localStorage persistence
- Toast notification system across all NeuraNAC pages

#### AI Features
- 4-phase AI implementation: Backend foundation, Inline RADIUS, AI Mode UI, Advanced AI
- 45 intent action router with LLM fallback
- TLS fingerprinting (JA3/JA4), adaptive risk scoring, capacity planning
- Full-screen ChatGPT-like AI chat layout with polymorphic response cards

#### Infrastructure
- Docker Compose with health checks, dependency ordering, monitoring stack
- Helm charts with pinned image tags, startupProbes, resource limits, HPA, PDB, NetworkPolicies
- PostgreSQL streaming replication, Redis Sentinel, NATS JetStream clustering
- Prometheus + Grafana monitoring with comprehensive alerting rules (217 lines)
- Backup and secret rotation automation scripts

#### CI/CD
- GitHub Actions pipeline: lint, test (Go/Python/Web/Integration/E2E), Helm validation, k6 load tests, security scanning (Trivy, TruffleHog, pip-audit), SBOM generation
- Coverage enforcement: 70% for Go and Python
- k6 load tests with threshold enforcement

#### Testing
- 333+ sanity tests across all phases
- Unit tests for handler, config, store, crypto, sync service
- Integration tests for EAP-TLS state machine and RADIUS round-trip
- Web component tests (Layout, ErrorBoundary, stores, pages)
- Benchmarks for crypto and MAC normalization

#### Documentation
- `CONTRIBUTING.md` — Development setup, repo structure, code standards, PR process
- `docs/ARCHITECTURE_SCALE_REPORT.md` — Data flow diagrams, scale estimates
- `docs/AI_PHASES_REPORT.md` — AI implementation details
- `docs/SANITY_REPORT.md` — Test results
- `docs/INFRA_RESOURCE_REPORT.md` — Infrastructure resource planning

### Security
- AES-256-GCM encryption for shared secrets in Redis cache
- mTLS for gRPC inter-service communication (mandatory in production)
- Production guard: gRPC startup fails if mTLS certs missing in production
- Non-root containers with distroless/alpine base images
- Grafana admin password via environment variable (not hardcoded)
- bcrypt 72-byte truncation warning for PAP passwords

### Fixed
- Safe type assertions (comma-ok pattern) in HandleRadius/HandleAccounting — prevents panics
- Nil guard on NATS JetStream publish in triggerCoAIfNeeded
- PDB selector labels now match Deployment labels (`app.kubernetes.io/name`)
- Prometheus NATS scrape config points to nats-exporter
- Helm dry-run CI step no longer swallows errors (`|| true` removed)
- Sync engine health check reports DB and peer connection status
- gRPC policy client wired with automatic DB fallback on failure

## [Unreleased]

### Planned
- Bump Helm chart version to 1.0.0 for GA
- External secret management (Vault/AWS Secrets Manager)
- Chaos engineering tests (Litmus/Chaos Monkey)
- Formal pen-test and security audit
- SLA documentation and runbook expansion
