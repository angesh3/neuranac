-- NeuraNAC V002: Legacy Integration Enhancements
-- Background sync scheduler, Event Stream events, sync conflicts, policy translation,
-- RADIUS traffic analysis, migration wizard state

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ═══════════════════════════════════════════════════════════════════
-- SYNC SCHEDULES (Background cron-based sync)
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE legacy_nac_sync_schedules (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    connection_id UUID NOT NULL REFERENCES legacy_nac_connections(id) ON DELETE CASCADE,
    entity_type VARCHAR(100) NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    interval_minutes INT NOT NULL DEFAULT 60,
    sync_type VARCHAR(50) DEFAULT 'incremental',  -- 'full', 'incremental'
    direction VARCHAR(20) DEFAULT 'legacy_to_neuranac',
    last_run_at TIMESTAMPTZ,
    next_run_at TIMESTAMPTZ,
    run_count INT DEFAULT 0,
    last_run_status VARCHAR(50),
    last_run_duration_ms INT,
    cron_expression VARCHAR(100),  -- optional cron override e.g. '0 */2 * * *'
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(connection_id, entity_type)
);

-- ═══════════════════════════════════════════════════════════════════
-- SYNC CONFLICTS (Entity-level conflict tracking)
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE legacy_nac_sync_conflicts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    connection_id UUID NOT NULL REFERENCES legacy_nac_connections(id) ON DELETE CASCADE,
    entity_type VARCHAR(100) NOT NULL,
    legacy_nac_id VARCHAR(255) NOT NULL,
    legacy_nac_name VARCHAR(255),
    neuranac_id UUID,
    conflict_type VARCHAR(50) NOT NULL,  -- 'field_mismatch', 'missing_in_legacy_nac', 'missing_in_neuranac', 'schema_diff'
    conflicting_fields JSONB DEFAULT '[]',  -- [{"field":"name","legacy_nac_value":"x","neuranac_value":"y"}]
    legacy_nac_data JSONB DEFAULT '{}',
    neuranac_data JSONB DEFAULT '{}',
    status VARCHAR(50) DEFAULT 'unresolved',  -- 'unresolved', 'resolved_legacy_nac', 'resolved_neuranac', 'resolved_manual', 'ignored'
    resolved_by VARCHAR(255),
    resolved_at TIMESTAMPTZ,
    resolution_note TEXT,
    detected_at TIMESTAMPTZ DEFAULT NOW(),
    sync_log_id UUID REFERENCES legacy_nac_sync_log(id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_legacy_nac_conflicts_conn ON legacy_nac_sync_conflicts(connection_id, status);
CREATE INDEX idx_legacy_nac_conflicts_entity ON legacy_nac_sync_conflicts(entity_type, status);

-- ═══════════════════════════════════════════════════════════════════
-- EVENT STREAM EVENTS (Real-time event log from Legacy NAC Event Stream)
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE legacy_nac_event_stream_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    connection_id UUID NOT NULL REFERENCES legacy_nac_connections(id) ON DELETE CASCADE,
    event_type VARCHAR(100) NOT NULL,  -- 'session_created', 'session_deleted', 'profiler_update', 'trustsec_update', 'radius_failure'
    topic VARCHAR(255) NOT NULL,       -- STOMP topic e.g. '/topic/com.legacy.session'
    payload JSONB NOT NULL DEFAULT '{}',
    source_ip VARCHAR(45),
    mac_address VARCHAR(17),
    username VARCHAR(255),
    processed BOOLEAN DEFAULT FALSE,
    processed_at TIMESTAMPTZ,
    action_taken VARCHAR(255),  -- what NeuraNAC did in response
    received_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_event_stream_events_conn ON legacy_nac_event_stream_events(connection_id, received_at DESC);
CREATE INDEX idx_event_stream_events_type ON legacy_nac_event_stream_events(event_type, received_at DESC);
CREATE INDEX idx_event_stream_events_unprocessed ON legacy_nac_event_stream_events(connection_id) WHERE NOT processed;

-- ═══════════════════════════════════════════════════════════════════
-- POLICY TRANSLATIONS (NeuraNAC XML → NeuraNAC JSON policy mapping)
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE legacy_nac_policy_translations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    connection_id UUID NOT NULL REFERENCES legacy_nac_connections(id) ON DELETE CASCADE,
    legacy_nac_policy_id VARCHAR(255),
    legacy_nac_policy_name VARCHAR(255) NOT NULL,
    legacy_nac_policy_type VARCHAR(100),  -- 'authorization', 'authentication', 'profiling', 'posture'
    legacy_nac_policy_xml TEXT,    -- raw Legacy NAC XML policy definition
    legacy_nac_conditions JSONB,   -- parsed Legacy NAC conditions
    neuranac_policy_id UUID,            -- linked NeuraNAC policy if created
    neuranac_policy_json JSONB,         -- translated NeuraNAC policy definition
    translation_method VARCHAR(50) DEFAULT 'ai',  -- 'ai', 'rule_based', 'manual'
    confidence_score FLOAT,        -- AI translation confidence (0.0-1.0)
    ai_explanation TEXT,           -- AI reasoning for translation choices
    status VARCHAR(50) DEFAULT 'draft',  -- 'draft', 'reviewed', 'applied', 'rejected'
    review_notes TEXT,
    reviewed_by VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ═══════════════════════════════════════════════════════════════════
-- RADIUS TRAFFIC ANALYSIS (Migration verification)
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE legacy_nac_radius_traffic_snapshots (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    connection_id UUID REFERENCES legacy_nac_connections(id) ON DELETE SET NULL,
    snapshot_name VARCHAR(255) NOT NULL,
    snapshot_type VARCHAR(50) NOT NULL,  -- 'baseline_legacy', 'during_migration', 'post_migration', 'comparison'
    capture_period_start TIMESTAMPTZ NOT NULL,
    capture_period_end TIMESTAMPTZ NOT NULL,
    total_requests INT DEFAULT 0,
    total_accepts INT DEFAULT 0,
    total_rejects INT DEFAULT 0,
    total_timeouts INT DEFAULT 0,
    unique_users INT DEFAULT 0,
    unique_endpoints INT DEFAULT 0,
    unique_nads INT DEFAULT 0,
    auth_methods JSONB DEFAULT '{}',   -- {"PAP": 120, "EAP-TLS": 450, "MAB": 80}
    reject_reasons JSONB DEFAULT '{}', -- {"invalid_password": 5, "unknown_nad": 2}
    response_time_p50_ms FLOAT,
    response_time_p95_ms FLOAT,
    response_time_p99_ms FLOAT,
    per_nad_stats JSONB DEFAULT '[]',  -- [{nad_ip, requests, accepts, rejects}]
    comparison_result JSONB,           -- diff against baseline if snapshot_type='comparison'
    status VARCHAR(50) DEFAULT 'capturing',  -- 'capturing', 'complete', 'analyzing', 'compared'
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ═══════════════════════════════════════════════════════════════════
-- MIGRATION WIZARD STATE (Step-by-step migration tracking)
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE legacy_nac_migration_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    connection_id UUID NOT NULL REFERENCES legacy_nac_connections(id) ON DELETE CASCADE,
    run_name VARCHAR(255) NOT NULL,
    current_step INT DEFAULT 1,
    total_steps INT DEFAULT 8,
    status VARCHAR(50) DEFAULT 'in_progress',  -- 'in_progress', 'paused', 'completed', 'rolled_back', 'failed'
    steps JSONB NOT NULL DEFAULT '[]',  -- [{step, name, status, started_at, completed_at, result}]
    pilot_nad_ids JSONB DEFAULT '[]',
    rollback_available BOOLEAN DEFAULT TRUE,
    rollback_data JSONB DEFAULT '{}',   -- snapshot for rollback
    started_by VARCHAR(255),
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    notes TEXT
);

-- Add new columns to legacy_nac_connections for enhanced features
ALTER TABLE legacy_nac_connections ADD COLUMN IF NOT EXISTS detected_version VARCHAR(50);
ALTER TABLE legacy_nac_connections ADD COLUMN IF NOT EXISTS version_features JSONB DEFAULT '{}';
ALTER TABLE legacy_nac_connections ADD COLUMN IF NOT EXISTS event_stream_status VARCHAR(50) DEFAULT 'disconnected';
ALTER TABLE legacy_nac_connections ADD COLUMN IF NOT EXISTS event_stream_node_name VARCHAR(255);
ALTER TABLE legacy_nac_connections ADD COLUMN IF NOT EXISTS bidirectional_sync BOOLEAN DEFAULT FALSE;
ALTER TABLE legacy_nac_connections ADD COLUMN IF NOT EXISTS sync_scheduler_enabled BOOLEAN DEFAULT FALSE;
