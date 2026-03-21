-- V006: Multi-Tenant SaaS Architecture
-- Adds tenant_id to all hybrid infrastructure tables to enforce per-tenant isolation.
-- Key invariant: one tenant → many nodes, one node → exactly one tenant.
--
-- Tables modified:
--   neuranac_sites              — add tenant_id FK
--   neuranac_connectors         — add tenant_id FK, widen connector_type CHECK
--   neuranac_node_registry      — add tenant_id FK + UNIQUE constraint (1 node → 1 tenant)
--   neuranac_activation_codes   — add tenant_id FK, widen connector_type CHECK
--   neuranac_connector_trust    — add tenant_id FK
--   neuranac_deployment_config  — add tenant_id FK (per-tenant deployment config)
--
-- New tables:
--   neuranac_tenant_quotas      — per-tenant resource limits
--   neuranac_tenant_node_map    — explicit tenant↔node allocation ledger

-- ═══════════════════════════════════════════════════════════════════
-- 1. Add tenant_id to existing hybrid tables
-- ═══════════════════════════════════════════════════════════════════

-- neuranac_sites
ALTER TABLE neuranac_sites
    ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS idx_sites_tenant_id ON neuranac_sites(tenant_id);

-- neuranac_connectors: add tenant_id + widen connector_type
ALTER TABLE neuranac_connectors
    ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS idx_connectors_tenant_id ON neuranac_connectors(tenant_id);

-- Widen connector_type CHECK to include bridge adapter types
ALTER TABLE neuranac_connectors DROP CONSTRAINT IF EXISTS neuranac_connectors_connector_type_check;
ALTER TABLE neuranac_connectors ADD CONSTRAINT neuranac_connectors_connector_type_check
    CHECK (connector_type IN ('legacy_nac', 'meraki', 'dnac', 'bridge', 'neuranac_to_neuranac', 'generic_rest'));

-- neuranac_node_registry: add tenant_id + enforce 1 node → 1 tenant
ALTER TABLE neuranac_node_registry
    ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS idx_node_registry_tenant_id ON neuranac_node_registry(tenant_id);

-- A node (identified by k8s_pod_name + k8s_namespace) can only belong to one tenant
CREATE UNIQUE INDEX IF NOT EXISTS idx_node_one_tenant
    ON neuranac_node_registry(k8s_pod_name, k8s_namespace)
    WHERE k8s_pod_name IS NOT NULL AND k8s_namespace IS NOT NULL AND tenant_id IS NOT NULL;

-- neuranac_activation_codes: add tenant_id + widen connector_type
ALTER TABLE neuranac_activation_codes
    ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS idx_activation_codes_tenant_id ON neuranac_activation_codes(tenant_id);

ALTER TABLE neuranac_activation_codes DROP CONSTRAINT IF EXISTS neuranac_activation_codes_connector_type_check;
ALTER TABLE neuranac_activation_codes ADD CONSTRAINT neuranac_activation_codes_connector_type_check
    CHECK (connector_type IN ('legacy_nac', 'meraki', 'dnac', 'bridge', 'neuranac_to_neuranac', 'generic_rest'));

-- neuranac_connector_trust: add tenant_id
ALTER TABLE neuranac_connector_trust
    ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS idx_connector_trust_tenant_id ON neuranac_connector_trust(tenant_id);

-- neuranac_deployment_config: add tenant_id (per-tenant deployment settings)
ALTER TABLE neuranac_deployment_config
    ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE;

-- Drop the singleton index so we can have per-tenant config rows
DROP INDEX IF EXISTS idx_deployment_config_singleton;
-- New unique: one config per tenant (NULL tenant_id = system default)
CREATE UNIQUE INDEX IF NOT EXISTS idx_deployment_config_tenant
    ON neuranac_deployment_config(COALESCE(tenant_id, '00000000-0000-0000-0000-000000000000'::uuid));

-- ═══════════════════════════════════════════════════════════════════
-- 2. Tenant Quotas — per-tenant resource limits
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS neuranac_tenant_quotas (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID         NOT NULL UNIQUE REFERENCES tenants(id) ON DELETE CASCADE,
    max_sites       INTEGER      NOT NULL DEFAULT 5,
    max_nodes       INTEGER      NOT NULL DEFAULT 20,
    max_connectors  INTEGER      NOT NULL DEFAULT 10,
    max_sessions    INTEGER      NOT NULL DEFAULT 10000,
    max_policies    INTEGER      NOT NULL DEFAULT 500,
    max_endpoints   INTEGER      NOT NULL DEFAULT 50000,
    max_admins      INTEGER      NOT NULL DEFAULT 50,
    storage_gb      INTEGER      NOT NULL DEFAULT 100,
    tier            VARCHAR(30)  NOT NULL DEFAULT 'standard' CHECK (tier IN ('free', 'standard', 'enterprise', 'unlimited')),
    custom_limits   JSONB        DEFAULT '{}',
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- ═══════════════════════════════════════════════════════════════════
-- 3. Tenant ↔ Node Allocation Ledger
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS neuranac_tenant_node_map (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID         NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    node_id         UUID         NOT NULL REFERENCES neuranac_node_registry(id) ON DELETE CASCADE,
    allocated_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    released_at     TIMESTAMPTZ,
    status          VARCHAR(20)  NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'releasing', 'released')),
    UNIQUE(node_id, status)  -- one active allocation per node
);

CREATE INDEX IF NOT EXISTS idx_tenant_node_map_tenant ON neuranac_tenant_node_map(tenant_id);
CREATE INDEX IF NOT EXISTS idx_tenant_node_map_node ON neuranac_tenant_node_map(node_id);
CREATE INDEX IF NOT EXISTS idx_tenant_node_map_active ON neuranac_tenant_node_map(status) WHERE status = 'active';

-- ═══════════════════════════════════════════════════════════════════
-- 4. Backfill existing rows with default tenant
-- ═══════════════════════════════════════════════════════════════════

UPDATE neuranac_sites SET tenant_id = '00000000-0000-0000-0000-000000000000'::uuid
    WHERE tenant_id IS NULL;
UPDATE neuranac_connectors SET tenant_id = '00000000-0000-0000-0000-000000000000'::uuid
    WHERE tenant_id IS NULL;
UPDATE neuranac_node_registry SET tenant_id = '00000000-0000-0000-0000-000000000000'::uuid
    WHERE tenant_id IS NULL;
UPDATE neuranac_activation_codes SET tenant_id = '00000000-0000-0000-0000-000000000000'::uuid
    WHERE tenant_id IS NULL;
UPDATE neuranac_deployment_config SET tenant_id = '00000000-0000-0000-0000-000000000000'::uuid
    WHERE tenant_id IS NULL;

-- ═══════════════════════════════════════════════════════════════════
-- 5. Default tenant quota for system tenant
-- ═══════════════════════════════════════════════════════════════════

INSERT INTO neuranac_tenant_quotas (tenant_id, tier, max_sites, max_nodes, max_connectors, max_sessions)
VALUES ('00000000-0000-0000-0000-000000000000'::uuid, 'unlimited', 999, 999, 999, 999999)
ON CONFLICT (tenant_id) DO NOTHING;
