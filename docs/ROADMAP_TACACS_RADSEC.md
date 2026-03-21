# TACACS+ and RadSec Roadmap (G29)

This document outlines the planned support for **TACACS+** (device administration) and **RadSec** (RADIUS over TLS) in the NeuraNAC platform.

---

## 1. TACACS+ Device Administration

### Overview
TACACS+ provides centralized authentication, authorization, and accounting for network device CLI access. Unlike RADIUS (which focuses on network access control), TACACS+ controls **who can configure switches, routers, and firewalls** and **what commands they may execute**.

### Current State
- The RADIUS server already listens on TCP port 49 (placeholder).
- No TACACS+ protocol parsing or command authorization logic exists yet.

### Planned Implementation

| Phase | Deliverable                                                  | Priority |
| ----- | ------------------------------------------------------------ | -------- |
| T1    | TACACS+ packet codec (header, authen, author, acct)          | High     |
| T2    | Authentication: PAP/CHAP against identity sources            | High     |
| T3    | Command authorization engine (permit/deny per command set)   | High     |
| T4    | Accounting: log all device admin sessions and commands       | Medium   |
| T5    | Command sets CRUD in API Gateway + UI                        | Medium   |
| T6    | Integration with AI anomaly detection (unusual CLI commands) | Low      |

### Key Design Decisions
- **Shared identity sources** — TACACS+ will reuse the same LDAP/AD/local identity backends as RADIUS.
- **Separate policy sets** — Device-admin policies are distinct from network-access policies.
- **Encryption** — TACACS+ encrypts the entire packet body (not just passwords like RADIUS), using a shared secret per device.
- **Go implementation** — Lives in `services/radius-server/internal/tacacs/` alongside the RADIUS handler.

### Data Model Additions
```sql
-- Command sets for TACACS+ authorization
CREATE TABLE tacacs_command_sets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    commands JSONB NOT NULL DEFAULT '[]',  -- [{pattern, action: permit|deny}]
    tenant_id UUID REFERENCES tenants(id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Device admin profiles (maps user/group → privilege level + command set)
CREATE TABLE tacacs_device_admin_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    privilege_level INT DEFAULT 15,
    command_set_id UUID REFERENCES tacacs_command_sets(id),
    shell_profile JSONB DEFAULT '{}',
    tenant_id UUID REFERENCES tenants(id)
);
```

---

## 2. RadSec (RADIUS over TLS)

### Overview
RadSec (RFC 6614) wraps RADIUS packets in TLS, replacing the hop-by-hop MD5 shared-secret model with end-to-end certificate-based encryption. This is critical for:
- **RADIUS over the internet** — Without VPN tunnels.
- **Zero-trust device onboarding** — Mutual certificate validation for NADs.

### Current State
- The RADIUS server listens on TCP port 2083 (RadSec standard port).
- TLS termination is configured but no RADIUS-over-TLS framing exists.
- mTLS infrastructure (`internal/tlsutil/`) is already in place for gRPC and can be reused.

### Planned Implementation

| Phase | Deliverable                                                | Priority |
| ----- | ---------------------------------------------------------- | -------- |
| R1    | TCP listener with TLS 1.3 (reuse `tlsutil.LoadServerMTLS`) | High     |
| R2    | RADIUS packet framing over TLS stream (length-prefix)      | High     |
| R3    | Client certificate → NAD identity mapping                  | High     |
| R4    | Certificate provisioning API for NADs (EST/SCEP)           | Medium   |
| R5    | RadSec proxy mode (forward to on-prem RADIUS via RadSec)   | Medium   |
| R6    | Status-Server keepalive on RadSec connections              | Low      |

### Key Design Decisions
- **Certificate-based NAD auth** — Each NAD presents a client cert; the CN/SAN maps to the network device entry in the DB, replacing shared secrets.
- **Connection persistence** — RadSec uses persistent TCP connections. The server must track per-connection state and handle reconnections gracefully.
- **Dual-stack** — The RADIUS server will accept both traditional UDP (1812/1813) and RadSec (2083) simultaneously.
- **Cloud-first** — RadSec is the recommended transport for cloud-managed NADs.

### Architecture
```
NAD (switch/AP)
   │
   ├── UDP 1812 ── Traditional RADIUS ──┐
   │                                     ├── RADIUS Handler
   └── TCP 2083 ── RadSec (TLS 1.3) ───┘
                        │
                        ├── Client cert → NAD lookup
                        └── Same policy evaluation pipeline
```

---

## 3. Dependencies & Prerequisites

| Dependency               | Status  | Notes                                      |
| ------------------------ | ------- | ------------------------------------------ |
| mTLS infrastructure      | ✅ Done | `internal/tlsutil/mtls.go`                 |
| X.509 cert validation    | ✅ Done | `handler.go` — `validateClientCertificate` |
| Identity source backends | ✅ Done | LDAP/AD/local via API Gateway              |
| Policy engine gRPC       | ✅ Done | Shared evaluation for RADIUS/TACACS+       |
| Network device model     | ✅ Done | `network_devices` table                    |
| Audit logging            | ✅ Done | `audit_logs` table                         |

## 4. Timeline Estimate

- **TACACS+ T1–T3**: ~3 sprints (device admin MVP)
- **RadSec R1–R3**: ~2 sprints (RadSec MVP)
- **Full feature parity**: ~2 additional sprints

## 5. References

- [RFC 8907 — TACACS+ Protocol](https://www.rfc-editor.org/rfc/rfc8907)
- [RFC 6614 — RadSec](https://www.rfc-editor.org/rfc/rfc6614)
- [RFC 7585 — Dynamic RadSec Discovery](https://www.rfc-editor.org/rfc/rfc7585)
