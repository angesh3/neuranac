-- NeuraNAC V003: SIEM & Operational Tables
-- Fills the V003 gap in the migration sequence.
-- Adds persistent storage for SIEM destinations, SOAR playbooks,
-- schema version tracking, and WebSocket session metadata.

-- ═══════════════════════════════════════════════════════════════════
-- SCHEMA VERSION TRACKING (for upgrade/rollback)
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS neuranac_schema_versions (
    version VARCHAR(20) PRIMARY KEY,
    description TEXT,
    applied_at TIMESTAMPTZ DEFAULT NOW(),
    applied_by VARCHAR(255) DEFAULT CURRENT_USER,
    checksum VARCHAR(64)
);

INSERT INTO neuranac_schema_versions (version, description)
VALUES ('V003', 'SIEM & Operational Tables')
ON CONFLICT (version) DO NOTHING;

-- ═══════════════════════════════════════════════════════════════════
-- SIEM DESTINATIONS (persistent, survives restarts)
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS neuranac_siem_destinations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    dest_type VARCHAR(50) NOT NULL,
    host VARCHAR(255) NOT NULL,
    port INT DEFAULT 514,
    protocol VARCHAR(10) DEFAULT 'udp',
    format VARCHAR(20) DEFAULT 'cef',
    webhook_url TEXT,
    webhook_headers JSONB DEFAULT '{}',
    filters JSONB DEFAULT '{}',
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_siem_dest_enabled ON neuranac_siem_destinations(enabled);

-- ═══════════════════════════════════════════════════════════════════
-- SOAR PLAYBOOKS (persistent)
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS neuranac_soar_playbooks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    trigger_event VARCHAR(100) NOT NULL,
    webhook_url TEXT NOT NULL,
    webhook_headers JSONB DEFAULT '{}',
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_soar_pb_trigger ON neuranac_soar_playbooks(trigger_event);
