# NeuraNAC Capacity Planning Guide

## 1. Reference Architecture Sizing

### Small Deployment (up to 5,000 endpoints)
| Component     | Replicas    | CPU      | Memory | Storage   |
| ------------- | ----------- | -------- | ------ | --------- |
| RADIUS Server | 2           | 2 cores  | 2 GB   | -         |
| API Gateway   | 2           | 1 core   | 1 GB   | -         |
| Policy Engine | 2           | 1 core   | 1 GB   | -         |
| AI Engine     | 1           | 2 cores  | 4 GB   | -         |
| Sync Engine   | 1           | 0.5 core | 512 MB | -         |
| PostgreSQL    | 1 (primary) | 2 cores  | 4 GB   | 50 GB SSD |
| Redis         | 1           | 1 core   | 2 GB   | -         |
| NATS          | 1           | 0.5 core | 512 MB | 10 GB     |

### Medium Deployment (5,000–50,000 endpoints)
| Component      | Replicas                   | CPU     | Memory | Storage    |
| -------------- | -------------------------- | ------- | ------ | ---------- |
| RADIUS Server  | 3–4                        | 4 cores | 4 GB   | -          |
| API Gateway    | 3                          | 2 cores | 2 GB   | -          |
| Policy Engine  | 3                          | 2 cores | 2 GB   | -          |
| AI Engine      | 2                          | 4 cores | 8 GB   | -          |
| Sync Engine    | 2 (HA pair)                | 1 core  | 1 GB   | -          |
| PostgreSQL     | 1 primary + 1 replica      | 4 cores | 16 GB  | 200 GB SSD |
| Redis Sentinel | 3 (1 primary + 2 replicas) | 2 cores | 4 GB   | -          |
| NATS Cluster   | 3                          | 1 core  | 1 GB   | 50 GB      |

### Large Deployment (50,000+ endpoints)
| Component     | Replicas                   | CPU     | Memory | Storage         |
| ------------- | -------------------------- | ------- | ------ | --------------- |
| RADIUS Server | 6–8                        | 8 cores | 8 GB   | -               |
| API Gateway   | 4–6                        | 4 cores | 4 GB   | -               |
| Policy Engine | 4                          | 4 cores | 4 GB   | -               |
| AI Engine     | 3–4                        | 8 cores | 16 GB  | 100 GB (models) |
| Sync Engine   | 2 (HA pair)                | 2 cores | 2 GB   | -               |
| PostgreSQL    | 1 primary + 2 replicas     | 8 cores | 32 GB  | 500 GB SSD      |
| Redis Cluster | 6 (3 primary + 3 replicas) | 4 cores | 8 GB   | -               |
| NATS Cluster  | 5                          | 2 cores | 2 GB   | 100 GB          |

## 2. Throughput Estimates

### RADIUS Authentication
| Metric                               | Expected | Maximum Tested |
| ------------------------------------ | -------- | -------------- |
| PAP/CHAP auth/sec (per replica)      | 2,000    | 5,000          |
| EAP-TLS auth/sec (per replica)       | 500      | 1,200          |
| PEAP/EAP-TTLS auth/sec (per replica) | 800      | 2,000          |
| MAB auth/sec (per replica)           | 3,000    | 8,000          |
| Accounting req/sec (per replica)     | 5,000    | 10,000         |

### API Gateway
| Metric                              | Expected | Maximum |
| ----------------------------------- | -------- | ------- |
| REST API req/sec (per replica)      | 500      | 2,000   |
| WebSocket connections (per replica) | 200      | 1,000   |
| Concurrent admin sessions           | 50       | 500     |

### Policy Engine
| Metric                               | Expected        | Maximum          |
| ------------------------------------ | --------------- | ---------------- |
| Policy evaluations/sec (per replica) | 3,000           | 10,000           |
| Max policies in memory               | 10,000          | 100,000          |
| Policy reload time (full)            | < 1s (1K rules) | ~5s (100K rules) |

## 3. Database Sizing

### PostgreSQL Storage Growth
| Table         | Row Size (avg) | Growth Rate       | 1-Year Estimate |
| ------------- | -------------- | ----------------- | --------------- |
| auth_sessions | 500 bytes      | 10K/hour (medium) | ~44 GB          |
| audit_log     | 300 bytes      | 1K/hour           | ~2.6 GB         |
| endpoints     | 400 bytes      | Slow (discovery)  | < 1 GB          |
| event-stream_events | 200 bytes      | 5K/hour           | ~8.8 GB         |

**Recommendation:** Enable `pg_partman` for auth_sessions and audit_log tables with monthly partitions and 6-month retention.

### Redis Memory Usage
| Data Type             | Memory per Item | Typical Count | Total  |
| --------------------- | --------------- | ------------- | ------ |
| Rate limit keys       | 100 bytes       | 10K           | 1 MB   |
| EAP sessions (active) | 500 bytes       | 1K            | 500 KB |
| JWT blocklist         | 200 bytes       | 5K            | 1 MB   |
| API key cache         | 300 bytes       | 500           | 150 KB |

**Total Redis memory (medium deployment):** ~50 MB active + overhead → allocate 2 GB minimum.

## 4. Network Bandwidth

| Traffic Type         | Per Replica | Notes                          |
| -------------------- | ----------- | ------------------------------ |
| RADIUS UDP           | 1–5 Mbps    | Auth + Accounting              |
| RadSec TLS           | 2–10 Mbps   | TLS overhead ~2x               |
| gRPC (RADIUS↔Policy) | 5–20 Mbps   | Internal, low latency required |
| NATS messaging       | 1–5 Mbps    | Event streaming                |
| API HTTP             | 5–20 Mbps   | REST + WebSocket               |
| DB connections       | 10–50 Mbps  | Depends on query patterns      |

## 5. Scaling Triggers

| Metric                          | Threshold | Action                                  |
| ------------------------------- | --------- | --------------------------------------- |
| RADIUS CPU > 70% sustained      | 5 min     | Scale out RADIUS replicas               |
| API Gateway CPU > 70%           | 5 min     | Scale out API Gateway                   |
| Policy eval latency p95 > 100ms | 5 min     | Scale out Policy Engine                 |
| DB connection pool > 80%        | 5 min     | Increase pool size or add read replica  |
| Redis memory > 70%              | -         | Increase memory or add replicas         |
| EAP sessions > 1000/replica     | -         | Verify Redis-backed EAP store is active |

## 6. Load Testing Commands

```bash
# Smoke test (5 VUs, 10 seconds)
k6 run --vus 5 --duration 10s tests/load/k6_api_gateway.js

# Medium load (50 VUs, 5 minutes)
k6 run --vus 50 --duration 5m tests/load/k6_api_gateway.js

# Sustained load (200 VUs, 30 minutes)
k6 run --vus 200 --duration 30m tests/load/k6_api_gateway.js

# Stress test (ramp up to 500 VUs)
k6 run --vus 500 --duration 10m tests/load/k6_api_gateway.js
```
