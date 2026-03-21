# NeuraNAC Deployment Guide & Runbooks

## Quick Start (Development)

```bash
# 1. Clone and configure
cp .env.example .env
# Edit .env with your secrets

# 2. Start all services
cd deploy
docker-compose up -d

# 3. Verify health
curl http://localhost:8080/health
curl http://localhost:8082/health   # Policy Engine
curl http://localhost:8083/health   # AI Engine
curl http://localhost:9100/health   # Sync Engine

# 4. Access UI
open http://localhost:3001
# Login: admin / admin123
```

## Service Ports

| Service            | Port | Protocol |
| ------------------ | ---- | -------- |
| API Gateway        | 8080 | HTTP     |
| Web Dashboard      | 3001 | HTTP     |
| RADIUS Auth        | 1812 | UDP      |
| RADIUS Acct        | 1813 | UDP      |
| RadSec             | 2083 | TCP/TLS  |
| TACACS+            | 49   | TCP      |
| CoA                | 3799 | UDP      |
| Policy Engine API  | 8082 | HTTP     |
| Policy Engine gRPC | 9091 | gRPC     |
| AI Engine          | 8083 | HTTP     |
| Sync Engine gRPC   | 9090 | gRPC     |
| Sync Engine Health | 9100 | HTTP     |
| NeuraNAC Bridge         | 8090 | HTTP     |
| PostgreSQL         | 5432 | TCP      |
| Redis              | 6379 | TCP      |
| NATS               | 4222 | TCP      |
| NATS Monitor       | 8222 | HTTP     |
| Prometheus         | 9092 | HTTP     |
| Grafana            | 3000 | HTTP     |

## Deployment Scenarios

NeuraNAC supports 4 deployment topologies. Choose the one that matches your environment:

| #   | Scenario                        | NeuraNAC? | Mode         | Site Types     | Helm Overlay(s)                                                        |
| --- | ------------------------------- | ---- | ------------ | -------------- | ---------------------------------------------------------------------- |
| S1  | NeuraNAC + Hybrid (cloud + on-prem)  | Yes  | `hybrid`     | onprem + cloud | `values-onprem-hybrid.yaml` + `values-cloud-hybrid.yaml`               |
| S2  | Cloud only (no NeuraNAC)             | No   | `standalone` | cloud          | `values-cloud-standalone.yaml`                                         |
| S3  | On-prem only (no NeuraNAC)           | No   | `standalone` | onprem         | `values-onprem-standalone.yaml`                                        |
| S4  | Hybrid no NeuraNAC (cloud + on-prem) | No   | `hybrid`     | onprem + cloud | `values-hybrid-no-lnac-onprem.yaml` + `values-hybrid-no-lnac-cloud.yaml` |

### Architecture Diagram

```
┌─────────────── Customer Private Network ───────────────┐
│  ┌──────────────────┐                                  │    ┌──────────────────┐
│  │ NeuraNAC Dashboard    │                                  │    │ NeuraNAC Dashboard    │
│  │   (on-prem)      │                                  │    │   (cloud)        │
│  │ NeuraNAC (on-prem)    │ ◄═══════ federation ═══════►     │    │ NeuraNAC (cloud)      │
│  │                  │       (HMAC-SHA256 signed)        │    │                  │
│  │ NeuraNAC Bridge      │ ◄═══════ federation ═══════►     │    │ NeuraNAC Bridge      │
│  │  (NeuraNAC adapter)  │       (gRPC + NATS + mTLS)       │    │  (NeuraNAC-to-NeuraNAC)  │
│  └──────┬───────────┘                                  │    └──────────────────┘
│         │ ERS/Event Stream                                   │       ▲  ▲  ▲
│  ┌──────┴──┐                                           │    Node1 Node2 NodeN
│  │  NeuraNAC*   │  (* S1 only)                              │
│  └─────────┘                                           │
│      ▲  ▲  ▲                                           │
│   Node1 Node2 NodeN                                    │
└────────────────────────────────────────────────────────┘
```

### Scenario 1: NeuraNAC + Hybrid (Docker Compose)

```bash
# .env settings:
# DEPLOYMENT_MODE=hybrid
# NeuraNAC_ENABLED=true
# NEURANAC_SITE_TYPE=onprem
# NEURANAC_PEER_API_URL=http://api-gateway-cloud:8080
# FEDERATION_SHARED_SECRET=$(openssl rand -hex 32)

# Start on-prem (NeuraNAC Bridge auto-starts with NeuraNAC adapter enabled):
cd deploy
docker compose up -d
```

### Scenario 2: Cloud Only (Docker Compose)

```bash
# .env settings:
# DEPLOYMENT_MODE=standalone
# NeuraNAC_ENABLED=false
# NEURANAC_SITE_TYPE=cloud

cd deploy && docker compose up -d
```

### Scenario 3: On-Prem Only (Docker Compose)

```bash
# .env settings:
# DEPLOYMENT_MODE=standalone
# NeuraNAC_ENABLED=false
# NEURANAC_SITE_TYPE=onprem

cd deploy && docker compose up -d
```

### Scenario 4: Hybrid No NeuraNAC (Docker Compose)

```bash
# .env settings:
# DEPLOYMENT_MODE=hybrid
# NeuraNAC_ENABLED=false
# NEURANAC_SITE_TYPE=onprem
# NEURANAC_PEER_API_URL=http://api-gateway-cloud:8080
# FEDERATION_SHARED_SECRET=$(openssl rand -hex 32)

cd deploy
docker compose -f docker-compose.yml -f docker-compose.hybrid.yml up -d
```

---

## Production Deployment (Kubernetes)

### Prerequisites
- Kubernetes 1.28+
- Helm 3.12+
- cert-manager (for TLS certificates)
- External PostgreSQL 16+ (recommended)
- External Redis 7+ (recommended)

### Scenario 1: NeuraNAC + Hybrid (Helm)

```bash
# Generate shared secret
export FED_SECRET=$(openssl rand -hex 32)

# On-prem site (inside customer network, next to NeuraNAC)
helm install neuranac-onprem deploy/helm/neuranac/ \
  -f deploy/helm/neuranac/values-onprem-hybrid.yaml \
  --set global.legacyNacEnabled=true \
  --set global.peerApiUrl=https://cloud-neuranac.example.com \
  --set global.postgres.host=your-pg-host \
  --set global.postgres.password=your-secret \
  --namespace neuranac --create-namespace

# Cloud site
helm install neuranac-cloud deploy/helm/neuranac/ \
  -f deploy/helm/neuranac/values-cloud-hybrid.yaml \
  --set global.peerApiUrl=https://onprem-neuranac.customer.local \
  --set global.postgres.host=your-pg-host \
  --set global.postgres.password=your-secret \
  --namespace neuranac --create-namespace
```

### Scenario 2: Cloud Only (Helm)

```bash
helm install neuranac deploy/helm/neuranac/ \
  -f deploy/helm/neuranac/values-cloud-standalone.yaml \
  --set global.postgres.host=your-pg-host \
  --set global.postgres.password=your-secret \
  --namespace neuranac --create-namespace
```

### Scenario 3: On-Prem Only (Helm)

```bash
helm install neuranac deploy/helm/neuranac/ \
  -f deploy/helm/neuranac/values-onprem-standalone.yaml \
  --set global.postgres.host=your-pg-host \
  --set global.postgres.password=your-secret \
  --namespace neuranac --create-namespace
```

### Scenario 4: Hybrid No NeuraNAC (Helm)

```bash
export FED_SECRET=$(openssl rand -hex 32)

# On-prem side
helm install neuranac-onprem deploy/helm/neuranac/ \
  -f deploy/helm/neuranac/values-hybrid-no-lnac-onprem.yaml \
  --set global.peerApiUrl=https://cloud-neuranac.example.com \
  --set global.postgres.host=your-pg-host \
  --namespace neuranac --create-namespace

# Cloud side
helm install neuranac-cloud deploy/helm/neuranac/ \
  -f deploy/helm/neuranac/values-hybrid-no-lnac-cloud.yaml \
  --set global.peerApiUrl=https://onprem-neuranac.customer.local \
  --set global.postgres.host=your-pg-host \
  --namespace neuranac --create-namespace
```

### On-Prem Twin Nodes (HA within a single site)

```bash
# Node A
helm install neuranac-a deploy/helm/neuranac -f deploy/helm/neuranac/values-onprem-standalone.yaml \
  --set global.nodeId=twin-a \
  --set syncEngine.peerAddress=twin-b:9090

# Node B
helm install neuranac-b deploy/helm/neuranac -f deploy/helm/neuranac/values-onprem-standalone.yaml \
  --set global.nodeId=twin-b \
  --set syncEngine.peerAddress=twin-a:9090
```

## Runbooks

### Runbook 1: Service Not Starting

```bash
# Check container logs
docker logs neuranac-radius
docker logs neuranac-api
docker logs neuranac-policy

# Check DB connectivity
docker exec neuranac-postgres pg_isready -U neuranac

# Check Redis
docker exec neuranac-redis redis-cli -a neuranac_dev_password ping

# Check NATS
curl http://localhost:8222/healthz
```

### Runbook 2: RADIUS Authentication Failures

```bash
# Check RADIUS logs
docker logs neuranac-radius | grep -i "auth"

# Verify NAD is registered
curl http://localhost:8080/api/v1/network-devices

# Test with radtest
radtest testuser testing123 localhost 0 testing123

# Check policy engine
curl http://localhost:8082/health
curl -X POST http://localhost:8082/evaluate -H 'Content-Type: application/json' \
  -d '{"tenant_id":"00000000-0000-0000-0000-000000000000","auth_context":{"username":"testuser"}}'
```

### Runbook 3: Sync Engine Issues

```bash
# Check sync status
curl http://localhost:9100/sync/status

# Trigger manual sync
curl -X POST http://localhost:9100/sync/trigger

# Check sync journal
docker exec neuranac-postgres psql -U neuranac -c "SELECT count(*) FROM sync_journal WHERE NOT delivered"
```

### Runbook 4: AI Engine Not Responding

```bash
# Check health
curl http://localhost:8083/health

# Test profiling
curl -X POST http://localhost:8083/api/v1/profile \
  -H 'Content-Type: application/json' \
  -d '{"mac":"AA:BB:CC:DD:EE:FF","vendor":"Cisco","dhcp_hostname":"switch01"}'

# Test anomaly detection
curl -X POST http://localhost:8083/api/v1/anomaly/analyze \
  -H 'Content-Type: application/json' \
  -d '{"endpoint_mac":"AA:BB:CC:DD:EE:FF","username":"testuser","nas_ip":"10.0.0.1"}'
```

### Runbook 5: Certificate Expiry

```bash
# Check for expiring certificates
curl "http://localhost:8080/api/v1/certificates?expiring_within_days=30"

# Generate new certificate
curl -X POST http://localhost:8080/api/v1/certificates/generate \
  -H 'Content-Type: application/json' \
  -d '{"subject":"CN=neuranac-server","usage":"server","validity_days":365}'
```

### Runbook 6: Database Maintenance

```bash
# Check DB size
docker exec neuranac-postgres psql -U neuranac -c "SELECT pg_size_pretty(pg_database_size('neuranac'))"

# Check table sizes
docker exec neuranac-postgres psql -U neuranac -c "
  SELECT relname, pg_size_pretty(pg_total_relation_size(relid))
  FROM pg_catalog.pg_statio_user_tables ORDER BY pg_total_relation_size(relid) DESC LIMIT 20"

# Vacuum
docker exec neuranac-postgres psql -U neuranac -c "VACUUM ANALYZE"

# Check active sessions
docker exec neuranac-postgres psql -U neuranac -c "SELECT count(*) FROM sessions WHERE is_active"
```

### Runbook 7: Performance Monitoring

```bash
# Prometheus metrics
curl http://localhost:8080/metrics

# Grafana dashboards
open http://localhost:3000  # admin / admin

# System status
curl http://localhost:8080/api/v1/diagnostics/system-status
```

## Environment Variables

### Core

| Variable            | Default                | Description                  |
| ------------------- | ---------------------- | ---------------------------- |
| `NeuraNAC_ENV`           | production             | Environment (dev/production) |
| `NEURANAC_NODE_ID`       | twin-a                 | Node identifier for sync     |
| `POSTGRES_HOST`     | postgres               | PostgreSQL hostname          |
| `POSTGRES_PORT`     | 5432                   | PostgreSQL port              |
| `POSTGRES_DB`       | neuranac                    | Database name                |
| `POSTGRES_USER`     | neuranac                    | Database user                |
| `POSTGRES_PASSWORD` | neuranac_dev_password       | Database password            |
| `REDIS_HOST`        | redis                  | Redis hostname               |
| `REDIS_PORT`        | 6379                   | Redis port                   |
| `REDIS_PASSWORD`    | neuranac_dev_password       | Redis password               |
| `NATS_URL`          | nats://nats:4222       | NATS connection URL          |
| `SYNC_PEER_ADDRESS` |                        | Peer node address for sync   |
| `LLM_API_URL`       | http://localhost:11434 | Ollama/LLM endpoint          |
| `LLM_MODEL`         | llama3                 | LLM model name               |
| `API_CORS_ORIGINS`  | http://localhost:5173  | Allowed CORS origins         |

### Hybrid / NeuraNAC / Federation

| Variable                   | Default      | Scenarios | Description                                 |
| -------------------------- | ------------ | --------- | ------------------------------------------- |
| `DEPLOYMENT_MODE`          | `standalone` | All       | `standalone` or `hybrid`                    |
| `NeuraNAC_ENABLED`              | `false`      | S1        | Enable NeuraNAC features                         |
| `NEURANAC_SITE_TYPE`            | `onprem`     | All       | `onprem` or `cloud`                         |
| `NEURANAC_SITE_ID`              | `0000...01`  | All       | UUID of this site                           |
| `NEURANAC_PEER_API_URL`         | (empty)      | S1, S4    | Peer site API URL                           |
| `NeuraNAC_CONNECTOR_URL`        | (empty)      | S1        | Bridge Connector URL (deprecated — use Bridge) |
| `BRIDGE_URL`               | (empty)      | All       | NeuraNAC Bridge service URL                      |
| `FEDERATION_SHARED_SECRET` | (empty)      | S1, S4    | HMAC-SHA256 secret for cross-site auth      |

### NeuraNAC Bridge

| Variable                       | Default                 | Description                                |
| ------------------------------ | ----------------------- | ------------------------------------------ |
| `NEURANAC_BRIDGE_BRIDGE_NAME`       | neuranac-bridge-01           | Bridge instance name                       |
| `NEURANAC_BRIDGE_SITE_ID`           | `0000...01`             | UUID of this site                          |
| `NEURANAC_BRIDGE_TENANT_ID`         | `0000...00`             | UUID of the tenant                         |
| `NEURANAC_BRIDGE_CLOUD_NeuraNAC_API_URL` | `http://localhost:8080` | Cloud API Gateway URL                      |
| `NEURANAC_BRIDGE_DEPLOYMENT_MODE`   | `standalone`            | `standalone` or `hybrid`                   |
| `NEURANAC_BRIDGE_SITE_TYPE`         | `onprem`                | `onprem` or `cloud`                        |
| `NEURANAC_BRIDGE_NeuraNAC_ENABLED`       | `false`                 | Enable NeuraNAC adapter                         |
| `NEURANAC_BRIDGE_NeuraNAC_HOSTNAME`      | `legacy-nac.local`      | Legacy NAC hostname (if adapter enabled)             |
| `NEURANAC_BRIDGE_PEER_API_URL`      | (empty)                 | Peer site API URL (for NeuraNAC-to-NeuraNAC adapter) |
| `NEURANAC_BRIDGE_PEER_GRPC_ADDRESS` | (empty)                 | Peer gRPC address (for NeuraNAC-to-NeuraNAC adapter) |
| `NEURANAC_BRIDGE_NATS_URL`          | `nats://localhost:4222` | NATS URL for event bridging                |
| `NEURANAC_BRIDGE_SIMULATED`         | `true`                  | Simulated mode (no real NeuraNAC/peer)          |
| `NEURANAC_BRIDGE_ACTIVATION_CODE`   | (empty)                 | Zero-trust activation code                 |

## Security Checklist

- [ ] Change all default passwords in `.env`
- [ ] Enable TLS for all external-facing services
- [ ] Configure RadSec for RADIUS over TLS
- [ ] Set up certificate rotation (90-day cycle recommended)
- [ ] Enable audit log tamper-proof chain verification
- [ ] Configure SIEM forwarding for security events
- [ ] Set up rate limiting appropriate for your environment
- [ ] Review and customize OWASP security headers
- [ ] Enable BYOD certificate provisioning
- [ ] Configure backup for PostgreSQL data
