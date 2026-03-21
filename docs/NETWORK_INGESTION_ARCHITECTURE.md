# NeuraNAC Network Ingestion Architecture — How NADs Push Data to NeuraNAC

> **Version:** 2.0.0 | **Date:** 2026-03-04 | **Status:** Implemented

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Current Model — AAA-Driven Ingestion](#2-current-model--aaa-driven-ingestion)
3. [The Gap — What's Missing](#3-the-gap--whats-missing)
4. [Proposed Architecture — Network Ingestion Collector](#4-proposed-architecture--network-ingestion-collector)
5. [Ingestion Channel Deep Dive](#5-ingestion-channel-deep-dive)
6. [Scaling Architecture](#6-scaling-architecture)
7. [Deployment Scenario S1 — NeuraNAC + Hybrid](#7-deployment-scenario-s1-lnac-hybrid)
8. [Deployment Scenario S2 — Cloud Standalone](#8-deployment-scenario-s2--cloud-standalone)
9. [Deployment Scenario S3 — On-Prem Standalone](#9-deployment-scenario-s3--on-prem-standalone)
10. [Deployment Scenario S4 — Hybrid No NeuraNAC](#10-deployment-scenario-s4--hybrid-no-lnac)
11. [Scaling Numbers & Capacity Planning](#11-scaling-numbers--capacity-planning)
12. [Implementation Roadmap](#12-implementation-roadmap)

---

## 1. Executive Summary

### The Question

> How do network devices push information from their network to the NeuraNAC platform?
> Don't we need an ingestion service or traffic grabber?

### The Answer

**Today, NeuraNAC uses a protocol-driven ingestion model** — network access devices (NADs) are configured to point to NeuraNAC as their RADIUS/TACACS+ server. When an endpoint connects, the NAD sends an AAA request to NeuraNAC. This is the standard model used by every NAC platform (NeuraNAC, ClearPass, FreeRADIUS).

**However, AAA alone is not sufficient for full network visibility.** For deep endpoint profiling, traffic analysis, and contextual awareness, a NAC platform needs additional ingestion channels:

| Channel                 | Current State  | Purpose                               |
| ----------------------- | -------------- | ------------------------------------- |
| RADIUS/TACACS+ (AAA)    | ✅ Implemented | Auth, authz, accounting — the core    |
| RADIUS Accounting       | ✅ Implemented | Session tracking (start/interim/stop) |
| CoA (reverse — NeuraNAC→NAD) | ✅ Implemented | Dynamic policy enforcement            |
| SNMP Trap Receiver      | ✅ Implemented | Device events, link up/down           |
| NetFlow/IPFIX Collector | ✅ Implemented | Traffic flow telemetry                |
| Syslog Receiver         | ✅ Implemented | Device log ingestion                  |
| DHCP Snooping/Relay     | ✅ Implemented | IP-MAC binding, OS fingerprint        |
| CDP/LLDP Discovery      | ✅ Implemented | Neighbor topology mapping (polling)   |
| SPAN/TAP Analysis       | ❌ Not yet     | Deep packet inspection                |
| SNMP Polling (active)   | ✅ Implemented | Interface stats, ARP tables (stub)    |

This document designs the **Network Ingestion Collector** — a new service that fills these gaps and explains how the full architecture scales across all 4 deployment scenarios.

---

## 2. Current Model — AAA-Driven Ingestion

### How NADs Currently Talk to NeuraNAC

The current architecture uses the **standard NAC AAA model**. The NAD is the initiator — it sends RADIUS/TACACS+ packets to NeuraNAC when network events occur.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         CURRENT INGESTION MODEL                                  │
│                                                                                  │
│   ┌──────────┐                                                                  │
│   │ Endpoint │ Connects to network port                                         │
│   │ (laptop, │ (plugs in cable, joins WiFi, VPN connects)                       │
│   │  phone,  │                                                                  │
│   │  IoT)    │                                                                  │
│   └────┬─────┘                                                                  │
│        │ 802.1X / MAB / Web Auth                                                │
│        ▼                                                                         │
│   ┌──────────┐                                                                  │
│   │   NAD    │  The NAD is configured with:                                     │
│   │ (switch, │    radius-server host <NeuraNAC_IP> key <shared_secret>               │
│   │  WLC,    │    aaa authentication dot1x default group radius                 │
│   │  AP)     │    aaa accounting dot1x default start-stop group radius          │
│   └────┬─────┘                                                                  │
│        │                                                                         │
│        │  NAD sends RADIUS packets TO NeuraNAC                                       │
│        │  (NeuraNAC does NOT pull from NAD — NAD pushes to NeuraNAC)                      │
│        │                                                                         │
│        ├──── Access-Request (UDP 1812) ──────────────────► NeuraNAC RADIUS Server    │
│        │     Contains: username, MAC, NAS-IP, EAP type                          │
│        │                                                                         │
│        ├──── Accounting-Request (UDP 1813) ──────────────► NeuraNAC RADIUS Server    │
│        │     Contains: session start/stop, bytes in/out                          │
│        │                                                                         │
│        ├──── TACACS+ Auth (TCP 49) ──────────────────────► NeuraNAC RADIUS Server    │
│        │     Contains: admin username, command authorization                     │
│        │                                                                         │
│        │◄─── Access-Accept/Reject (UDP 1812) ◄──────────── NeuraNAC RADIUS Server   │
│        │     Contains: VLAN, SGT, session-timeout                               │
│        │                                                                         │
│        │◄─── CoA Disconnect/Reauth (UDP 3799) ◄─────────── NeuraNAC CoA Sender     │
│        │     Triggered by: AI risk score > threshold                             │
│        │                                                                         │
│   ┌────┴───────────────────────────────────────────────────────────────────┐    │
│   │                     NeuraNAC PLATFORM                                       │    │
│   │                                                                        │    │
│   │  RADIUS Server (Go)                                                    │    │
│   │  ├── UDP :1812 listener (Authentication)                               │    │
│   │  ├── UDP :1813 listener (Accounting)                                   │    │
│   │  ├── TCP :2083 listener (RadSec — RADIUS over TLS)                     │    │
│   │  ├── TCP :49   listener (TACACS+)                                      │    │
│   │  └── UDP :3799 sender  (CoA — outbound to NAD)                         │    │
│   │                                                                        │    │
│   │  These listeners ARE the ingestion service for AAA traffic.            │    │
│   │  The Go RADIUS server processes ~10,000 auth/sec per replica.          │    │
│   └────────────────────────────────────────────────────────────────────────┘    │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### What Happens Inside NeuraNAC After Ingestion

```
   RADIUS Access-Request arrives at :1812
              │
              ▼
   ┌─────────────────────┐
   │  1. Parse Packet     │  Extract: User-Name, Calling-Station-Id (MAC),
   │                      │  NAS-IP-Address, NAS-Port, EAP-Message, etc.
   └──────────┬──────────┘
              │
              ▼
   ┌─────────────────────┐
   │  2. NAD Lookup       │  SELECT * FROM network_devices WHERE ip = NAS-IP
   │     (PostgreSQL)     │  Verify shared secret matches
   └──────────┬──────────┘
              │
              ▼
   ┌─────────────────────┐
   │  3. Authentication   │  Route to handler based on EAP type:
   │     Handler          │  ├── PAP:     bcrypt verify password
   │                      │  ├── EAP-TLS: crypto/tls.Server handshake
   │                      │  ├── MAB:     MAC lookup + OUI profiling
   │                      │  └── TACACS+: parse header, decrypt body
   └──────────┬──────────┘
              │
              ▼
   ┌─────────────────────┐
   │  4. Policy Engine    │  gRPC call → evaluate 14-operator conditions
   │     (gRPC :9091)     │  Returns: VLAN, SGT, dACL, CoA action
   └──────────┬──────────┘
              │
              ▼
   ┌─────────────────────┐
   │  5. AI Enrichment    │  HTTP calls to AI Engine:
   │     (HTTP :8081)     │  ├── /profile  → device classification
   │                      │  ├── /risk     → multi-dimensional risk score
   │                      │  ├── /anomaly  → baseline deviation check
   │                      │  └── /drift    → policy drift detection
   └──────────┬──────────┘
              │
              ▼
   ┌─────────────────────┐
   │  6. Build Response   │  Access-Accept with RADIUS attributes
   │     + Persist        │  → PostgreSQL (session record)
   │     + Publish        │  → NATS (event bus for real-time UI)
   │     + Cache          │  → Redis (session state, EAP state)
   └──────────┬──────────┘
              │
              ▼
   ┌─────────────────────┐
   │  7. CoA (if needed)  │  If risk_score > 70:
   │     UDP :3799        │  → Send Disconnect-Request to NAD
   │     (outbound)       │  → Publish coa.triggered event to NATS
   └─────────────────────┘
```

---

## 3. The Gap — What's Missing

### Why AAA Alone Is Not Enough

The AAA model only sees traffic **at the moment of authentication**. It doesn't see:

| Blind Spot                      | Impact                                         | How to Fix              |
| ------------------------------- | ---------------------------------------------- | ----------------------- |
| **Post-auth traffic patterns**  | Can't detect data exfiltration after auth      | NetFlow/IPFIX collector |
| **Device OS fingerprinting**    | Limited profiling (only OUI from MAC)          | DHCP fingerprinting     |
| **Network topology changes**    | No visibility into link up/down, new neighbors | SNMP traps + CDP/LLDP   |
| **Configuration drift on NADs** | NAD config may deviate from policy             | SNMP polling            |
| **Non-802.1X segments**         | Devices on unmanaged ports are invisible       | SPAN/TAP analysis       |
| **IP address binding**          | MAC-to-IP mapping relies on ARP tables         | DHCP snooping/relay     |
| **Device log correlation**      | Can't correlate auth events with device logs   | Syslog receiver         |

### How Legacy NAC Solves This (for comparison)

NeuraNAC uses **Profiling Probes** — each one is essentially an ingestion channel:

```
  NeuraNAC Profiling Probes (10 channels):
  ┌─────────────────────────────────────────────────────────────┐
  │  1. RADIUS Probe        ← From RADIUS auth attributes     │
  │  2. DHCP Probe          ← From DHCP helper-address relay   │
  │  3. DHCP SPAN Probe     ← From SPAN port mirroring         │
  │  4. HTTP Probe           ← From HTTP User-Agent headers     │
  │  5. DNS Probe            ← From DNS reverse lookups         │
  │  6. NetFlow Probe       ← From NetFlow/IPFIX exports       │
  │  7. SNMP Query Probe    ← Active polling of NADs            │
  │  8. SNMP Trap Probe     ← Passive trap receiver             │
  │  9. NMAP Scan Probe     ← Active network scanning           │
  │ 10. Event Stream Probe        ← From Event Stream context sharing   │
  └─────────────────────────────────────────────────────────────┘
```

**NeuraNAC today implements probes 1 and 10 (via Bridge Connector).** The remaining probes represent the ingestion gap.

---

## 4. Proposed Architecture — Network Ingestion Collector

### New Service: `ingestion-collector`

A new Go microservice that acts as a **multi-protocol network telemetry receiver**. It collects data from NADs via standard network protocols and feeds it into the NeuraNAC platform through NATS.

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                    COMPLETE NeuraNAC INGESTION ARCHITECTURE                                │
│                                                                                      │
│   ┌──────────────────────────────────────────────────────────────────────────────┐   │
│   │                           NETWORK ACCESS DEVICES                             │   │
│   │                                                                              │   │
│   │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐      │   │
│   │  │  Cisco   │  │  Aruba   │  │ Juniper  │  │  Meraki  │  │ Generic  │      │   │
│   │  │ Catalyst │  │  CX/IAP  │  │  EX/SRX  │  │  MS/MR   │  │  Switch  │      │   │
│   │  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘      │   │
│   │       │              │              │              │              │           │   │
│   └───────┼──────────────┼──────────────┼──────────────┼──────────────┼───────────┘   │
│           │              │              │              │              │                │
│           │ What each NAD sends to NeuraNAC:                                               │
│           │                                                                           │
│    ┌──────┴──────────────┴──────────────┴──────────────┴──────────────┴──────────┐   │
│    │                                                                             │   │
│    │  ❶ RADIUS Auth       (UDP 1812)  → username, MAC, EAP type, NAS-IP        │   │
│    │  ❷ RADIUS Accounting (UDP 1813)  → session start/stop, bytes, duration     │   │
│    │  ❸ TACACS+           (TCP 49)    → admin auth, command authorization       │   │
│    │  ❹ RadSec            (TCP 2083)  → same as RADIUS but over TLS            │   │
│    │  ❺ SNMP Traps        (UDP 162)   → link up/down, config change, auth fail │   │
│    │  ❻ Syslog            (UDP 514)   → device logs, security events           │   │
│    │  ❼ NetFlow/IPFIX     (UDP 2055)  → traffic flows: src/dst IP, bytes, proto│   │
│    │  ❽ DHCP Relay        (UDP 67)    → DHCP options (OS fingerprint, hostname)│   │
│    │  ❾ CDP/LLDP          (via SNMP)  → neighbor info (NeuraNAC polls the NAD)      │   │
│    │                                                                             │   │
│    └──────┬──────────────┬──────────────┬──────────────┬─────────────────────────┘   │
│           │              │              │              │                              │
│           │              │              │              │                              │
│    ┌──────▼──────┐ ┌─────▼──────┐ ┌────▼──────┐ ┌────▼───────┐                     │
│    │   RADIUS    │ │ Ingestion  │ │ Ingestion │ │ Ingestion  │                     │
│    │   Server    │ │ Collector  │ │ Collector │ │ Collector  │                     │
│    │   (Go)      │ │ (Go) — A   │ │ (Go) — B  │ │ (Go) — C   │                     │
│    │             │ │            │ │           │ │            │                     │
│    │  :1812 Auth │ │  :162 SNMP │ │ :162 SNMP │ │ :162 SNMP  │ ← HPA scales      │
│    │  :1813 Acct │ │  :514 Syslg│ │ :514 Syslg│ │ :514 Syslg │   based on         │
│    │  :2083 TLS  │ │ :2055 NFlow│ │:2055 NFlow│ │:2055 NFlow │   ingestion rate   │
│    │  :49 TACACS │ │  :67 DHCP  │ │ :67 DHCP  │ │ :67 DHCP   │                     │
│    │  :3799 CoA↑ │ │  SNMP poll │ │ SNMP poll │ │ SNMP poll  │                     │
│    └──────┬──────┘ └─────┬──────┘ └────┬──────┘ └────┬───────┘                     │
│           │              │              │              │                              │
│           │              └──────────────┼──────────────┘                              │
│           │                             │                                             │
│           ▼                             ▼                                             │
│    ┌──────────────────────────────────────────────────────────────────────────┐      │
│    │                         NATS JetStream (:4222)                           │      │
│    │                                                                          │      │
│    │  Streams:                                                                │      │
│    │  ├── neuranac.auth.*          (from RADIUS Server)                           │      │
│    │  ├── neuranac.accounting.*    (from RADIUS Server)                           │      │
│    │  ├── neuranac.telemetry.snmp  (from Ingestion Collector — traps)             │      │
│    │  ├── neuranac.telemetry.syslog (from Ingestion Collector — logs)             │      │
│    │  ├── neuranac.telemetry.netflow (from Ingestion Collector — flows)           │      │
│    │  ├── neuranac.telemetry.dhcp  (from Ingestion Collector — DHCP fingerprints) │      │
│    │  ├── neuranac.telemetry.neighbor (from Ingestion Collector — CDP/LLDP)       │      │
│    │  └── neuranac.coa.*          (CoA events)                                    │      │
│    │                                                                          │      │
│    │  Consumers:                                                              │      │
│    │  ├── AI Engine subscribes to telemetry.* for enriched profiling         │      │
│    │  ├── API Gateway subscribes to auth.* for real-time dashboard           │      │
│    │  └── Sync Engine replicates telemetry across sites                      │      │
│    └──────────────────────────────────────────────────────────────────────────┘      │
│           │                             │                                             │
│           ▼                             ▼                                             │
│    ┌──────────────┐              ┌──────────────┐                                    │
│    │  PostgreSQL  │              │  AI Engine   │                                    │
│    │  :5432       │              │  :8081       │                                    │
│    │              │              │              │                                    │
│    │  Tables:     │              │  Enhanced    │                                    │
│    │  sessions    │              │  profiling:  │                                    │
│    │  endpoints   │              │  RADIUS +    │                                    │
│    │  telemetry_  │              │  DHCP +      │                                    │
│    │   flows      │              │  NetFlow +   │                                    │
│    │  telemetry_  │              │  SNMP →      │                                    │
│    │   events     │              │  90%+ device │                                    │
│    │  neighbor_   │              │  accuracy    │                                    │
│    │   topology   │              │  (vs 60% w/  │                                    │
│    │              │              │   RADIUS     │                                    │
│    │              │              │   alone)     │                                    │
│    └──────────────┘              └──────────────┘                                    │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Ingestion Channel Deep Dive

### Channel 1: RADIUS/TACACS+ (Existing — Port 1812/1813/49/2083)

**Direction:** NAD → NeuraNAC (push)
**How it works:** NAD is configured with `radius-server host <NeuraNAC_IP>`. Every auth event triggers a RADIUS Access-Request.

```
  NAD Config (Cisco IOS example):
  ─────────────────────────────────
  radius-server host 10.0.1.100 key testing123
  aaa new-model
  aaa authentication dot1x default group radius
  aaa authorization network default group radius
  aaa accounting dot1x default start-stop group radius
```

**Data collected:** Username, MAC, NAS-IP, NAS-Port, EAP type, VLAN requested, session bytes.

### Channel 2: SNMP Traps (New — Port 162)

**Direction:** NAD → NeuraNAC (push)
**How it works:** NADs are configured to send SNMP traps to NeuraNAC on link up/down, auth failure, config changes.

```
  NAD Config (Cisco IOS example):
  ─────────────────────────────────
  snmp-server host 10.0.1.100 traps version 3 priv neuranac-user
  snmp-server enable traps snmp linkdown linkup
  snmp-server enable traps dot1x auth-fail-vlan
  snmp-server enable traps config
```

**Data collected:** Interface status changes, auth failures, config change timestamps, MAC move notifications.

### Channel 3: NetFlow/IPFIX (New — Port 2055)

**Direction:** NAD → NeuraNAC (push)
**How it works:** NADs export flow records to NeuraNAC. Each flow = (src_ip, dst_ip, protocol, bytes, packets, duration).

```
  NAD Config (Cisco IOS example):
  ─────────────────────────────────
  flow exporter NeuraNAC-EXPORTER
   destination 10.0.1.100
   transport udp 2055
   export-protocol ipfix
  flow monitor NeuraNAC-MONITOR
   exporter NeuraNAC-EXPORTER
   record netflow ipv4 original-input
  interface GigabitEthernet0/1
   ip flow monitor NeuraNAC-MONITOR input
```

**Data collected:** Traffic flows — enables post-auth traffic analysis, shadow AI detection, bandwidth monitoring.

### Channel 4: Syslog (New — Port 514)

**Direction:** NAD → NeuraNAC (push)
**How it works:** NADs send syslog messages to NeuraNAC for log correlation.

```
  NAD Config (Cisco IOS example):
  ─────────────────────────────────
  logging host 10.0.1.100 transport udp port 514
  logging trap informational
  logging facility local6
```

**Data collected:** Device logs — enables correlation of auth events with device-side events, troubleshooting.

### Channel 5: DHCP Relay/Snooping (New — Port 67)

**Direction:** NAD relays DHCP → NeuraNAC snoops
**How it works:** NeuraNAC acts as a DHCP relay helper or snoops DHCP packets from a SPAN port.

**Data collected:** DHCP options (option 55 = OS fingerprint, option 12 = hostname, option 60 = vendor class). This is the **#1 profiling enhancement** — DHCP fingerprinting alone increases device identification accuracy from ~60% to ~85%.

### Channel 6: CDP/LLDP Discovery (New — via SNMP polling)

**Direction:** NeuraNAC → NAD (pull — NeuraNAC polls the NAD)
**How it works:** NeuraNAC's Ingestion Collector periodically queries NAD SNMP MIBs for neighbor tables.

```
  SNMP OIDs polled:
  ─────────────────────────────────
  CDP:  cdpCacheDeviceId     (1.3.6.1.4.1.9.9.23.1.2.1.1.6)
        cdpCachePlatform     (1.3.6.1.4.1.9.9.23.1.2.1.1.8)
  LLDP: lldpRemSysName      (1.0.8802.1.1.2.1.4.1.1.9)
        lldpRemPortId        (1.0.8802.1.1.2.1.4.1.1.7)
```

**Data collected:** Network neighbor topology — which devices are connected to which ports, enabling auto-topology mapping.

### Channel 7: SPAN/TAP Analysis (New — passive)

**Direction:** Network TAP → NeuraNAC (push — mirrored traffic)
**How it works:** A network TAP or SPAN port mirrors traffic to a dedicated NeuraNAC analysis interface.
**Data collected:** Deep packet inspection — HTTP User-Agent, TLS ClientHello (JA3), DNS queries, application identification.

---

## 6. Scaling Architecture

### How Each Component Scales

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          NeuraNAC SCALING ARCHITECTURE                                │
│                                                                                  │
│  ┌────────────────────────────────────────────────────────────────────────────┐  │
│  │  LAYER 1: NETWORK EDGE (L4 Load Balancer)                                 │  │
│  │                                                                            │  │
│  │  ┌──────────────────────────┐  ┌────────────────────────────────────────┐ │  │
│  │  │  L4 UDP Load Balancer   │  │  L4 UDP/TCP Load Balancer              │ │  │
│  │  │  (F5 / HAProxy / NLB)   │  │  (F5 / HAProxy / NLB)                 │ │  │
│  │  │                          │  │                                        │ │  │
│  │  │  VIP: 10.0.1.100:1812   │  │  VIP: 10.0.1.101:162                  │ │  │
│  │  │       10.0.1.100:1813   │  │       10.0.1.101:514                  │ │  │
│  │  │       10.0.1.100:2083   │  │       10.0.1.101:2055                 │ │  │
│  │  │       10.0.1.100:49     │  │       10.0.1.101:67                   │ │  │
│  │  │                          │  │                                        │ │  │
│  │  │  Algorithm: src-ip hash  │  │  Algorithm: src-ip hash               │ │  │
│  │  │  (same NAD → same node) │  │  (same NAD → same collector)          │ │  │
│  │  └─────────┬────────────────┘  └─────────┬──────────────────────────────┘ │  │
│  │            │                              │                                │  │
│  └────────────┼──────────────────────────────┼────────────────────────────────┘  │
│               │                              │                                    │
│  ┌────────────▼──────────────────────────────▼────────────────────────────────┐  │
│  │  LAYER 2: DATA PLANE (Stateless — Horizontal Pod Autoscaler)              │  │
│  │                                                                            │  │
│  │  ┌──────────────┐ ┌──────────────┐      ┌──────────────┐ ┌────────────┐  │  │
│  │  │ RADIUS       │ │ RADIUS       │      │ Ingestion    │ │ Ingestion  │  │  │
│  │  │ Server-1     │ │ Server-2     │ ...  │ Collector-1  │ │ Collector-2│  │  │
│  │  │ :1812/:1813  │ │ :1812/:1813  │      │ :162/:514    │ │ :162/:514  │  │  │
│  │  │ :2083/:49    │ │ :2083/:49    │      │ :2055/:67    │ │ :2055/:67  │  │  │
│  │  └──────┬───────┘ └──────┬───────┘      └──────┬───────┘ └─────┬──────┘  │  │
│  │         │                │                      │               │          │  │
│  │  HPA: min=2, max=8               HPA: min=1, max=4                       │  │
│  │  Scale trigger: CPU > 70%         Scale trigger: packets/sec > 50k        │  │
│  │  Each replica: ~10k auth/sec      Each replica: ~100k events/sec          │  │
│  │                                                                            │  │
│  └─────────┼────────────────┼──────────────────────┼───────────────┼──────────┘  │
│            │                │                      │               │              │
│  ┌─────────▼────────────────▼──────────────────────▼───────────────▼──────────┐  │
│  │  LAYER 3: EVENT BUS (NATS JetStream — Buffer + Decouple)                  │  │
│  │                                                                            │  │
│  │  ┌───────────────────────────────────────────────────────────────────────┐│  │
│  │  │  NATS Cluster (3 nodes for HA)                                        ││  │
│  │  │                                                                       ││  │
│  │  │  Streams: neuranac.auth.*, neuranac.telemetry.*, neuranac.coa.*                     ││  │
│  │  │                                                                       ││  │
│  │  │  Buffering: If downstream is slow, NATS holds messages               ││  │
│  │  │  (JetStream retention: 72h or 10GB per stream)                       ││  │
│  │  │                                                                       ││  │
│  │  │  Fan-out: Multiple consumers process different aspects               ││  │
│  │  │    ├── AI Engine: consumes telemetry.* for profiling                 ││  │
│  │  │    ├── API Gateway: consumes auth.* for dashboard updates            ││  │
│  │  │    ├── SIEM Router: consumes *.* for syslog/CEF forwarding           ││  │
│  │  │    └── Sync Engine: replicates events to peer site                   ││  │
│  │  └───────────────────────────────────────────────────────────────────────┘│  │
│  │                                                                            │  │
│  └────────────────────────┬───────────────────────────────────────────────────┘  │
│                           │                                                      │
│  ┌────────────────────────▼───────────────────────────────────────────────────┐  │
│  │  LAYER 4: CONTROL PLANE (Consumers — Scale Independently)                 │  │
│  │                                                                            │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                    │  │
│  │  │ API Gateway  │  │ Policy Engine│  │ AI Engine    │                    │  │
│  │  │ :8080        │  │ :8082/:9091  │  │ :8081        │                    │  │
│  │  │ HPA: 2–10   │  │ HPA: 2–4     │  │ HPA: 1–4     │                    │  │
│  │  │ ~5k req/sec  │  │ ~20k eval/sec│  │ ~2k score/sec│                    │  │
│  │  └──────────────┘  └──────────────┘  └──────────────┘                    │  │
│  │                                                                            │  │
│  └────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                  │
│  ┌────────────────────────────────────────────────────────────────────────────┐  │
│  │  LAYER 5: DATA (Stateful — Vertical Scale + Replicas)                     │  │
│  │                                                                            │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                    │  │
│  │  │ PostgreSQL   │  │ Redis        │  │ NATS         │                    │  │
│  │  │ Primary +    │  │ Sentinel HA  │  │ 3-node       │                    │  │
│  │  │ Standby      │  │ (3 sentinels)│  │ cluster      │                    │  │
│  │  │              │  │              │  │              │                    │  │
│  │  │ Scale:       │  │ Scale:       │  │ Scale:       │                    │  │
│  │  │ Read replicas│  │ Redis Cluster│  │ Add nodes    │                    │  │
│  │  │ Partitioning │  │ (sharding)   │  │ Leaf nodes   │                    │  │
│  │  └──────────────┘  └──────────────┘  └──────────────┘                    │  │
│  │                                                                            │  │
│  └────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Why NATS is the Key to Scaling

NATS JetStream sits between producers (RADIUS Server, Ingestion Collector) and consumers (AI Engine, API Gateway, SIEM). This architecture means:

1. **Producers never block** — RADIUS Server sends to NATS and immediately responds to the NAD
2. **Consumers scale independently** — Add more AI Engine replicas without touching RADIUS
3. **Burst absorption** — If 10,000 endpoints authenticate at 8 AM, NATS buffers events
4. **Replay** — New consumers can replay historical events from JetStream
5. **Cross-site** — NATS leaf nodes replicate events between sites

---

## 7. Deployment Scenario S1 — NeuraNAC + Hybrid

**The most complete deployment.** Two federated NeuraNAC sites with NeuraNAC coexistence on-prem.

```
                                 INTERNET / WAN
                    ┌──────────────────┼──────────────────┐
                    │                  │                   │
                    ▼                  │                   ▼
┌───────────────────────────────────┐  │  ┌───────────────────────────────────┐
│     ON-PREM SITE (site_type:     │  │  │     CLOUD SITE (site_type:       │
│     onprem)                       │  │  │     cloud)                        │
│                                   │  │  │                                   │
│  ┌─────────────────────────────┐ │  │  │ ┌─────────────────────────────┐  │
│  │    CAMPUS NETWORK           │ │  │  │ │    CLOUD VPC                │  │
│  │                             │ │  │  │ │                             │  │
│  │  ┌────────┐  ┌────────┐    │ │  │  │ │  ┌────────┐  ┌────────┐   │  │
│  │  │Switch-1│  │Switch-2│    │ │  │  │ │  │ Cloud  │  │ Remote │   │  │
│  │  │Cisco   │  │Aruba   │    │ │  │  │ │  │ NAD-1  │  │ NAD-2  │   │  │
│  │  └───┬────┘  └───┬────┘    │ │  │  │ │  └───┬────┘  └───┬────┘   │  │
│  │      │            │         │ │  │  │ │      │            │        │  │
│  │      │ RADIUS     │ RADIUS  │ │  │  │ │      │ RADIUS     │ RADIUS │  │
│  │      │ SNMP trap  │ Syslog  │ │  │  │ │      │            │        │  │
│  │      │ NetFlow    │ NetFlow │ │  │  │ │      │            │        │  │
│  │      │ DHCP relay │         │ │  │  │ │      │            │        │  │
│  └──────┼────────────┼─────────┘ │  │  │ └──────┼────────────┼────────┘  │
│         │            │           │  │  │        │            │           │
│  ┌──────▼────────────▼─────────┐ │  │  │ ┌──────▼────────────▼─────────┐ │
│  │  L4 Load Balancer           │ │  │  │ │  Cloud LB (NLB/ALB)        │ │
│  │  VIP :1812/1813/162/514/2055│ │  │  │ │  VIP :1812/1813            │ │
│  └──────┬──────────────────────┘ │  │  │ └──────┬──────────────────────┘ │
│         │                        │  │  │        │                        │
│  ┌──────▼────────────────────┐   │  │  │ ┌──────▼────────────────────┐  │
│  │  NeuraNAC ON-PREM STACK        │   │  │  │ │  NeuraNAC CLOUD STACK          │  │
│  │                            │   │  │  │ │                            │  │
│  │  ┌────────────────────┐   │   │  │  │ │  ┌────────────────────┐   │  │
│  │  │ RADIUS Server ×2   │   │   │  │  │ │  │ RADIUS Server ×2   │   │  │
│  │  │ :1812/:1813/:2083  │   │   │  │  │ │  │ :1812/:1813/:2083  │   │  │
│  │  └────────────────────┘   │   │  │  │ │  └────────────────────┘   │  │
│  │  ┌────────────────────┐   │   │  │  │ │  ┌────────────────────┐   │  │
│  │  │ Ingestion Collector│   │   │  │  │ │  │ Ingestion Collector│   │  │
│  │  │ :162/:514/:2055/:67│   │   │  │  │ │  │ :162/:514/:2055    │   │  │
│  │  └────────────────────┘   │   │  │  │ │  └────────────────────┘   │  │
│  │  ┌────────────────────┐   │   │  │  │ │  ┌────────────────────┐   │  │
│  │  │ API Gateway ×3     │   │   │  │  │ │  │ API Gateway ×3     │   │  │
│  │  │ :8080              │   │   │  │  │ │  │ :8080              │   │  │
│  │  └────────────────────┘   │   │  │  │ │  └────────────────────┘   │  │
│  │  ┌────────────────────┐   │   │  │  │ │  ┌────────────────────┐   │  │
│  │  │ Policy Engine ×2   │   │   │  │  │ │  │ Policy Engine ×2   │   │  │
│  │  │ :8082/:9091        │   │   │  │  │ │  │ :8082/:9091        │   │  │
│  │  └────────────────────┘   │   │  │  │ │  └────────────────────┘   │  │
│  │  ┌────────────────────┐   │   │  │  │ │  ┌────────────────────┐   │  │
│  │  │ AI Engine ×2       │   │   │  │  │ │  │ AI Engine ×2       │   │  │
│  │  │ :8081              │   │   │  │  │ │  │ :8081              │   │  │
│  │  └────────────────────┘   │   │  │  │ │  └────────────────────┘   │  │
│  │  ┌────────────────────┐   │   │  │  │ │  ┌────────────────────┐   │  │
│  │  │ Sync Engine        │◄──┼───┼──┼──┼─┤  │ Sync Engine        │   │  │
│  │  │ :9090 gRPC+mTLS    │   │   │  │  │ │  │ :9090 gRPC+mTLS    │   │  │
│  │  └────────────────────┘   │   │  │  │ │  └────────────────────┘   │  │
│  │  ┌────────────────────┐   │   │  │  │ │  ┌────────────────────┐   │  │
│  │  │ NeuraNAC Bridge :8090   │   │   │  │  │ │  │ NeuraNAC Bridge :8090   │   │  │
│  │  │ NeuraNAC adapter active │   │   │  │  │ │  │ No NeuraNAC adapter     │   │  │
│  │  └─────────┬──────────┘   │   │  │  │ │  └────────────────────┘   │  │
│  │            │               │   │  │  │ │                            │  │
│  │  ┌─────────▼──────────┐   │   │  │  │ │  ┌────────────────────┐   │  │
│  │  │ PostgreSQL + Redis │   │   │  │  │ │  │ PostgreSQL + Redis │   │  │
│  │  │ NATS (hub cluster) │   │   │  │  │ │  │ NATS (leaf → hub)  │   │  │
│  │  └────────────────────┘   │   │  │  │ │  └────────────────────┘   │  │
│  └────────────────────────────┘   │  │  │ └────────────────────────────┘ │
│                                   │  │  │                                │
│  ┌──── NeuraNAC Coexistence ─────────┐│  │  │                                │
│  │  Legacy NAC Cluster            ││  │  │                                │
│  │  NeuraNAC-managed NADs             ││  │  │                                │
│  │  ERS API :9060 ◄──► NeuraNAC Bridge││  │  │                                │
│  │  Event Stream :8910 ◄──► NeuraNAC Bridge ││  │  │                                │
│  └───────────────────────────────┘│  │  │                                │
│                                   │  │  │                                │
│  FEDERATION: HMAC-SHA256 signed   │◄─┼──┤  FEDERATION: HMAC-SHA256      │
│  Sync Engine: gRPC + mTLS + gzip │──┼──►│  Sync Engine: gRPC + mTLS     │
│  NATS: hub cluster ◄──────────── │──┼──►│  NATS: leaf node              │
│                                   │  │  │                                │
└───────────────────────────────────┘  │  └────────────────────────────────┘
                                       │
                                 ┌─────┴──────┐
                                 │ Observability│
                                 │ Prometheus   │
                                 │ Grafana      │
                                 │ Loki         │
                                 │ (per site)   │
                                 └──────────────┘
```

---

## 8. Deployment Scenario S2 — Cloud Standalone

**Simplest deployment.** Single cloud site, no NeuraNAC, no federation.

```
                    ┌──────────────────────────────────────────────┐
                    │              CLOUD VPC                        │
                    │                                               │
                    │  ┌───────────────────────────────────────┐   │
                    │  │    NADs (cloud-connected switches/APs) │   │
                    │  │    RADIUS :1812  →  NeuraNAC RADIUS Server  │   │
                    │  │    Telemetry     →  Ingestion Collector │   │
                    │  └───────────────────────┬───────────────┘   │
                    │                          │                    │
                    │  ┌───────────────────────▼───────────────┐   │
                    │  │          NeuraNAC PLATFORM (K8s)            │   │
                    │  │                                        │   │
                    │  │  ┌────────────┐  ┌─────────────────┐  │   │
                    │  │  │ RADIUS ×2  │  │ Ingest Coll. ×1 │  │   │
                    │  │  │ :1812/:1813│  │ :162/:514/:2055 │  │   │
                    │  │  └─────┬──────┘  └──────┬──────────┘  │   │
                    │  │        │                 │             │   │
                    │  │        ▼                 ▼             │   │
                    │  │  ┌──────────────────────────────────┐ │   │
                    │  │  │     NATS JetStream (single)      │ │   │
                    │  │  └──────────┬───────────────────────┘ │   │
                    │  │             │                          │   │
                    │  │  ┌──────────▼──┐  ┌──────┐  ┌──────┐ │   │
                    │  │  │ API GW ×2   │  │Policy│  │  AI  │ │   │
                    │  │  │ :8080       │  │ :8082│  │:8081 │ │   │
                    │  │  └─────────────┘  └──────┘  └──────┘ │   │
                    │  │                                        │   │
                    │  │  ┌──────┐  ┌──────┐  ┌──────────────┐│   │
                    │  │  │  PG  │  │Redis │  │ Web :3001    ││   │
                    │  │  │:5432 │  │:6379 │  │              ││   │
                    │  │  └──────┘  └──────┘  └──────────────┘│   │
                    │  │                                        │   │
                    │  │  NOT present: NeuraNAC Bridge, Federation,  │   │
                    │  │  Sync Engine (cross-site), Peer Site   │   │
                    │  └────────────────────────────────────────┘   │
                    │                                               │
                    └──────────────────────────────────────────────┘

  Scale: RADIUS HPA 2→8, API GW HPA 2→10, Ingestion HPA 1→4
  Capacity: ~20k endpoints, ~5k concurrent sessions
```

---

## 9. Deployment Scenario S3 — On-Prem Standalone

**Twin-node HA deployment.** No cloud, no NeuraNAC — pure on-prem with high availability.

```
┌───────────────────────────────────────────────────────────────────────────────┐
│                          ON-PREM DATA CENTER                                   │
│                                                                                │
│   ┌──────────────────────────────────┐                                        │
│   │       CAMPUS NETWORK              │                                        │
│   │                                   │                                        │
│   │  ┌────────┐ ┌────────┐ ┌───────┐│                                        │
│   │  │Switch-1│ │Switch-2│ │WLC-1  ││                                        │
│   │  │        │ │        │ │       ││                                        │
│   │  └───┬────┘ └───┬────┘ └──┬────┘│                                        │
│   │      │           │         │     │                                        │
│   │      │ RADIUS / SNMP / NetFlow / Syslog / DHCP                           │
│   └──────┼───────────┼─────────┼─────┘                                        │
│          │           │         │                                               │
│   ┌──────▼───────────▼─────────▼──────┐                                       │
│   │    L4 LOAD BALANCER (F5/HAProxy)  │                                       │
│   │    VIP: 10.0.1.100               │                                       │
│   │    :1812/:1813/:162/:514/:2055   │                                       │
│   └───────────┬───────────────┬───────┘                                       │
│               │               │                                                │
│    ┌──────────▼────────┐  ┌───▼──────────────┐                                │
│    │   NODE A (Active) │  │  NODE B (Standby) │                                │
│    │                    │  │                    │                                │
│    │  RADIUS Server    │  │  RADIUS Server    │                                │
│    │  Ingestion Coll.  │  │  Ingestion Coll.  │                                │
│    │  API Gateway      │  │  API Gateway      │                                │
│    │  Policy Engine    │  │  Policy Engine    │                                │
│    │  AI Engine        │  │  AI Engine        │                                │
│    │  Sync Engine  ◄───┼──┼──► Sync Engine    │                                │
│    │       gRPC+mTLS   │  │       gRPC+mTLS   │                                │
│    │  PostgreSQL (P)   │  │  PostgreSQL (R)   │                                │
│    │  Redis            │  │  Redis            │                                │
│    │  NATS (hub)       │  │  NATS (leaf)      │                                │
│    │                    │  │                    │                                │
│    └────────────────────┘  └────────────────────┘                                │
│                                                                                │
│    HA Model: Active-Active for RADIUS (both nodes handle auth)                │
│              Active-Standby for writes (journal replication via Sync Engine)   │
│              Automatic failover: DNS/LB health check based                     │
│                                                                                │
│    NOT present: NeuraNAC Bridge, Federation MW, Cloud Peer Site                    │
│                                                                                │
└───────────────────────────────────────────────────────────────────────────────┘

  Scale: Twin-node HA, ~40k endpoints, ~10k concurrent sessions
  Failover: < 30s (LB health check + Sync Engine reconnect)
```

---

## 10. Deployment Scenario S4 — Hybrid No NeuraNAC

**Two federated NeuraNAC sites, greenfield (no legacy NeuraNAC).**

```
┌────────────────────────────────┐            ┌────────────────────────────────┐
│   ON-PREM SITE                 │            │   CLOUD SITE                   │
│   site_type: onprem            │            │   site_type: cloud             │
│                                │            │                                │
│  ┌──────────────────────────┐  │            │  ┌──────────────────────────┐  │
│  │  Campus NADs             │  │            │  │  Cloud / Remote NADs     │  │
│  │  RADIUS + Telemetry      │  │            │  │  RADIUS + Telemetry      │  │
│  └────────────┬─────────────┘  │            │  └────────────┬─────────────┘  │
│               │                │            │               │                │
│  ┌────────────▼─────────────┐  │            │  ┌────────────▼─────────────┐  │
│  │  RADIUS Server ×2       │  │            │  │  RADIUS Server ×2       │  │
│  │  Ingestion Collector ×1  │  │            │  │  Ingestion Collector ×1  │  │
│  │  API Gateway ×3          │  │            │  │  API Gateway ×3          │  │
│  │  Policy Engine ×2        │  │            │  │  Policy Engine ×2        │  │
│  │  AI Engine ×2            │  │            │  │  AI Engine ×2            │  │
│  │  Sync Engine ×1          │  │  gRPC+mTLS │  │  Sync Engine ×1          │  │
│  │  NeuraNAC Bridge :8090        │◄─┼────────────┼──►│  NeuraNAC Bridge :8090        │  │
│  │                           │  │            │  │                           │  │
│  │  PostgreSQL + Redis      │  │  NATS hub  │  │  PostgreSQL + Redis      │  │
│  │  NATS hub cluster        │◄─┼────────────┼──►│  NATS leaf               │  │
│  └───────────────────────────┘  │  ◄─leaf   │  └───────────────────────────┘  │
│                                │            │                                │
│  Federation: HMAC-SHA256      │◄───────────►│  Federation: HMAC-SHA256      │
│  X-NeuraNAC-Site: local|peer|all  │            │  X-NeuraNAC-Site: local|peer|all  │
│                                │            │                                │
│  NO NeuraNAC Bridge adapter        │            │  NO NeuraNAC Bridge adapter        │
│  NO NeuraNAC Cluster               │            │  NO NeuraNAC Cluster               │
└────────────────────────────────┘            └────────────────────────────────┘

  Scale per site: RADIUS HPA 2→8, API GW HPA 2→10, Ingestion HPA 1→4
  Cross-site: Sync Engine replication (sessions, endpoints, policies, telemetry)
  Total capacity: ~80k endpoints across both sites
```

---

## 11. Scaling Numbers & Capacity Planning

### Per-Component Throughput

| Component           | Per Replica              | Min Replicas | Max Replicas (HPA) | Scale Trigger           |
| ------------------- | ------------------------ | ------------ | ------------------ | ----------------------- |
| RADIUS Server       | ~10k auth/sec            | 2            | 8                  | CPU > 70%               |
| Ingestion Collector | ~100k events/sec         | 1            | 4                  | Packets/sec > 50k       |
| API Gateway         | ~5k req/sec              | 2            | 10                 | CPU > 70%               |
| Policy Engine       | ~20k eval/sec            | 2            | 4                  | CPU > 60%               |
| AI Engine           | ~2k score/sec            | 1            | 4                  | CPU > 70%, Memory > 80% |
| Sync Engine         | ~50k journal entries/sec | 1 per node   | 1 per node         | N/A (fixed per node)    |
| NeuraNAC Bridge          | ~1k relay/sec            | 1            | 2                  | CPU > 70%               |

### Deployment Sizing

| Size                 | Endpoints | Concurrent Sessions | RADIUS replicas | Ingestion replicas | DB Size  |
| -------------------- | --------- | ------------------- | --------------- | ------------------ | -------- |
| **Small**            | 1–5k      | 500                 | 2               | 1                  | 10 GB    |
| **Medium**           | 5–20k     | 2,000               | 3               | 2                  | 50 GB    |
| **Large**            | 20–50k    | 5,000               | 5               | 3                  | 200 GB   |
| **Enterprise**       | 50–200k   | 20,000              | 8               | 4                  | 1 TB     |
| **Hybrid (2 sites)** | 200k+     | 40,000              | 8+8             | 4+4                | 1 TB × 2 |

### Load Balancing Strategy

| Protocol    | Transport | LB Type  | Algorithm      | Sticky?                    |
| ----------- | --------- | -------- | -------------- | -------------------------- |
| RADIUS Auth | UDP :1812 | L4 (NLB) | Source IP hash | Yes (same NAD → same node) |
| RADIUS Acct | UDP :1813 | L4 (NLB) | Source IP hash | Yes                        |
| RadSec      | TCP :2083 | L4 (NLB) | Source IP hash | Yes                        |
| TACACS+     | TCP :49   | L4 (NLB) | Source IP hash | Yes                        |
| SNMP Traps  | UDP :162  | L4 (NLB) | Round-robin    | No                         |
| Syslog      | UDP :514  | L4 (NLB) | Round-robin    | No                         |
| NetFlow     | UDP :2055 | L4 (NLB) | Round-robin    | No                         |
| REST API    | TCP :8080 | L7 (ALB) | Least-conn     | No                         |
| Web UI      | TCP :3001 | L7 (ALB) | Least-conn     | No                         |

> **Why source-IP hash for RADIUS?** EAP-TLS handshakes span multiple packets. All packets in a session must reach the same RADIUS replica because EAP state is held in that replica's Redis-backed session store.

---

## 12. Implementation Roadmap

### Phase 1: Ingestion Collector Core (v1.1.0)

| Task                                        | Priority | Effort  |
| ------------------------------------------- | -------- | ------- |
| SNMP Trap Receiver (UDP :162)               | P0       | 2 weeks |
| Syslog Receiver (UDP :514)                  | P0       | 1 week  |
| NATS integration (publish telemetry events) | P0       | 1 week  |
| Helm chart + Docker Compose config          | P0       | 3 days  |
| DB schema: `telemetry_events` table         | P0       | 2 days  |
| Dashboard: telemetry event feed             | P1       | 1 week  |

### Phase 2: Traffic Telemetry (v1.2.0)

| Task                                                    | Priority | Effort  |
| ------------------------------------------------------- | -------- | ------- |
| NetFlow v5/v9/IPFIX Collector (UDP :2055)               | P0       | 2 weeks |
| DHCP Snooping / Fingerprinting                          | P0       | 2 weeks |
| AI Engine: enhanced profiling (RADIUS + DHCP + NetFlow) | P0       | 2 weeks |
| DB schema: `telemetry_flows`, `dhcp_fingerprints`       | P0       | 3 days  |
| Dashboard: traffic flow visualization                   | P1       | 1 week  |

### Phase 3: Active Discovery (v1.3.0)

| Task                                                 | Priority | Effort  |
| ---------------------------------------------------- | -------- | ------- |
| SNMP Polling Engine (CDP/LLDP neighbors, ARP tables) | P1       | 2 weeks |
| Auto-topology builder from SNMP data                 | P1       | 2 weeks |
| SPAN/TAP packet analyzer (HTTP, TLS, DNS)            | P2       | 3 weeks |
| AI Engine: deep profiling (all probe data)           | P1       | 2 weeks |

### Service Definition

```
services/
└── ingestion-collector/     # Go 1.22+ — Multi-protocol network telemetry receiver
    ├── cmd/collector/main.go    # Entry point, listener setup
    ├── internal/
    │   ├── snmp/               # SNMP trap receiver + polling engine
    │   ├── syslog/             # Syslog receiver (RFC 5424 + RFC 3164)
    │   ├── netflow/            # NetFlow v5/v9/IPFIX decoder
    │   ├── dhcp/               # DHCP snooping + fingerprint DB
    │   ├── discovery/          # CDP/LLDP neighbor discovery via SNMP
    │   └── publisher/          # NATS JetStream publisher
    ├── Dockerfile              # Multi-stage, distroless, non-root
    └── go.mod
```

---

## 13. Implementation Status

> All items below have been implemented and are ready for integration testing.

| Component | Status | Files |
|-----------|--------|-------|
| **Go Service — main.go** | ✅ Done | `services/ingestion-collector/cmd/collector/main.go` |
| **Config** | ✅ Done | `internal/config/config.go` (env-driven, 20+ settings) |
| **NATS Publisher** | ✅ Done | `internal/publisher/publisher.go` (batch + JetStream) |
| **SNMP Trap Receiver** | ✅ Done | `internal/snmp/trap_receiver.go` (UDP 1162, SNMPv2c) |
| **Syslog Receiver** | ✅ Done | `internal/syslog/receiver.go` (UDP 1514, RFC 5424/3164) |
| **NetFlow/IPFIX Collector** | ✅ Done | `internal/netflow/collector.go` (UDP 2055, v5/v9/v10) |
| **DHCP Snooper** | ✅ Done | `internal/dhcp/snooper.go` (UDP 6767, fingerprinting) |
| **CDP/LLDP Discovery** | ✅ Done | `internal/discovery/neighbor.go` (SNMP polling) |
| **Metrics** | ✅ Done | `internal/metrics/metrics.go` (Prometheus-style) |
| **Dockerfile** | ✅ Done | Multi-stage, distroless, non-root |
| **DB Migration** | ✅ Done | `V007_network_ingestion.sql` (5 tables, indexes, retention) |
| **Docker Compose** | ✅ Done | `ingestion-collector` service with all UDP ports |
| **Helm Template** | ✅ Done | `templates/ingestion-collector.yaml` (Deployment + Service) |
| **Helm Values** | ✅ Done | `ingestionCollector` section in `values.yaml` |
| **API Gateway Router** | ✅ Done | `routers/telemetry.py` (10 endpoints) |
| **Go Unit Tests** | ✅ Done | 30 tests (config, snmp, syslog, netflow, dhcp) |
| **Python Unit Tests** | ✅ Done | 24 tests (`test_telemetry.py`) |
| **Sanity Tests** | ✅ Done | 20 tests (ing-01 to ing-20) |

### Database Tables Added (V007)

| Table | Purpose |
|-------|---------|
| `neuranac_telemetry_events` | SNMP traps, syslog events |
| `neuranac_telemetry_flows` | NetFlow/IPFIX flow records |
| `neuranac_dhcp_fingerprints` | DHCP-based OS fingerprinting |
| `neuranac_neighbor_topology` | CDP/LLDP neighbor graph |
| `neuranac_ingestion_collectors` | Collector instance status/heartbeat |

### API Endpoints Added

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/telemetry/events` | List telemetry events (filterable) |
| GET | `/api/v1/telemetry/events/summary` | Event count by type/severity |
| GET | `/api/v1/telemetry/flows` | List NetFlow/IPFIX records |
| GET | `/api/v1/telemetry/flows/top-talkers` | Top N sources by bytes |
| GET | `/api/v1/telemetry/dhcp` | List DHCP fingerprints |
| GET | `/api/v1/telemetry/dhcp/os-distribution` | OS type distribution |
| GET | `/api/v1/telemetry/neighbors` | List CDP/LLDP neighbors |
| GET | `/api/v1/telemetry/neighbors/topology-map` | Network topology graph |
| GET | `/api/v1/telemetry/collectors` | Collector instance status |
| GET | `/api/v1/telemetry/health` | Telemetry subsystem health |

---

## Summary

| Question                                     | Answer                                                                                                                                   |
| -------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| How do NADs push data to NeuraNAC?                | NADs are configured to point to NeuraNAC as their RADIUS/TACACS+ server. The NAD **pushes** AAA packets to NeuraNAC on every auth event.           |
| Is the RADIUS server the ingestion service?  | **Yes** — for AAA traffic. The Go RADIUS server IS the ingestion point for auth/acct.                                                    |
| Do we need a traffic grabber?                | **Yes** — a new **Ingestion Collector** service is needed for SNMP traps, Syslog, NetFlow, DHCP snooping, and CDP/LLDP.                  |
| How does it scale?                           | **Horizontally** — stateless RADIUS and Collector replicas behind L4 LB, decoupled via NATS JetStream, HPA in K8s.                       |
| How does architecture differ per deployment? | S1 (NeuraNAC+Hybrid): full stack × 2 sites + NeuraNAC. S2 (Cloud): single site, minimal. S3 (On-Prem): twin-node HA. S4 (Hybrid): 2 sites, no NeuraNAC. |
