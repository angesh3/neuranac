-- V007: Network Ingestion & Telemetry Tables
-- Supports: SNMP traps, Syslog, NetFlow/IPFIX, DHCP fingerprinting, CDP/LLDP neighbor topology

BEGIN;

-- ─── Telemetry Events (SNMP traps, syslog, generic) ────────────────────────
CREATE TABLE IF NOT EXISTS neuranac_telemetry_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type      VARCHAR(32)  NOT NULL,  -- snmp, syslog, dhcp, neighbor
    source_ip       INET         NOT NULL,
    site_id         UUID         REFERENCES neuranac_sites(id),
    node_id         VARCHAR(64),
    severity        VARCHAR(16)  DEFAULT 'informational',
    facility        VARCHAR(32),
    trap_oid        VARCHAR(128),
    message         TEXT,
    raw_data        JSONB,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_telemetry_events_type      ON neuranac_telemetry_events (event_type);
CREATE INDEX IF NOT EXISTS idx_telemetry_events_source    ON neuranac_telemetry_events (source_ip);
CREATE INDEX IF NOT EXISTS idx_telemetry_events_site      ON neuranac_telemetry_events (site_id);
CREATE INDEX IF NOT EXISTS idx_telemetry_events_created   ON neuranac_telemetry_events (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_telemetry_events_severity  ON neuranac_telemetry_events (severity);

-- ─── NetFlow / IPFIX Flow Records ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS neuranac_telemetry_flows (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    exporter_ip     INET         NOT NULL,
    site_id         UUID         REFERENCES neuranac_sites(id),
    node_id         VARCHAR(64),
    version         SMALLINT     NOT NULL,  -- 5, 9, or 10 (IPFIX)
    src_ip          INET,
    dst_ip          INET,
    src_port        INTEGER,
    dst_port        INTEGER,
    protocol        SMALLINT,
    packets         BIGINT       DEFAULT 0,
    bytes           BIGINT       DEFAULT 0,
    tos             SMALLINT     DEFAULT 0,
    next_hop        INET,
    flow_start      TIMESTAMPTZ,
    flow_end        TIMESTAMPTZ,
    raw_data        JSONB,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_telemetry_flows_exporter   ON neuranac_telemetry_flows (exporter_ip);
CREATE INDEX IF NOT EXISTS idx_telemetry_flows_src        ON neuranac_telemetry_flows (src_ip);
CREATE INDEX IF NOT EXISTS idx_telemetry_flows_dst        ON neuranac_telemetry_flows (dst_ip);
CREATE INDEX IF NOT EXISTS idx_telemetry_flows_site       ON neuranac_telemetry_flows (site_id);
CREATE INDEX IF NOT EXISTS idx_telemetry_flows_created    ON neuranac_telemetry_flows (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_telemetry_flows_proto_port ON neuranac_telemetry_flows (protocol, dst_port);

-- ─── DHCP Fingerprints ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS neuranac_dhcp_fingerprints (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mac_address     MACADDR      NOT NULL,
    client_ip       INET,
    hostname        VARCHAR(255),
    vendor_class    VARCHAR(255),
    fingerprint     VARCHAR(512),  -- hex-encoded option 55 parameter list
    os_guess        VARCHAR(128),
    msg_type        VARCHAR(16),   -- DISCOVER, REQUEST, ACK, etc.
    source_ip       INET         NOT NULL,
    site_id         UUID         REFERENCES neuranac_sites(id),
    node_id         VARCHAR(64),
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_dhcp_fp_mac        ON neuranac_dhcp_fingerprints (mac_address);
CREATE INDEX IF NOT EXISTS idx_dhcp_fp_hostname   ON neuranac_dhcp_fingerprints (hostname);
CREATE INDEX IF NOT EXISTS idx_dhcp_fp_os         ON neuranac_dhcp_fingerprints (os_guess);
CREATE INDEX IF NOT EXISTS idx_dhcp_fp_site       ON neuranac_dhcp_fingerprints (site_id);
CREATE INDEX IF NOT EXISTS idx_dhcp_fp_created    ON neuranac_dhcp_fingerprints (created_at DESC);

-- Unique constraint: latest fingerprint per MAC (upsert pattern)
CREATE UNIQUE INDEX IF NOT EXISTS idx_dhcp_fp_mac_unique ON neuranac_dhcp_fingerprints (mac_address, site_id)
    WHERE msg_type IN ('DISCOVER', 'REQUEST');

-- ─── CDP/LLDP Neighbor Topology ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS neuranac_neighbor_topology (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    local_device_ip INET         NOT NULL,
    local_port      VARCHAR(128),
    remote_device   VARCHAR(255),
    remote_port     VARCHAR(128),
    remote_ip       INET,
    platform        VARCHAR(255),
    protocol        VARCHAR(8)   NOT NULL DEFAULT 'cdp',  -- cdp or lldp
    site_id         UUID         REFERENCES neuranac_sites(id),
    node_id         VARCHAR(64),
    last_seen       TIMESTAMPTZ  NOT NULL DEFAULT now(),
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_neighbor_local     ON neuranac_neighbor_topology (local_device_ip);
CREATE INDEX IF NOT EXISTS idx_neighbor_remote    ON neuranac_neighbor_topology (remote_device);
CREATE INDEX IF NOT EXISTS idx_neighbor_site      ON neuranac_neighbor_topology (site_id);
CREATE INDEX IF NOT EXISTS idx_neighbor_protocol  ON neuranac_neighbor_topology (protocol);

-- Unique constraint: one entry per local+remote pair
CREATE UNIQUE INDEX IF NOT EXISTS idx_neighbor_unique
    ON neuranac_neighbor_topology (local_device_ip, local_port, remote_device, remote_port, site_id);

-- ─── Ingestion Collector Status ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS neuranac_ingestion_collectors (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    node_id         VARCHAR(64)  NOT NULL,
    site_id         UUID         REFERENCES neuranac_sites(id),
    status          VARCHAR(16)  NOT NULL DEFAULT 'active',  -- active, draining, stopped
    channels        JSONB        NOT NULL DEFAULT '{}',      -- {snmp: true, syslog: true, ...}
    stats           JSONB        NOT NULL DEFAULT '{}',      -- latest stats snapshot
    last_heartbeat  TIMESTAMPTZ  NOT NULL DEFAULT now(),
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_collector_node_site
    ON neuranac_ingestion_collectors (node_id, site_id);

-- ─── Retention policy for telemetry (auto-purge old data) ──────────────────
INSERT INTO neuranac_retention_policies (table_name, retention_days, enabled)
VALUES
    ('neuranac_telemetry_events', 30, true),
    ('neuranac_telemetry_flows', 7, true),
    ('neuranac_dhcp_fingerprints', 90, true),
    ('neuranac_neighbor_topology', 90, true)
ON CONFLICT (table_name) DO UPDATE SET retention_days = EXCLUDED.retention_days;

COMMIT;
