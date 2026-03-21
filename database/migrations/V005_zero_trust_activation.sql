-- V005: Zero-Trust Activation Code System
-- Enables secure on-prem → cloud connector bootstrap without manual configuration.
--
-- Flow:
--   1. Cloud admin generates activation code via POST /api/v1/connectors/activation-codes
--   2. On-prem installer runs: NeuraNAC_CONNECTOR_ACTIVATION_CODE=NeuraNAC-XXXX-YYYY docker run ...
--   3. Connector calls POST /api/v1/connectors/activate {code: "NeuraNAC-XXXX-YYYY"}
--   4. Cloud returns site_id, api_url, ws_url, shared_secret
--   5. Connector auto-configures and registers with mTLS bootstrap
--   6. Activation code is consumed (single-use)

-- ─── Activation Codes ─────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS neuranac_activation_codes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code            VARCHAR(20)  NOT NULL UNIQUE,
    site_id         UUID         NOT NULL REFERENCES neuranac_sites(id) ON DELETE CASCADE,
    connector_type  VARCHAR(30)  NOT NULL DEFAULT 'bridge' CHECK (connector_type IN ('bridge', 'meraki', 'dnac')),
    created_by      UUID         REFERENCES admin_users(id),
    status          VARCHAR(20)  NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'consumed', 'expired', 'revoked')),
    consumed_by     UUID         REFERENCES neuranac_connectors(id),
    consumed_at     TIMESTAMPTZ,
    expires_at      TIMESTAMPTZ  NOT NULL DEFAULT (now() + interval '24 hours'),
    metadata        JSONB        DEFAULT '{}',
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_activation_codes_code ON neuranac_activation_codes(code);
CREATE INDEX IF NOT EXISTS idx_activation_codes_status ON neuranac_activation_codes(status);
CREATE INDEX IF NOT EXISTS idx_activation_codes_site_id ON neuranac_activation_codes(site_id);

-- ─── Connector Trust Certificates ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS neuranac_connector_trust (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    connector_id    UUID         NOT NULL REFERENCES neuranac_connectors(id) ON DELETE CASCADE,
    client_cert_pem TEXT,
    client_key_hash VARCHAR(64),
    ca_cert_pem     TEXT,
    trust_status    VARCHAR(20)  NOT NULL DEFAULT 'pending' CHECK (trust_status IN ('pending', 'trusted', 'revoked')),
    fingerprint     VARCHAR(64),
    issued_at       TIMESTAMPTZ  NOT NULL DEFAULT now(),
    expires_at      TIMESTAMPTZ,
    revoked_at      TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_connector_trust_connector ON neuranac_connector_trust(connector_id);
CREATE INDEX IF NOT EXISTS idx_connector_trust_status ON neuranac_connector_trust(trust_status);
