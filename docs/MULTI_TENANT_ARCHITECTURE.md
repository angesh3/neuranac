# Multi-Tenant SaaS Architecture

> NeuraNAC Cloud Manager — Tenant Isolation, Node Mapping, and Zero-Trust Security

## Overview

NeuraNAC implements a **row-level multi-tenant** architecture where every infrastructure resource (sites, nodes, connectors, activation codes) is scoped to a tenant via `tenant_id` foreign keys. The system enforces a critical invariant:

- **One tenant → many nodes** (horizontal scaling)
- **One node → exactly one tenant** (isolation guarantee)

## Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         NeuraNAC Control Plane                                │
│                                                                          │
│  ┌─────────────┐   ┌──────────────┐   ┌──────────────────────────────┐  │
│  │  Tenant      │   │  Node        │   │  Certificate                 │  │
│  │  Provisioner │   │  Mapper      │   │  Issuer                      │  │
│  │  (CRUD +     │   │  (Allocate + │   │  (Per-tenant mTLS,           │  │
│  │   Quotas)    │   │   Rebalance) │   │   SPIFFE URIs)               │  │
│  └──────┬───────┘   └──────┬───────┘   └──────────┬───────────────────┘  │
│         │                  │                       │                      │
│  ┌──────▼──────────────────▼───────────────────────▼───────────────────┐  │
│  │                    PostgreSQL (tenant_id on all tables)              │  │
│  │                                                                      │  │
│  │  tenants ──┬── neuranac_sites ──── neuranac_connectors ──── neuranac_node_registry │  │
│  │            ├── neuranac_tenant_quotas                                     │  │
│  │            ├── neuranac_tenant_node_map (allocation ledger)               │  │
│  │            ├── neuranac_activation_codes                                  │  │
│  │            └── neuranac_connector_trust (mTLS certs)                      │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────┘

  Tenant A                          Tenant B
  ┌──────────────────┐              ┌──────────────────┐
  │  neuranac-acme-corp   │ (namespace)  │  neuranac-globex-inc  │
  │                  │              │                  │
  │  ┌────┐ ┌────┐  │              │  ┌────┐          │
  │  │Node│ │Node│  │              │  │Node│          │
  │  │ 1  │ │ 2  │  │              │  │ 1  │          │
  │  └──┬─┘ └──┬─┘  │              │  └──┬─┘          │
  │     │      │    │              │     │            │
  │  ┌──▼──────▼──┐ │              │  ┌──▼──────────┐ │
  │  │ NeuraNAC Bridge │ │              │  │ NeuraNAC Bridge  │ │
  │  │ (NeuraNAC+NeuraNAC)  │ │              │  │ (REST only) │ │
  │  └────────────┘ │              │  └─────────────┘ │
  └──────────────────┘              └──────────────────┘
```

## Database Schema (V006)

Migration `V006_multi_tenant_saas.sql` adds:

| Change | Table                   | Description                                                     |
| ------ | ----------------------- | --------------------------------------------------------------- |
| ALTER  | `neuranac_sites`             | Add `tenant_id` FK → `tenants(id)`                              |
| ALTER  | `neuranac_connectors`        | Add `tenant_id` FK, widen `connector_type` CHECK                |
| ALTER  | `neuranac_node_registry`     | Add `tenant_id` FK + unique constraint (1 node → 1 tenant)      |
| ALTER  | `neuranac_activation_codes`  | Add `tenant_id` FK, widen `connector_type` CHECK                |
| ALTER  | `neuranac_connector_trust`   | Add `tenant_id` FK                                              |
| ALTER  | `neuranac_deployment_config` | Add `tenant_id` FK (per-tenant config)                          |
| CREATE | `neuranac_tenant_quotas`     | Per-tenant resource limits (sites, nodes, connectors, sessions) |
| CREATE | `neuranac_tenant_node_map`   | Tenant ↔ Node allocation ledger with status tracking            |

### Key Constraints

```sql
-- One node (by k8s identity) → one tenant
CREATE UNIQUE INDEX idx_node_one_tenant
    ON neuranac_node_registry(k8s_pod_name, k8s_namespace)
    WHERE k8s_pod_name IS NOT NULL AND k8s_namespace IS NOT NULL AND tenant_id IS NOT NULL;

-- One active allocation per node
UNIQUE(node_id, status) on neuranac_tenant_node_map
```

### Connector Types (widened CHECK)

```sql
CHECK (connector_type IN ('legacy_nac', 'meraki', 'dnac', 'bridge', 'neuranac_to_neuranac', 'generic_rest'))
```

## API Endpoints

### Tenant Management (`/api/v1/tenants`)

| Method | Path                       | Description                                                |
| ------ | -------------------------- | ---------------------------------------------------------- |
| GET    | `/`                        | List all tenants with usage stats                          |
| GET    | `/{tenant_id}`             | Get tenant detail + quota + usage                          |
| POST   | `/`                        | Provision new tenant (creates quota, config, default site) |
| PUT    | `/{tenant_id}`             | Update tenant properties                                   |
| DELETE | `/{tenant_id}`             | Suspend tenant (soft delete)                               |
| GET    | `/{tenant_id}/quota`       | Get quota limits + current usage                           |
| PUT    | `/{tenant_id}/quota`       | Update quota limits                                        |
| GET    | `/{tenant_id}/nodes`       | List allocated nodes                                       |
| POST   | `/nodes/allocate`          | Allocate node to tenant (enforces 1:1)                     |
| POST   | `/nodes/{node_id}/release` | Release node from tenant                                   |

### Tenant-Scoped Existing APIs

All existing infrastructure APIs now filter by `tenant_id` from the JWT:

- **`/api/v1/sites`** — Only shows sites belonging to the caller's tenant
- **`/api/v1/nodes`** — Only shows nodes belonging to the caller's tenant
- **`/api/v1/connectors`** — Only shows connectors belonging to the caller's tenant
- **`/api/v1/connectors/activation-codes`** — Scoped to tenant
- **`/api/v1/connectors/register`** — Validates site belongs to tenant + quota check
- **`/api/v1/connectors/activate`** — Resolves tenant from activation code's site

## Tenant Provisioning Flow

```
Admin: POST /api/v1/tenants
  {name: "Acme Corp", slug: "acme-corp", tier: "enterprise"}
                │
                ▼
        ┌───────────────┐
        │ 1. Create      │
        │    tenant row  │
        ├───────────────┤
        │ 2. Create      │
        │    quota (tier)│
        ├───────────────┤
        │ 3. Create      │
        │    deploy cfg  │
        ├───────────────┤
        │ 4. Create      │
        │    default site│
        └───────────────┘
                │
                ▼
  Response: {id, slug, tier, status: "provisioned"}
```

## Node Allocation

### Auto-Allocation (via TenantNodeMapper)

```python
mapper = TenantNodeMapper(db)
# Allocate 3 least-loaded nodes to tenant
node_ids = await mapper.auto_allocate("tenant-uuid", count=3, site_id="site-uuid")
```

### Capacity Rebalancing

```python
suggestions = await mapper.get_rebalance_suggestions()
# Returns: [{tenant_id, suggestion: "scale_up"|"scale_down", reason: "High CPU..."}]
```

### Quota Tiers

| Tier       | Sites | Nodes | Connectors | Sessions |
| ---------- | ----- | ----- | ---------- | -------- |
| free       | 1     | 2     | 1          | 100      |
| standard   | 5     | 20    | 10         | 10,000   |
| enterprise | 20    | 100   | 50         | 100,000  |
| unlimited  | 999   | 999   | 999        | 999,999  |

## Zero-Trust Security

### Certificate Hierarchy

```
NeuraNAC Root CA (ECDSA P-256, 5-year validity)
  └── Per-Connector Client Cert (ECDSA P-256, 30-day default)
       - Subject: O=NeuraNAC, OU=tenant-{id}, CN=connector-{id}-{name}
       - SAN: spiffe://neuranac.local/tenant/{tid}/connector/{cid}
       - Extended Key Usage: clientAuth
```

### Activation + mTLS Flow

```
1. Admin generates activation code
   POST /api/v1/connectors/activation-codes → NeuraNAC-XXXX-YYYY

2. On-prem bridge activates
   POST /api/v1/connectors/activate {code: "NeuraNAC-XXXX-YYYY"}
   ← {connector_id, site_id, federation_secret, mtls: {
        client_cert_pem, client_key_pem, ca_cert_pem, fingerprint
      }}

3. Bridge uses mTLS cert for all subsequent calls
   Header: X-Client-Cert-Fingerprint: <sha256>

4. BridgeTrustMiddleware verifies fingerprint against neuranac_connector_trust
   Sets: request.state.bridge_tenant_id, bridge_connector_id
```

### Bridge Trust Middleware

- Validates `X-Client-Cert-Fingerprint` header on bridge endpoints
- Looks up cert in `neuranac_connector_trust` table
- Checks: trust_status == 'trusted', not expired, not revoked
- Sets tenant context from cert for downstream scoping
- Fail-open in dev (when `NEURANAC_BRIDGE_TRUST_ENFORCE != true`)
- Fail-closed in production

## Namespace Isolation (Kubernetes)

### Naming Convention

```
neuranac-{tenant-slug}           — primary namespace
neuranac-{tenant-slug}-data      — data plane
neuranac-{tenant-slug}-bridge    — bridge adapters
```

### Labels

```yaml
neuranac.cisco.com/tenant-id: <uuid>
neuranac.cisco.com/tenant-slug: <slug>
neuranac.cisco.com/isolation-mode: row|schema|namespace
neuranac.cisco.com/managed-by: neuranac-control-plane
```

### Per-Tenant NetworkPolicy

Each tenant namespace gets an auto-generated NetworkPolicy that:
- Allows ingress only from same-tenant pods + neuranac-system namespace
- Allows egress only to same-tenant pods + DNS + NATS

### Per-Tenant ResourceQuota

Mapped from quota tier (free/standard/enterprise/unlimited) to K8s CPU/memory/pod limits.

## Environment Variables

| Variable                   | Default | Description                                        |
| -------------------------- | ------- | -------------------------------------------------- |
| `NEURANAC_BRIDGE_TRUST_ENFORCE` | `false` | Enforce mTLS cert verification on bridge endpoints |
| `NEURANAC_CA_KEY_PATH`          | (none)  | Path to CA private key PEM (for production)        |
| `NEURANAC_CA_CERT_PATH`         | (none)  | Path to CA certificate PEM (for production)        |

## File Inventory

### New Files (Phase 2–5)

| File                                                       | Description                                           |
| ---------------------------------------------------------- | ----------------------------------------------------- |
| `database/migrations/V006_multi_tenant_saas.sql`           | Schema migration: tenant_id columns, quotas, node map |
| `services/api-gateway/app/routers/tenants.py`              | Tenant CRUD, quota management, node allocation API    |
| `services/api-gateway/app/services/namespace_isolation.py` | K8s namespace/label/NetworkPolicy generation          |
| `services/api-gateway/app/services/tenant_node_mapper.py`  | Node allocation, capacity, rebalancing service        |
| `services/api-gateway/app/services/tenant_cert_issuer.py`  | Per-tenant mTLS certificate issuance                  |
| `services/api-gateway/app/middleware/bridge_trust.py`      | mTLS fingerprint verification middleware              |
| `services/api-gateway/tests/test_tenants.py`               | Unit tests for all multi-tenant components            |
| `docs/MULTI_TENANT_ARCHITECTURE.md`                        | This document                                         |

### Modified Files

| File                                             | Change                                               |
| ------------------------------------------------ | ---------------------------------------------------- |
| `services/api-gateway/app/main.py`               | Register tenants router + BridgeTrustMiddleware      |
| `services/api-gateway/app/routers/sites.py`      | Tenant-scoped queries + quota check                  |
| `services/api-gateway/app/routers/nodes.py`      | Tenant-scoped queries + 1-node→1-tenant enforcement  |
| `services/api-gateway/app/routers/connectors.py` | Tenant-scoped queries + quota check                  |
| `services/api-gateway/app/routers/activation.py` | Tenant-scoped codes + mTLS cert issuance on activate |
