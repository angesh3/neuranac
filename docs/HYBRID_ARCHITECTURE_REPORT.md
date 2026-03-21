# NeuraNAC Hybrid Architecture Report

## Overview

The NeuraNAC Hybrid Architecture enables deployment across on-prem and cloud environments with cross-site federation, Bridge Connector bridging, and multi-node management.

## Deployment Scenarios

| #   | Scenario                 | Site Type | Mode       | NeuraNAC | Helm Overlay                                                           |
| --- | ------------------------ | --------- | ---------- | --- | ---------------------------------------------------------------------- |
| 1   | On-prem + NeuraNAC + Cloud    | onprem    | hybrid     | yes | `values-onprem-hybrid.yaml`                                            |
| 2   | Cloud only               | cloud     | standalone | no  | `values-cloud-standalone.yaml`                                         |
| 3   | On-prem only             | onprem    | standalone | no  | `values-onprem-standalone.yaml`                                        |
| 4   | On-prem + Cloud (no NeuraNAC) | onprem    | hybrid     | no  | `values-hybrid-no-lnac-onprem.yaml` + `values-hybrid-no-lnac-cloud.yaml` |

## Architecture Diagram

```
┌──────────────────── On-Prem Network ────────────────────┐
│                                                         │
│  ┌───────────┐  ┌───────────┐  ┌────────────┐  │
│  │ RADIUS    │  │ Policy    │  │ Sync Engine│  │
│  │ Server    │  │ Engine    │  │ (Node A)   │  │
│  │ site_id=1 │  │ site_id=1 │  │ site_id=1  │  │
│  └─────┬─────┘  └─────┬─────┘  └──────┬─────┘  │
│        │            │              │            │
│  ┌─────┴──────────┴──────────────┴─────┐  │
│  │  API Gateway (on-prem)                        │  │
│  │  DEPLOYMENT_MODE=hybrid  NeuraNAC_ENABLED=*        │  │
│  │  FEDERATION_SHARED_SECRET=<hmac-key>           │  │
│  └─────┬──────────────────────────────┬─────┘  │
│        │ ERS/Event Stream (S1 only)     │ Federation    │
│  ┌─────┴───────┐                │ (HMAC-256)    │
│  │ NeuraNAC          │                │               │
│  │ Connector*   │                │               │
│  └─────┬───────┘                │               │
│        │                        │               │
│  ┌─────┴─────┐                  │               │
│  │ Legacy NAC* │  (* S1 only)   │               │
│  └───────────┘                  │               │
└─────────────────────────────┬───────────────┘
                                 │
┌──────────────────── Cloud ───┬────────────────┐
│  ┌────────────────────────┴──────────────┐  │
│  │  API Gateway (cloud)                          │  │
│  │  DEPLOYMENT_MODE=hybrid  NEURANAC_SITE_TYPE=cloud   │  │
│  └─────┬──────────┬─────────────────┬────────┘  │
│        │            │                   │          │
│  ┌─────┴─────┐  ┌──┴─────────┐  ┌────┴─────┐  │
│  │ RADIUS    │  │ Policy      │  │ Sync      │  │
│  │ Server    │  │ Engine      │  │ Engine    │  │
│  │ site_id=2 │  │ site_id=2   │  │ site_id=2 │  │
│  └───────────┘  └────────────┘  └──────────┘  │
└─────────────────────────────────────────────────┘
```

## Architecture Components

### Database (V004 Migration)
- `neuranac_sites` — site registry (on-prem, cloud, paired)
- `neuranac_connectors` — Bridge Connector registration and status
- `neuranac_node_registry` — multi-node registry across sites
- `neuranac_deployment_config` — singleton deployment configuration
- Added `site_id` columns to existing tables

### API Gateway Extensions
- **`GET /api/v1/config/ui`** — deployment config for frontend
- **`/api/v1/sites/`** — site CRUD + peer status
- **`/api/v1/connectors/`** — Bridge Connector registration, heartbeat, status
- **`/api/v1/nodes/`** — multi-node registry with registration, heartbeat, drain, deregister
- **Federation middleware** — routes requests via `X-NeuraNAC-Site` header (local/peer/all)

### Bridge Connector Service (new microservice)
- Deployed on-prem next to Legacy NAC
- Outbound WebSocket tunnel to cloud NeuraNAC
- ERS API proxy + Event Stream event relay
- Self-registration + heartbeat with cloud API Gateway
- Simulated mode for dev/demo

### Sync Engine Updates
- `SiteID` and `DeploymentMode` config fields
- `ShouldConnectPeer()` — only connects in hybrid mode
- Enhanced startup logging with site context

### Frontend
- **`site-store.ts`** — Zustand store for UI config + site selection
- **`SiteSelector`** — Local/Peer/All pill selector (hidden in standalone)
- **`SiteManagementPage`** — sites, connectors, nodes tables
- **`api.ts`** — auto-attaches `X-NeuraNAC-Site` header
- **`Layout.tsx`** — SiteSelector in sidebar, conditional NeuraNAC nav

### AI Engine
- 4 new intents: `list_sites`, `peer_status`, `list_connectors`, `deployment_config`
- 1 new navigation intent: `go_sites`

## Environment Variables

| Variable                   | Default          | Description                         |
| -------------------------- | ---------------- | ----------------------------------- |
| `DEPLOYMENT_MODE`          | `standalone`     | `standalone` or `hybrid`            |
| `NeuraNAC_ENABLED`              | `false`          | Enable NeuraNAC features                 |
| `NEURANAC_SITE_ID`              | `00000000-...01` | UUID of this site                   |
| `NEURANAC_SITE_TYPE`            | `onprem`         | `onprem` or `cloud`                 |
| `NEURANAC_PEER_API_URL`         | (empty)          | Peer site API URL                   |
| `NeuraNAC_CONNECTOR_URL`        | (empty)          | Bridge Connector URL                   |
| `FEDERATION_SHARED_SECRET` | (empty)          | HMAC-SHA256 key for cross-site auth |

## File Inventory

### New Files (24)
| File                                                | Description             |
| --------------------------------------------------- | ----------------------- |
| `database/migrations/V004_hybrid_architecture.sql`  | Migration: 4 new tables |
| `services/api-gateway/app/routers/ui_config.py`     | UI config endpoint      |
| `services/api-gateway/app/routers/sites.py`         | Site management CRUD    |
| `services/api-gateway/app/routers/connectors.py`    | Connector registration  |
| `services/api-gateway/app/middleware/federation.py` | Cross-site federation   |
| `services/neuranac-connector/Dockerfile`                 | Bridge Connector container |
| `services/neuranac-connector/requirements.txt`           | Python dependencies     |
| `services/neuranac-connector/app/__init__.py`            | Package init            |
| `services/neuranac-connector/app/config.py`              | Connector config        |
| `services/neuranac-connector/app/main.py`                | FastAPI app             |
| `services/neuranac-connector/app/legacy_nac_proxy.py`           | ERS/Event Stream proxy        |
| `services/neuranac-connector/app/registration.py`        | Cloud registration      |
| `services/neuranac-connector/app/tunnel.py`              | WebSocket tunnel        |
| `services/neuranac-connector/app/routers/__init__.py`    | Package init            |
| `services/neuranac-connector/app/routers/health.py`      | Health endpoints        |
| `services/neuranac-connector/app/routers/relay.py`       | ERS relay endpoints     |
| `web/src/lib/site-store.ts`                         | Site Zustand store      |
| `web/src/components/SiteSelector.tsx`               | Site selector component |
| `web/src/pages/SiteManagementPage.tsx`              | Site management page    |
| `deploy/helm/neuranac/values-onprem-standalone.yaml`     | Helm overlay            |
| `deploy/helm/neuranac/values-cloud-standalone.yaml`      | Helm overlay            |
| `deploy/helm/neuranac/values-onprem-hybrid.yaml`         | Helm overlay            |
| `deploy/helm/neuranac/values-cloud-hybrid.yaml`          | Helm overlay            |
| `deploy/k8s/operator/main.go`                       | K8s operator stub       |

### Modified Files (14)
| File                                               | Changes                                                               |
| -------------------------------------------------- | --------------------------------------------------------------------- |
| `database/seeds/seed_data.sql`                     | Default site + deployment config rows                                 |
| `services/api-gateway/app/config.py`               | 5 new env vars + validation                                           |
| `services/api-gateway/app/main.py`                 | Register ui_config, sites, connectors routers + federation middleware |
| `services/api-gateway/app/routers/nodes.py`        | Rewritten for multi-node registry                                     |
| `services/api-gateway/app/routers/legacy_nac_enhanced.py` | NeuraNAC-enabled guard                                                     |
| `services/sync-engine/internal/config/config.go`   | SiteID, DeploymentMode, IsHybrid(), ShouldConnectPeer()               |
| `services/sync-engine/cmd/sync/main.go`            | Hybrid-aware peer connection                                          |
| `services/ai-engine/app/action_router.py`          | 4 new intents + 1 nav intent                                          |
| `web/src/lib/api.ts`                               | X-NeuraNAC-Site header interceptor                                         |
| `web/src/components/Layout.tsx`                    | SiteSelector, conditional NeuraNAC nav                                     |
| `web/src/App.tsx`                                  | /sites route                                                          |
| `deploy/docker-compose.yml`                        | Hybrid env vars + neuranac-connector service                               |
| `deploy/helm/neuranac/values.yaml`                      | global hybrid config + neuranacConnector section                           |
| `deploy/k8s/crds/neuranac-node.yaml`                    | siteId, deploymentMode, serviceType fields                            |
| `.github/workflows/ci.yml`                         | Bridge Connector lint/test/build + Helm overlay validation               |
| `scripts/sanity_runner.py`                         | 35 new hybrid tests                                                   |

## Sanity Tests

35 new tests in `hybrid` phase (hyb-01 to hyb-35):
- **UIConfig** (3): endpoint, deployment fields, legacy_nac_enabled
- **Sites** (5): list, create, get, peer status, delete
- **Connectors** (5): list, register, heartbeat, get, delete
- **Nodes** (5): list, register, heartbeat, drain, delete
- **Federation** (2): local header, all header
- **DB_V004** (4): 4 new tables exist
- **SeedData** (1): default site row
- **Legacy** (2): twin-status, sync-status fallback
- **AI_Intents** (3): list sites, peer status, list connectors
- **WebRoutes** (1): /sites page loads
- **Infra** (4): Dockerfile, Helm overlays, CRD

Run: `python3 scripts/sanity_runner.py --phase hybrid`

## Docker Compose

```bash
# Standalone (default)
docker compose up -d

# With Bridge Connector
docker compose --profile legacy-nac up -d

# Hybrid mode
DEPLOYMENT_MODE=hybrid NEURANAC_PEER_API_URL=https://cloud.example.com NeuraNAC_ENABLED=true \
  docker compose --profile legacy-nac up -d
```

## Helm Install

```bash
# On-prem standalone
helm install neuranac deploy/helm/neuranac/ -f deploy/helm/neuranac/values-onprem-standalone.yaml

# On-prem hybrid with NeuraNAC
helm install neuranac deploy/helm/neuranac/ -f deploy/helm/neuranac/values-onprem-hybrid.yaml

# Cloud hybrid
helm install neuranac deploy/helm/neuranac/ -f deploy/helm/neuranac/values-cloud-hybrid.yaml
```
