# NeuraNAC Deployment Topology & Data Flow Reference

> **Version:** 1.0.0 | **Date:** 2026-03-03 | **Status:** GA

---

## Table of Contents

1. [Service Inventory](#1-service-inventory)
2. [Infrastructure Components](#2-infrastructure-components)
3. [Component Connectivity Matrix](#3-component-connectivity-matrix)
4. [Scenario S1 — NeuraNAC + Hybrid (Cloud + On-Prem)](#4-scenario-s1--lnac-hybrid-cloud-on-prem)
5. [Scenario S2 — Cloud Standalone (No NeuraNAC)](#5-scenario-s2--cloud-standalone-no-lnac)
6. [Scenario S3 — On-Prem Standalone (No NeuraNAC)](#6-scenario-s3--on-prem-standalone-no-lnac)
7. [Scenario S4 — Hybrid No NeuraNAC](#7-scenario-s4--hybrid-no-lnac)
8. [Unified Component Legend](#8-unified-component-legend)
9. [Data Flow: RADIUS Authentication (End-to-End)](#9-data-flow-radius-authentication-end-to-end)
10. [Data Flow: Policy Evaluation](#10-data-flow-policy-evaluation)
11. [Data Flow: AI-Powered Profiling & Risk](#11-data-flow-ai-powered-profiling--risk)
12. [Data Flow: Cross-Site Federation (S1, S4)](#12-data-flow-cross-site-federation-s1-s4)
13. [Data Flow: NeuraNAC Coexistence (S1 Only)](#13-data-flow-lnac-coexistence-s1-only)
14. [Data Flow: Real-Time Events (NATS + WebSocket)](#14-data-flow-real-time-events-nats--websocket)
15. [Data Flow: Sync Engine Replication](#15-data-flow-sync-engine-replication)
16. [Port & Protocol Reference](#16-port--protocol-reference)
17. [Environment Variables by Scenario](#17-environment-variables-by-scenario)

---

## 1. Service Inventory

| #   | Service           | Language                | Port(s)                    | Purpose                                                         |
| --- | ----------------- | ----------------------- | -------------------------- | --------------------------------------------------------------- |
| 1   | **API Gateway**   | Python / FastAPI        | 8080                       | REST API, 30 routers, 11 middleware, JWT/RBAC auth, federation  |
| 2   | **RADIUS Server** | Go                      | 1812, 1813, 2083, 49, 3799 | RADIUS (PAP/EAP-TLS/PEAP/MAB), RadSec, TACACS+, CoA             |
| 3   | **Policy Engine** | Python / FastAPI + gRPC | 8082, 9091                 | Rule evaluation, VLAN/SGT assignment, NATS policy reload        |
| 4   | **AI Engine**     | Python / FastAPI        | 8081                       | 16 modules: profiling, risk, anomaly, shadow AI, NLP, playbooks |
| 5   | **Sync Engine**   | Go / gRPC               | 9090, 9100                 | Cross-node/cross-site replication, cursor-based resync, mTLS    |
| 6   | **Bridge Connector** | Python / FastAPI        | 8090                       | On-prem NeuraNAC proxy, ERS relay, Event Stream bridge, WS tunnel          |
| 7   | **Web Dashboard** | React 18 / TypeScript   | 3001                       | 33 pages, AI chat mode, NeuraNAC management, site selector           |

---

## 2. Infrastructure Components

| Component      | Technology          | Port             | Purpose                                                     |
| -------------- | ------------------- | ---------------- | ----------------------------------------------------------- |
| **PostgreSQL** | PostgreSQL 16       | 5432             | 65 tables (V001–V004), multi-tenant, privacy-aware          |
| **Redis**      | Redis 7             | 6379             | Session cache, rate limiting, token buckets, AI baselines   |
| **NATS**       | NATS 2.10 JetStream | 4222, 7422, 8222 | Event bus, pub/sub, 3-node clustering, leaf node federation |
| **Prometheus** | Prometheus          | 9092             | Metrics collection, 25 alert rules (5 groups)               |
| **Grafana**    | Grafana             | 3000             | 17 dashboard panels, SLO/SLI monitoring                     |

---

## 3. Component Connectivity Matrix

```
                  ┌─────┬─────┬─────┬─────┬─────┬─────┬─────┬────┬─────┬──────┐
                  │ API │ RAD │ POL │  AI │SYNC │ NeuraNAC │ WEB │ PG │Redis│ NATS │
                  │ GW  │ SRV │ ENG │ ENG │ ENG │CONN │ UI  │    │     │      │
  ┌───────────────┼─────┼─────┼─────┼─────┼─────┼─────┼─────┼────┼─────┼──────┤
  │ API Gateway   │  -  │     │ HTTP│ HTTP│     │     │     │ SQL│ R/W │ Pub  │
  │               │     │     │gRPC │     │     │     │     │    │     │ Sub  │
  ├───────────────┼─────┼─────┼─────┼─────┼─────┼─────┼─────┼────┼─────┼──────┤
  │ RADIUS Server │     │  -  │ HTTP│ HTTP│     │     │     │ SQL│     │ Pub  │
  │               │     │     │gRPC │     │     │     │     │    │     │      │
  ├───────────────┼─────┼─────┼─────┼─────┼─────┼─────┼─────┼────┼─────┼──────┤
  │ Policy Engine │     │     │  -  │     │     │     │     │ SQL│     │ Sub  │
  ├───────────────┼─────┼─────┼─────┼─────┼─────┼─────┼─────┼────┼─────┼──────┤
  │ AI Engine     │     │     │     │  -  │     │     │     │ SQL│ R/W │      │
  ├───────────────┼─────┼─────┼─────┼─────┼─────┼─────┼─────┼────┼─────┼──────┤
  │ Sync Engine   │     │     │     │     │  -  │     │     │ SQL│     │ Sub  │
  │               │     │     │     │     │     │     │     │    │     │ Pub  │
  ├───────────────┼─────┼─────┼─────┼─────┼─────┼─────┼─────┼────┼─────┼──────┤
  │ Bridge Connector │ WS  │     │     │     │     │  -  │     │    │     │      │
  │               │HTTP │     │     │     │     │     │     │    │     │      │
  ├───────────────┼─────┼─────┼─────┼─────┼─────┼─────┼─────┼────┼─────┼──────┤
  │ Web Dashboard │ HTTP│     │     │     │     │     │  -  │    │     │      │
  │               │ WS  │     │     │     │     │     │     │    │     │      │
  └───────────────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴────┴─────┴──────┘

  HTTP = REST API calls    gRPC = Protocol Buffer RPC    WS = WebSocket
  SQL  = PostgreSQL conn   R/W  = Redis read/write       Pub/Sub = NATS JetStream
```

---

## 4. Scenario S1 — NeuraNAC + Hybrid (Cloud + On-Prem)

**The most complete deployment.** Two federated NeuraNAC sites with NeuraNAC coexistence on the on-prem side.

- `DEPLOYMENT_MODE=hybrid` | `NeuraNAC_ENABLED=true`
- Two sites: on-prem (`site_type=onprem`) + cloud (`site_type=cloud`)
- Bridge Connector runs on-prem only

```
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│                            CUSTOMER ON-PREM DATA CENTER                                       │
│                            [site_id: ...000001] [site_type: onprem]                           │
│                                                                                               │
│   ┌─────────────────────────────────────────────────────────────────────────────────────┐     │
│   │                              NeuraNAC ON-PREM SITE                                       │     │
│   │                                                                                     │     │
│   │   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │     │
│   │   │ Web Dashboard│  │ API Gateway  │  │ RADIUS Server│  │ Policy Engine│           │     │
│   │   │ :3001        │  │ :8080        │  │ :1812 (UDP)  │  │ :8082 (HTTP) │           │     │
│   │   │ React 18     │  │ 30 routers   │  │ :1813 (Acct) │  │ :9091 (gRPC) │           │     │
│   │   │ 33 pages     │  │ 11 middleware │  │ :2083 (TLS)  │  │ NATS reload  │           │     │
│   │   │ AI chat mode │  │ Federation MW│  │ :49 (TACACS+)│  │ 14 operators │           │     │
│   │   └──────┬───────┘  └──┬───┬───┬───┘  │ :3799 (CoA)  │  └──────┬───────┘           │     │
│   │          │ HTTP/WS     │   │   │       │ PAP/EAP/MAB  │         │                   │     │
│   │          └─────────────┘   │   │       └───┬──────┬───┘         │                   │     │
│   │                            │   │           │      │             │                   │     │
│   │   ┌──────────────┐         │   │           │ HTTP │gRPC         │                   │     │
│   │   │ AI Engine    │◄────────┘   │           │      │             │                   │     │
│   │   │ :8081        │             │           │      └─────────────┘                   │     │
│   │   │ 16 modules   │             │           │                                        │     │
│   │   │ profiling,   │             │           │                                        │     │
│   │   │ risk, NLP    │             │           │                                        │     │
│   │   └──────────────┘             │           │                                        │     │
│   │                                │           │                                        │     │
│   │   ┌──────────────┐  ┌─────────┴──┐  ┌─────┴────────┐  ┌──────────────┐            │     │
│   │   │ Sync Engine  │  │ PostgreSQL │  │    Redis     │  │    NATS      │            │     │
│   │   │ :9090 (gRPC) │  │ :5432      │  │    :6379     │  │ :4222 (client│            │     │
│   │   │ :9100 (HTTP) │  │ 65 tables  │  │ session cache│  │ :7422 (leaf) │            │     │
│   │   │ hub-spoke    │  │ V001-V004  │  │ rate limits  │  │ :8222 (mon.) │            │     │
│   │   │ mTLS + gzip  │  │ multi-     │  │ token bucket │  │ JetStream    │            │     │
│   │   │ cursor resync│  │ tenant     │  │ AI baselines │  │ 3-node cluster│           │     │
│   │   └──────┬───────┘  └────────────┘  └──────────────┘  └──────────────┘            │     │
│   │          │                                                                         │     │
│   └──────────┼─────────────────────────────────────────────────────────────────────────┘     │
│              │                                                                               │
│   ┌──────────┼───────────────────────────────────────────────────────────────────────┐       │
│   │  NeuraNAC INTEGRATION LAYER                                                           │       │
│   │          │                                                                       │       │
│   │   ┌──────┴───────┐         ┌──────────────────────────────────────┐              │       │
│   │   │Bridge Connector │  ERS    │ CISCO NeuraNAC CLUSTER                    │              │       │
│   │   │ :8090        │◄───────►│  ┌──────────┐  ┌──────────┐         │              │       │
│   │   │ ERS relay    │  :9060  │  │ NeuraNAC PAN  │  │ NeuraNAC PSN  │         │              │       │
│   │   │ Event Stream bridge│◄───────►│  │ Admin    │  │ RADIUS   │         │              │       │
│   │   │ WS tunnel to │  :8910  │  │ ERS API  │  │ :1812    │         │              │       │
│   │   │ cloud NeuraNAC    │         │  │ Event Stream   │  │ :2083    │         │              │       │
│   │   │ registration │         │  └──────────┘  └──────────┘         │              │       │
│   │   │ heartbeat    │         │  Entities: NADs, Endpoints, SGTs,   │              │       │
│   │   └──────┬───────┘         │  Policies, TrustSec, Certificates   │              │       │
│   │          │                 └──────────────────────────────────────┘              │       │
│   └──────────┼───────────────────────────────────────────────────────────────────────┘       │
│              │                                                                               │
└──────────────┼───────────────────────────────────────────────────────────────────────────────┘
               │
               │  Federation: HMAC-SHA256 signed HTTP
               │  Headers: X-NeuraNAC-Site: local|peer|all
               │  Sync Engine: gRPC + gzip + mTLS
               │  NATS: Leaf node → Hub cluster
               │
┌──────────────┼───────────────────────────────────────────────────────────────────────────────┐
│              ▼                                                                               │
│   ┌─────────────────────────────────────────────────────────────────────────────────────┐    │
│   │                              NeuraNAC CLOUD SITE                                         │    │
│   │                              [site_id: ...000002] [site_type: cloud]                │    │
│   │                                                                                     │    │
│   │   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │    │
│   │   │ Web Dashboard│  │ API Gateway  │  │ RADIUS Server│  │ Policy Engine│           │    │
│   │   │ :3001        │  │ :8080        │  │ :1812 (UDP)  │  │ :8082 (HTTP) │           │    │
│   │   │              │  │ Federation MW│  │ :1813, :2083 │  │ :9091 (gRPC) │           │    │
│   │   └──────────────┘  └──────────────┘  │ :49, :3799   │  └──────────────┘           │    │
│   │                                       └──────────────┘                              │    │
│   │   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │    │
│   │   │ AI Engine    │  │ Sync Engine  │  │ PostgreSQL   │  │    NATS      │           │    │
│   │   │ :8081        │  │ :9090, :9100 │  │ :5432        │  │ :4222        │           │    │
│   │   │ 16 modules   │  │ hub-spoke    │  │ 65 tables    │  │ leaf → hub   │           │    │
│   │   └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘           │    │
│   │                                                                                     │    │
│   │   ┌──────────────┐  ┌──────────────┐                                               │    │
│   │   │    Redis     │  │Bridge Connector │  ← optional in cloud (if NeuraNAC_ENABLED=true     │    │
│   │   │    :6379     │  │ :8090 (opt.) │    for bidirectional legacy sync)                 │    │
│   │   └──────────────┘  └──────────────┘                                               │    │
│   │                                                                                     │    │
│   └─────────────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                              │
│                            CLOUD / PUBLIC CLOUD                                              │
└──────────────────────────────────────────────────────────────────────────────────────────────┘

                                ┌──────────────────────┐
                                │     OBSERVABILITY     │
                                │  ┌────────────────┐   │
                                │  │ Prometheus      │   │
                                │  │ 25 alert rules  │   │
                                │  │ (incl. 5 fed.)  │   │
                                │  └────────────────┘   │
                                │  ┌────────────────┐   │
                                │  │ Grafana         │   │
                                │  │ 17 panels       │   │
                                │  └────────────────┘   │
                                │  ┌────────────────┐   │
                                │  │ SIEM / Syslog   │   │
                                │  │ forwarding      │   │
                                │  └────────────────┘   │
                                └──────────────────────┘
```

---

## 5. Scenario S2 — Cloud Standalone (No NeuraNAC)

**Simplest cloud deployment.** Single site, no federation, no NeuraNAC.

- `DEPLOYMENT_MODE=standalone` | `NeuraNAC_ENABLED=false` | `NEURANAC_SITE_TYPE=cloud`
- 6 services (no Bridge Connector)
- No federation middleware, no peer site

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                              CLOUD ENVIRONMENT                                    │
│                              [site_id: ...000001] [site_type: cloud]              │
│                              DEPLOYMENT_MODE=standalone | NeuraNAC_ENABLED=false        │
│                                                                                   │
│   ┌ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ APPLICATION SERVICES ─ ─ ─ ─ ─ ─ ─ ─ ─ ┐  │
│                                                                                   │
│   │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │  │
│      │ Web Dashboard│  │ API Gateway  │  │ RADIUS Server│  │ Policy Engine│     │
│   │  │ :3001        │  │ :8080        │  │ :1812 (UDP)  │  │ :8082 (HTTP) │  │  │
│      │ React 18     │─►│ 30 routers   │  │ :1813 (Acct) │  │ :9091 (gRPC) │     │
│   │  │ 33 pages     │  │ 10 middleware │  │ :2083 (TLS)  │  │              │  │  │
│      │              │  │ (no Fed. MW) │  │ :49 (TACACS+)│  │              │     │
│   │  └──────────────┘  └──┬───────────┘  │ :3799 (CoA)  │  └──────┬───────┘  │  │
│                            │              └───┬──────┬───┘         │              │
│   │                        │                  │ HTTP │gRPC         │           │  │
│      ┌──────────────┐      │                  │      └─────────────┘              │
│   │  │ AI Engine    │◄─────┘                  │                               │  │
│      │ :8081        │                         │                                  │
│   │  │ 16 modules   │                         │                               │  │
│      └──────────────┘                         │                                  │
│   │                                           │                               │  │
│   └ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┼ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┘  │
│                                               │                                   │
│   ┌ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ INFRASTRUCTURE ─ ─ ─┼─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─┐  │
│                                               │                                   │
│   │  ┌──────────────┐  ┌─────────────────┐    │    ┌──────────────┐           │  │
│      │ Sync Engine  │  │ PostgreSQL      │    │    │    NATS      │              │
│   │  │ :9090 (gRPC) │  │ :5432           │◄───┘    │ :4222        │           │  │
│      │ :9100 (HTTP) │  │ 65 tables       │         │ JetStream    │              │
│   │  │ (no peer)    │  │ V001–V004       │         │ (single node)│           │  │
│      └──────────────┘  └─────────────────┘         └──────────────┘              │
│   │                                                                           │  │
│      ┌──────────────┐                                                            │
│   │  │    Redis     │                                                         │  │
│      │    :6379     │                                                            │
│   │  └──────────────┘                                                         │  │
│                                                                                   │
│   └ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┘  │
│                                                                                   │
│   NOT present: Bridge Connector, Federation Middleware, Peer Site, NeuraNAC Cluster       │
│                                                                                   │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Scenario S3 — On-Prem Standalone (No NeuraNAC)

**Single on-prem site with twin-node HA.** No federation, no NeuraNAC, no cloud.

- `DEPLOYMENT_MODE=standalone` | `NeuraNAC_ENABLED=false` | `NEURANAC_SITE_TYPE=onprem`
- 6 services per node (no Bridge Connector)
- Twin-node HA via Sync Engine intra-site replication

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                              ON-PREM DATA CENTER                                      │
│                              [site_id: ...000001] [site_type: onprem]                 │
│                              DEPLOYMENT_MODE=standalone | NeuraNAC_ENABLED=false            │
│                                                                                       │
│   ┌──────────────────────────── TWIN NODE A (Active) ────────────────────────────┐   │
│   │                                                                               │   │
│   │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │   │
│   │  │ Web Dashboard│  │ API Gateway  │  │ RADIUS Server│  │ Policy Engine│     │   │
│   │  │ :3001        │  │ :8080        │  │ :1812/:1813  │  │ :8082/:9091  │     │   │
│   │  └──────────────┘  └──────────────┘  │ :2083/:49    │  └──────────────┘     │   │
│   │                                      │ :3799        │                        │   │
│   │  ┌──────────────┐  ┌──────────────┐  └──────────────┘  ┌──────────────┐     │   │
│   │  │ AI Engine    │  │ Sync Engine  │                     │ PostgreSQL   │     │   │
│   │  │ :8081        │  │ :9090/:9100  │─────────────────────│ :5432        │     │   │
│   │  └──────────────┘  └──────┬───────┘  gRPC + mTLS       │ 65 tables    │     │   │
│   │                           │                             │ (primary)    │     │   │
│   │  ┌──────────────┐  ┌─────┴────────┐                    └──────────────┘     │   │
│   │  │    Redis     │  │    NATS      │                                          │   │
│   │  │    :6379     │  │ :4222 (hub)  │                                          │   │
│   │  └──────────────┘  └──────────────┘                                          │   │
│   └──────────────────────────────┬────────────────────────────────────────────────┘   │
│                                  │                                                    │
│                     Sync Engine: gRPC + gzip + mTLS                                   │
│                     journal-based replication                                          │
│                     cursor-based resync on reconnect                                  │
│                                  │                                                    │
│   ┌──────────────────────────────┼── TWIN NODE B (Hot Standby) ──────────────────┐   │
│   │                              ▼                                                │   │
│   │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │   │
│   │  │ Web Dashboard│  │ API Gateway  │  │ RADIUS Server│  │ Policy Engine│     │   │
│   │  │ :3001        │  │ :8080        │  │ :1812/:1813  │  │ :8082/:9091  │     │   │
│   │  └──────────────┘  └──────────────┘  │ :2083/:49    │  └──────────────┘     │   │
│   │                                      │ :3799        │                        │   │
│   │  ┌──────────────┐  ┌──────────────┐  └──────────────┘  ┌──────────────┐     │   │
│   │  │ AI Engine    │  │ Sync Engine  │                     │ PostgreSQL   │     │   │
│   │  │ :8081        │  │ :9090/:9100  │                     │ :5432        │     │   │
│   │  └──────────────┘  └──────────────┘                     │ (replica)    │     │   │
│   │                                                         └──────────────┘     │   │
│   │  ┌──────────────┐  ┌──────────────┐                                          │   │
│   │  │    Redis     │  │    NATS      │                                          │   │
│   │  │    :6379     │  │ :4222 (leaf) │                                          │   │
│   │  └──────────────┘  └──────────────┘                                          │   │
│   └──────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                       │
│   NOT present: Bridge Connector, Federation Middleware, Peer Site, NeuraNAC Cluster           │
│   HA: Load balancer in front distributes RADIUS + API traffic across twin nodes       │
│                                                                                       │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 7. Scenario S4 — Hybrid No NeuraNAC

**Two federated NeuraNAC sites without NeuraNAC.** Greenfield deployment, no legacy NAC.

- `DEPLOYMENT_MODE=hybrid` | `NeuraNAC_ENABLED=false`
- Two sites: on-prem + cloud (or two data centers)
- Federation enabled, Bridge Connector NOT deployed

```
┌─────────────────────────────────────────────────────┐
│           ON-PREM SITE                               │
│           [site_id: ...000001]                       │
│           [site_type: onprem]                        │
│                                                      │
│  ┌──────────────┐  ┌──────────────┐                 │
│  │ Web Dashboard│  │ API Gateway  │                 │
│  │ :3001        │  │ :8080        │                 │
│  │ SiteSelector │  │ Federation MW│                 │
│  └──────────────┘  └──────────────┘                 │
│                                                      │
│  ┌──────────────┐  ┌──────────────┐                 │
│  │ RADIUS Server│  │ Policy Engine│                 │
│  │ :1812/:1813  │  │ :8082/:9091  │                 │
│  │ :2083/:49    │  │ site-aware   │                 │
│  │ :3799        │  │ evaluation   │                 │
│  └──────────────┘  └──────────────┘                 │
│                                                      │
│  ┌──────────────┐  ┌──────────────┐                 │
│  │ AI Engine    │  │ Sync Engine  │                 │
│  │ :8081        │  │ :9090/:9100  │                 │
│  │ 16 modules   │  │ hub-spoke    │                 │
│  └──────────────┘  └──────┬───────┘                 │
│                           │                          │
│  ┌──────────┐ ┌──────────┐│ ┌──────────┐            │
│  │PostgreSQL│ │  Redis   ││ │  NATS    │            │
│  │ :5432    │ │  :6379   ││ │  :4222   │            │
│  │ 65 tables│ │          ││ │  :7422   │            │
│  └──────────┘ └──────────┘│ └──────────┘            │
│                           │                          │
│  NO Bridge Connector         │                          │
│  NO NeuraNAC Cluster           │                          │
│                           │                          │
└───────────────────────────┼──────────────────────────┘
                            │
          ┌─────────────────┼─────────────────┐
          │  Federation     │  Sync Engine    │
          │  HMAC-SHA256    │  gRPC+gzip+mTLS │
          │  X-NeuraNAC-Site     │  cursor resync  │
          │  replay prot.   │  NATS leaf→hub  │
          └─────────────────┼─────────────────┘
                            │
┌───────────────────────────┼──────────────────────────┐
│                           ▼                          │
│           CLOUD SITE                                 │
│           [site_id: ...000002]                       │
│           [site_type: cloud]                         │
│                                                      │
│  ┌──────────────┐  ┌──────────────┐                 │
│  │ Web Dashboard│  │ API Gateway  │                 │
│  │ :3001        │  │ :8080        │                 │
│  │ SiteSelector │  │ Federation MW│                 │
│  └──────────────┘  └──────────────┘                 │
│                                                      │
│  ┌──────────────┐  ┌──────────────┐                 │
│  │ RADIUS Server│  │ Policy Engine│                 │
│  │ :1812/:1813  │  │ :8082/:9091  │                 │
│  │ :2083/:49    │  │ site-aware   │                 │
│  │ :3799        │  │ evaluation   │                 │
│  └──────────────┘  └──────────────┘                 │
│                                                      │
│  ┌──────────────┐  ┌──────────────┐                 │
│  │ AI Engine    │  │ Sync Engine  │                 │
│  │ :8081        │  │ :9090/:9100  │                 │
│  │ 16 modules   │  │ hub-spoke    │                 │
│  └──────────────┘  └──────────────┘                 │
│                                                      │
│  ┌──────────┐ ┌──────────┐  ┌──────────┐            │
│  │PostgreSQL│ │  Redis   │  │  NATS    │            │
│  │ :5432    │ │  :6379   │  │  :4222   │            │
│  │ 65 tables│ │          │  │  leaf    │            │
│  └──────────┘ └──────────┘  └──────────┘            │
│                                                      │
│  NO Bridge Connector                                    │
│  NO NeuraNAC Cluster                                      │
│                                                      │
└──────────────────────────────────────────────────────┘
```

---

## 8. Unified Component Legend

```
┌────────────────────────────────────────────────────────────────────────────────┐
│ COMPONENT PRESENCE BY SCENARIO                                                  │
│                                                                                 │
│  Component            │ S1 (NeuraNAC+Hybrid) │ S2 (Cloud) │ S3 (OnPrem) │ S4 (Hyb) │
│ ──────────────────────┼─────────────────┼────────────┼─────────────┼──────────│
│  API Gateway          │ Both sites      │ ✅          │ Twin nodes  │ Both     │
│  RADIUS Server        │ Both sites      │ ✅          │ Twin nodes  │ Both     │
│  Policy Engine        │ Both sites      │ ✅          │ Twin nodes  │ Both     │
│  AI Engine            │ Both sites      │ ✅          │ Twin nodes  │ Both     │
│  Sync Engine          │ Both sites      │ ✅          │ Twin nodes  │ Both     │
│  Bridge Connector        │ On-prem only    │ ❌          │ ❌           │ ❌        │
│  Web Dashboard        │ Both sites      │ ✅          │ Twin nodes  │ Both     │
│  PostgreSQL           │ Both sites      │ ✅          │ Twin (P+R)  │ Both     │
│  Redis                │ Both sites      │ ✅          │ Twin nodes  │ Both     │
│  NATS                 │ Hub + Leaf      │ Single      │ Hub + Leaf  │ Hub+Leaf │
│  Federation Middleware│ Both sites      │ ❌          │ ❌           │ Both     │
│  NeuraNAC Cluster          │ On-prem LAN     │ ❌          │ ❌           │ ❌        │
│  Prometheus + Grafana │ Per site        │ ✅          │ Per node    │ Per site │
└────────────────────────────────────────────────────────────────────────────────┘
```

---

## 9. Data Flow: RADIUS Authentication (End-to-End)

This is the core data flow for every RADIUS request, regardless of deployment scenario.

```
  ┌──────────┐       ┌──────────┐       ┌──────────────────────────────────────────────────┐
  │ Endpoint │       │   NAD    │       │                NeuraNAC SITE                           │
  │ (laptop, │ 802.1X│ (switch, │ RADIUS│                                                  │
  │  phone,  │──────►│  WLC,    │──────►│  ① RADIUS Server (:1812)                        │
  │  IoT)    │       │  AP)     │  :1812│     │                                            │
  └──────────┘       └──────────┘       │     │ Parse RADIUS packet                        │
                                        │     │ Extract: username, MAC, NAS-IP,            │
                                        │     │          EAP type, Calling-Station-Id      │
                                        │     │                                            │
                                        │     ▼                                            │
                                        │  ② Policy Engine (:8082 HTTP / :9091 gRPC)      │
                                        │     │                                            │
                                        │     │ Load tenant rules (from PostgreSQL)        │
                                        │     │ Evaluate conditions (14 operators)         │
                                        │     │ Match rule → auth profile                  │
                                        │     │ Return: VLAN, SGT, dACL, CoA action       │
                                        │     │ Include: site_id, site_type in result      │
                                        │     │                                            │
                                        │     ▼                                            │
                                        │  ③ AI Engine (:8081 HTTP)                       │
                                        │     │                                            │
                                        │     │ a. Profile endpoint (OUI + ML model)       │
                                        │     │ b. Risk score (behavioral + contextual)    │
                                        │     │ c. Anomaly detection (baseline deviation)  │
                                        │     │ d. Drift detection (role/VLAN changes)     │
                                        │     │ e. TLS fingerprint (JA3/JA4 analysis)     │
                                        │     │                                            │
                                        │     ▼                                            │
                                        │  ④ RADIUS Server builds Access-Accept/Reject    │
                                        │     │                                            │
                                        │     │ Encode RADIUS attributes:                  │
                                        │     │   Tunnel-Type + Tunnel-Medium (VLAN)       │
                                        │     │   cisco-av-pair (SGT)                      │
                                        │     │   Filter-Id (dACL)                         │
                                        │     │   Session-Timeout                          │
                                        │     │                                            │
                                        │     ▼                                            │
                                        │  ⑤ PostgreSQL (:5432)                           │
                                        │     │                                            │
                                        │     │ INSERT into: sessions, audit_logs          │
                                        │     │ UPDATE: endpoints (last_seen, profile)     │
                                        │     │                                            │
                                        │     ▼                                            │
                                        │  ⑥ NATS (:4222) — publish events                │
                                        │     │                                            │
                                        │     │ Topics: session.created, coa.requested,    │
                                        │     │         accounting.update                  │
                                        │     │                                            │
                                        │     ▼                                            │
                                        │  ⑦ Redis (:6379)                                │
                                        │     │                                            │
                                        │     │ Cache: session state, rate limit counter,  │
                                        │     │        EAP session state (TTL)             │
                                        │     │                                            │
                                        │     ▼                                            │
                                        │  ⑧ RADIUS Response → NAD                       │
                                        │     │                                            │
                                        └─────┼────────────────────────────────────────────┘
                                              │
                                              ▼
                                        ┌──────────┐
                                        │   NAD    │  Applies enforcement:
                                        │          │  • VLAN assignment
                                        │          │  • SGT tagging
                                        │          │  • dACL (downloadable ACL)
                                        └──────┬───┘
                                               │
                                               ▼ (if risk > threshold)
                                        ┌──────────────┐
                                        │ ⑨ CoA :3799  │  Change of Authorization:
                                        │              │  • Quarantine VLAN
                                        │              │  • Port bounce
                                        │              │  • Reauthenticate
                                        └──────────────┘
```

---

## 10. Data Flow: Policy Evaluation

```
  ┌─────────────────┐         ┌───────────────────────────────────────────────┐
  │  RADIUS Server  │  HTTP   │            POLICY ENGINE                      │
  │  or             │────────►│                                               │
  │  API Gateway    │  gRPC   │  ┌─────────────────────────────────────────┐  │
  └─────────────────┘         │  │ 1. Identify tenant (from request)      │  │
                              │  │ 2. Filter policy_sets for tenant       │  │
                              │  │ 3. For each rule (priority order):     │  │
                              │  │    a. Resolve attributes (dotted path) │  │
                              │  │    b. Apply operator (14 types):       │  │
                              │  │       equals, contains, starts_with,   │  │
                              │  │       ends_with, matches, in, not_in,  │  │
                              │  │       gt, lt, gte, lte, exists,        │  │
                              │  │       not_exists, between              │  │
                              │  │    c. If ALL conditions match → HIT    │  │
                              │  │ 4. Look up authorization_profile       │  │
                              │  │ 5. Build response:                     │  │
                              │  │    {decision, auth, site_id, time_us}  │  │
                              │  └─────────────────────────────────────────┘  │
                              │                                               │
                              │  ┌─────────────────────────────────────────┐  │
                              │  │ NATS subscriber: policy.reload          │  │
                              │  │ → Triggers in-memory rule refresh       │  │
                              │  │   without restart                       │  │
                              │  └─────────────────────────────────────────┘  │
                              │                                               │
                              │  PostgreSQL ──► policy_sets, policy_rules,    │
                              │                authorization_profiles         │
                              └───────────────────────────────────────────────┘
```

---

## 11. Data Flow: AI-Powered Profiling & Risk

```
  ┌─────────────┐                    ┌─────────────────────────────────────────────────────┐
  │ RADIUS      │  POST /profile     │                 AI ENGINE (:8081)                    │
  │ Server      │───────────────────►│                                                     │
  │             │  POST /risk        │  ┌─────────────────────────────────────────────────┐│
  │             │  POST /anomaly     │  │           16 AI MODULES                         ││
  │             │  POST /drift       │  │                                                 ││
  └─────────────┘                    │  │  ┌─────────────┐  ┌─────────────┐               ││
                                     │  │  │ Profiler    │  │ Risk Scorer │               ││
  ┌─────────────┐  POST /chat       │  │  │ OUI + ML    │  │ behavioral  │               ││
  │ API Gateway │───────────────────►│  │  │ model       │  │ + contextual│               ││
  │ (AI proxy)  │  POST /playbook    │  │  └─────────────┘  └─────────────┘               ││
  │             │  POST /nl-to-sql   │  │                                                 ││
  └─────────────┘                    │  │  ┌─────────────┐  ┌─────────────┐               ││
                                     │  │  │ Anomaly     │  │ Shadow AI   │               ││
                                     │  │  │ Detector    │  │ Detector    │               ││
                                     │  │  │ baselines   │  │ JA3/JA4     │               ││
                                     │  │  │ (Redis)     │  │ TLS finger  │               ││
                                     │  │  └─────────────┘  └─────────────┘               ││
                                     │  │                                                 ││
                                     │  │  ┌─────────────┐  ┌─────────────┐               ││
                                     │  │  │ NL-to-SQL   │  │ RAG Trouble │               ││
                                     │  │  │ 18 templates│  │ 12 KB docs  │               ││
                                     │  │  └─────────────┘  └─────────────┘               ││
                                     │  │                                                 ││
                                     │  │  ┌─────────────┐  ┌─────────────┐               ││
                                     │  │  │ Playbooks   │  │ Capacity    │               ││
                                     │  │  │ 6 built-in  │  │ Planner     │               ││
                                     │  │  └─────────────┘  └─────────────┘               ││
                                     │  │                                                 ││
                                     │  │  ┌─────────────┐  ┌─────────────┐               ││
                                     │  │  │ Model       │  │ Adaptive    │               ││
                                     │  │  │ Registry    │  │ Risk        │               ││
                                     │  │  │ A/B testing │  │ feedback    │               ││
                                     │  │  └─────────────┘  └─────────────┘               ││
                                     │  │                                                 ││
                                     │  │  ┌─────────────┐  ┌─────────────┐               ││
                                     │  │  │ Training    │  │ Action      │               ││
                                     │  │  │ Pipeline    │  │ Router      │               ││
                                     │  │  │ ONNX export │  │ 45 intents  │               ││
                                     │  │  └─────────────┘  └─────────────┘               ││
                                     │  │                                                 ││
                                     │  │  ┌─────────────┐  ┌─────────────┐               ││
                                     │  │  │ NLP Policy  │  │ OUI DB      │               ││
                                     │  │  │ translation │  │ ~500 entries│               ││
                                     │  │  └─────────────┘  └─────────────┘               ││
                                     │  └─────────────────────────────────────────────────┘│
                                     │                                                     │
                                     │  Dependencies:                                      │
                                     │    PostgreSQL ← session/endpoint data               │
                                     │    Redis ← anomaly baselines, adaptive thresholds   │
                                     │    LLM (Ollama) ← NLP fallback (optional)           │
                                     └─────────────────────────────────────────────────────┘
```

---

## 12. Data Flow: Cross-Site Federation (S1, S4)

```
 ┌────────────────────────┐                          ┌────────────────────────┐
 │   SITE A (on-prem)     │                          │   SITE B (cloud)       │
 │   site_id: ...000001   │                          │   site_id: ...000002   │
 │                        │                          │                        │
 │  ┌──────────────────┐  │                          │  ┌──────────────────┐  │
 │  │ Web Dashboard    │  │                          │  │ Web Dashboard    │  │
 │  │ SiteSelector:    │  │                          │  │ SiteSelector:    │  │
 │  │ [Local|Peer|All] │  │                          │  │ [Local|Peer|All] │  │
 │  └────────┬─────────┘  │                          │  └────────┬─────────┘  │
 │           │             │                          │           │             │
 │           ▼             │                          │           ▼             │
 │  ┌──────────────────┐  │   X-NeuraNAC-Site: peer       │  ┌──────────────────┐  │
 │  │ API Gateway      │  │   X-NeuraNAC-Timestamp        │  │ API Gateway      │  │
 │  │                  │  │   X-NeuraNAC-Nonce             │  │                  │  │
 │  │ Federation MW:   │──┼──────────────────────────►│  │ Federation MW:   │  │
 │  │  • HMAC-SHA256   │  │   X-NeuraNAC-Signature         │  │  • Verify HMAC   │  │
 │  │  • Replay prot.  │◄─┼──────────────────────────┤│  │  • Check nonce   │  │
 │  │  • Circuit break │  │   (bidirectional)         │  │  • Circuit break │  │
 │  │  • 60s window    │  │                          │  │  • 60s window    │  │
 │  └──────────────────┘  │                          │  └──────────────────┘  │
 │                        │                          │                        │
 │  ┌──────────────────┐  │   gRPC + gzip + mTLS     │  ┌──────────────────┐  │
 │  │ Sync Engine      │──┼─────────────────────────►│  │ Sync Engine      │  │
 │  │                  │◄─┼─────────────────────────┤│  │                  │  │
 │  │ • Journal-based  │  │   cursor-based resync    │  │ • Journal-based  │  │
 │  │ • Hub replicator │  │                          │  │ • Hub replicator │  │
 │  └──────────────────┘  │                          │  └──────────────────┘  │
 │                        │                          │                        │
 │  ┌──────────────────┐  │   NATS leaf → hub        │  ┌──────────────────┐  │
 │  │ NATS (hub)       │──┼─────────────────────────►│  │ NATS (leaf)      │  │
 │  │ :4222, :7422     │  │   :7422                  │  │ :4222            │  │
 │  └──────────────────┘  │                          │  └──────────────────┘  │
 │                        │                          │                        │
 └────────────────────────┘                          └────────────────────────┘

 X-NeuraNAC-Site header values:
   "local"  → Request stays on current site only
   "peer"   → Request forwarded to peer site only
   "all"    → Request executed on both sites, results merged
```

---

## 13. Data Flow: NeuraNAC Coexistence (S1 Only)

```
 ┌──────────────────────────────────────────────────────────────────────────────┐
 │                        ON-PREM PRIVATE NETWORK                               │
 │                                                                              │
 │  ┌──────────────────────────────────────────────────┐                       │
 │  │              NeuraNAC ON-PREM SITE                     │                       │
 │  │                                                   │                       │
 │  │  ┌───────────────┐       ┌───────────────┐       │                       │
 │  │  │ API Gateway   │ HTTP  │ Bridge Connector  │       │                       │
 │  │  │ :8080         │◄─────►│ :8090          │       │                       │
 │  │  │               │  WS   │                │       │                       │
 │  │  │ legacy_nac_enhanced  │ tunnel│ ┌────────────┐ │       │                       │
 │  │  │ router        │       │ │ERS Relay   │ │       │                       │
 │  │  └───────────────┘       │ │            │─┼───────┼──────┐               │
 │  │                          │ └────────────┘ │       │      │               │
 │  │                          │ ┌────────────┐ │       │      │  ERS API      │
 │  │                          │ │Event Stream      │ │       │      │  :9060        │
 │  │                          │ │Bridge      │─┼───────┼──────┤               │
 │  │                          │ └────────────┘ │       │      │  Event Stream       │
 │  │                          │ ┌────────────┐ │       │      │  :8910        │
 │  │                          │ │Registration│ │       │      │               │
 │  │                          │ │+ Heartbeat │ │       │      ▼               │
 │  │                          │ └────────────┘ │       │ ┌──────────────────┐ │
 │  │                          └───────────────┘       │ │  CISCO NeuraNAC       │ │
 │  │                                                   │ │  CLUSTER         │ │
 │  │  Sync operations:                                │ │                  │ │
 │  │    NeuraNAC → NeuraNAC: NADs, Endpoints, SGTs,             │ │  PAN (Admin)     │ │
 │  │               Policies, TrustSec, Certs          │ │  PSN-1 (RADIUS)  │ │
 │  │    NeuraNAC → NeuraNAC: Policy changes, SGT updates        │ │  PSN-2 (RADIUS)  │ │
 │  │    Bidirectional: Conflict resolution            │ │                  │ │
 │  │                                                   │ └──────────────────┘ │
 │  └───────────────────────────────────────────────────┘                       │
 │                                                                              │
 │  Migration path: NeuraNAC → coexistence → NeuraNAC primary → NeuraNAC decommission         │
 │                                                                              │
 │                     ┌──────────────────────────────┐                         │
 │                     │ NAD ASSIGNMENT (coexistence)  │                         │
 │                     │                              │                         │
 │                     │ Floor 1 switches ──► NeuraNAC     │                         │
 │                     │ Floor 2 switches ──► NeuraNAC     │                         │
 │                     │ WLC (Floor 1)    ──► NeuraNAC     │                         │
 │                     │ WLC (Floor 2)    ──► NeuraNAC     │                         │
 │                     │                              │                         │
 │                     │ Migrate one floor at a time  │                         │
 │                     └──────────────────────────────┘                         │
 │                                                                              │
 │            ┌──────────────── Federation ────────────────┐                    │
 │            │ (to cloud site for cross-site visibility)  │                    │
 │            └────────────────────────────────────────────┘                    │
 │                                                                              │
 └──────────────────────────────────────────────────────────────────────────────┘
```

---

## 14. Data Flow: Real-Time Events (NATS + WebSocket)

```
  ┌──────────────┐  publish    ┌──────────────┐  subscribe   ┌──────────────┐
  │ RADIUS Server│────────────►│              │─────────────►│ Sync Engine  │
  │              │  topics:    │              │  topics:      │ (journal     │
  │ Events:      │  session.*  │              │  sync.*       │  entries)    │
  │ • session    │  coa.*      │              │               └──────────────┘
  │   created    │  acct.*     │              │
  │ • session    │             │     NATS     │  subscribe   ┌──────────────┐
  │   terminated │             │   JetStream  │─────────────►│ Policy Engine│
  │ • CoA sent   │             │   (:4222)    │  topics:      │ (reload on   │
  │ • accounting │             │              │  policy.*     │  policy.*)   │
  └──────────────┘             │              │               └──────────────┘
                               │              │
  ┌──────────────┐  publish    │              │  subscribe   ┌──────────────┐
  │ API Gateway  │────────────►│              │─────────────►│ API Gateway  │
  │              │  topics:    │              │               │ WS endpoint  │
  │ Events:      │  event-stream.*   │              │               │              │
  │ • Event Stream     │  config.*   └──────────────┘               │ /api/v1/ws/  │
  │ • config     │                                            │ events       │
  │   changes    │                                            └──────┬───────┘
  └──────────────┘                                                   │
                                                                     │ WebSocket
                                                                     │ push
                                                                     ▼
                                                              ┌──────────────┐
                                                              │ Web Dashboard│
                                                              │ (browser)    │
                                                              │              │
                                                              │ Real-time:   │
                                                              │ • Session    │
                                                              │   updates    │
                                                              │ • Event Stream     │
                                                              │   events     │
                                                              │ • Alerts     │
                                                              └──────────────┘

  In hybrid mode (S1, S4):
  ┌──────────────┐  NATS leaf   ┌──────────────┐  NATS hub   ┌──────────────┐
  │ Site A NATS  │─────────────►│  NATS Cluster │◄────────────│ Site B NATS  │
  │ (hub :7422)  │              │  (3-node)     │             │ (leaf :7422) │
  └──────────────┘              └──────────────┘             └──────────────┘
  Events propagate across sites automatically via leaf node connections.
```

---

## 15. Data Flow: Sync Engine Replication

```
  ┌───────────────────────────────────────────────────────────────────┐
  │                    SYNC ENGINE ARCHITECTURE                       │
  │                                                                   │
  │  ┌─── Within a single site (twin-node HA) ────────────────────┐  │
  │  │                                                             │  │
  │  │  Node A (Active)              Node B (Standby)             │  │
  │  │  ┌──────────────┐             ┌──────────────┐             │  │
  │  │  │ Sync Engine  │   gRPC      │ Sync Engine  │             │  │
  │  │  │              │────────────►│              │             │  │
  │  │  │ Journal:     │   mTLS      │ Apply journal│             │  │
  │  │  │ • INSERT     │   gzip      │ entries to   │             │  │
  │  │  │ • UPDATE     │             │ local PG     │             │  │
  │  │  │ • DELETE     │◄────────────│              │             │  │
  │  │  └──────┬───────┘  bidirectional └──────┬───────┘          │  │
  │  │         │                               │                  │  │
  │  │         ▼                               ▼                  │  │
  │  │  ┌──────────────┐             ┌──────────────┐             │  │
  │  │  │ PostgreSQL   │             │ PostgreSQL   │             │  │
  │  │  │ (primary)    │             │ (replica)    │             │  │
  │  │  │ 65 tables    │             │ 65 tables    │             │  │
  │  │  └──────────────┘             └──────────────┘             │  │
  │  │                                                             │  │
  │  └─────────────────────────────────────────────────────────────┘  │
  │                                                                   │
  │  ┌─── Cross-site (hybrid S1, S4) ─────────────────────────────┐  │
  │  │                                                             │  │
  │  │  Site A                                Site B               │  │
  │  │  ┌──────────────┐                     ┌──────────────┐     │  │
  │  │  │ Sync Engine  │   gRPC + gzip       │ Sync Engine  │     │  │
  │  │  │              │   + mTLS             │              │     │  │
  │  │  │ Hub-Spoke    │ ──────────────────► │ Hub-Spoke    │     │  │
  │  │  │ Replicator   │                     │ Replicator   │     │  │
  │  │  │              │ ◄────────────────── │              │     │  │
  │  │  │ • Spoke      │   bidirectional     │ • Spoke      │     │  │
  │  │  │   discovery  │                     │   discovery  │     │  │
  │  │  │   (neuranac_sites)│                     │   (neuranac_sites)│     │  │
  │  │  │ • Heartbeat  │                     │ • Heartbeat  │     │  │
  │  │  │ • Auto-      │                     │ • Auto-      │     │  │
  │  │  │   reconnect  │                     │   reconnect  │     │  │
  │  │  └──────────────┘                     └──────────────┘     │  │
  │  │                                                             │  │
  │  │  Cursor-based resync:                                       │  │
  │  │  On reconnect after outage, Sync Engine uses keyset         │  │
  │  │  pagination (ResyncCursor) to efficiently catch up           │  │
  │  │  without full table scans. Page size: configurable.         │  │
  │  │                                                             │  │
  │  └─────────────────────────────────────────────────────────────┘  │
  │                                                                   │
  └───────────────────────────────────────────────────────────────────┘
```

---

## 16. Port & Protocol Reference

```
┌──────────────────────────────────────────────────────────────────────────┐
│  SERVICE              PORT    PROTOCOL    DIRECTION    PURPOSE           │
│ ─────────────────────────────────────────────────────────────────────── │
│  API Gateway          8080    HTTP/REST   Inbound      REST API          │
│  API Gateway          8080    WebSocket   Inbound      /ws/events        │
│  RADIUS Server        1812    UDP         Inbound      RADIUS Auth       │
│  RADIUS Server        1813    UDP         Inbound      RADIUS Acct       │
│  RADIUS Server        2083    TCP/TLS     Inbound      RadSec            │
│  RADIUS Server        49      TCP         Inbound      TACACS+           │
│  RADIUS Server        3799    UDP         Outbound     CoA to NADs       │
│  Policy Engine        8082    HTTP        Inbound      REST evaluation   │
│  Policy Engine        9091    gRPC        Inbound      gRPC evaluation   │
│  AI Engine            8081    HTTP        Inbound      AI endpoints      │
│  Sync Engine          9090    gRPC        Both         Replication       │
│  Sync Engine          9100    HTTP        Inbound      Health + trigger  │
│  Bridge Connector        8090    HTTP        Inbound      Health + relay    │
│  Bridge Connector        (WS)    WebSocket   Outbound     Tunnel to cloud   │
│  Bridge Connector        9060    HTTPS       Outbound     Legacy ERS API       │
│  Bridge Connector        8910    STOMP/WS    Outbound     Event Stream        │
│  Web Dashboard        3001    HTTP        Inbound      UI (Vite/Nginx)   │
│  PostgreSQL           5432    TCP         Internal     SQL               │
│  Redis                6379    TCP         Internal     Cache             │
│  NATS                 4222    TCP         Internal     Client connect    │
│  NATS                 7422    TCP         Cross-site   Leaf node         │
│  NATS                 8222    HTTP        Internal     Monitoring        │
│  Prometheus           9092    HTTP        Internal     Metrics scrape    │
│  Grafana              3000    HTTP        Inbound      Dashboards        │
│                                                                          │
│  Federation (S1/S4):  8080    HTTPS       Cross-site   HMAC signed API   │
│  Sync replication:    9090    gRPC/mTLS   Cross-site   Journal sync      │
│  NATS leaf:           7422    TCP/TLS     Cross-site   Event propagation │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 17. Environment Variables by Scenario

```
┌───────────────────────────────┬──────────┬──────────┬──────────┬──────────┐
│ Variable                      │ S1 (NeuraNAC+ │ S2 (Cloud│ S3 (On-  │ S4 (Hyb  │
│                               │  Hybrid) │  Alone)  │  Prem)   │  No NeuraNAC) │
├───────────────────────────────┼──────────┼──────────┼──────────┼──────────┤
│ DEPLOYMENT_MODE               │ hybrid   │standalone│standalone│ hybrid   │
│ NeuraNAC_ENABLED                   │ true     │ false    │ false    │ false    │
│ NEURANAC_SITE_TYPE                 │ onprem * │ cloud    │ onprem   │ onprem * │
│ NEURANAC_SITE_ID                   │ uuid     │ uuid     │ uuid     │ uuid     │
│ NEURANAC_PEER_API_URL              │ https:// │ (empty)  │ (empty)  │ https:// │
│ FEDERATION_SHARED_SECRET      │ ≥32 chars│ (empty)  │ (empty)  │ ≥32 chars│
│ NeuraNAC_CONNECTOR_URL             │ :8090    │ (empty)  │ (empty)  │ (empty)  │
│ NATS_URL                      │ nats://  │ nats://  │ nats://  │ nats://  │
│ POSTGRES_HOST                 │ postgres │ postgres │ postgres │ postgres │
│ REDIS_HOST                    │ redis    │ redis    │ redis    │ redis    │
│ SYNC_PEER_ADDRESS             │ peer:9090│ (empty)  │twin:9090 │ peer:9090│
├───────────────────────────────┴──────────┴──────────┴──────────┴──────────┤
│ * S1 and S4 have TWO sites — each site has its own NEURANAC_SITE_TYPE value.   │
│   On-prem site = "onprem", Cloud site = "cloud".                          │
│                                                                           │
│ Helm overlays:                                                            │
│   S1: values-onprem-hybrid.yaml + values-cloud-hybrid.yaml               │
│   S2: values-cloud-standalone.yaml                                        │
│   S3: values-onprem-standalone.yaml                                       │
│   S4: values-hybrid-no-lnac-onprem.yaml + values-hybrid-no-lnac-cloud.yaml │
└───────────────────────────────────────────────────────────────────────────┘
```

---

*Document generated as part of NeuraNAC v1.0.0 GA release. See also: [DEPLOYMENT.md](DEPLOYMENT.md) for commands, [ARCHITECTURE.md](ARCHITECTURE.md) for system design, [README.md](../README.md) for quick start.*
