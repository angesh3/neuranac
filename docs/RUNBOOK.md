# NeuraNAC Operations Runbook & Troubleshooting Guide

> **Audience:** NOC Engineers, SREs, Network Admins, Support Engineers
> **Last Updated:** February 2026

---

## Table of Contents

**Part 1 — Operational Runbooks**
1. [Daily Health Check](#1-daily-health-check)
2. [Service Startup & Shutdown](#2-service-startup--shutdown)
3. [Backup & Restore](#3-backup--restore)
4. [Scaling & Capacity](#4-scaling--capacity)
5. [Certificate Lifecycle](#5-certificate-lifecycle)
6. [User & Access Management](#6-user--access-management)
7. [Log Management](#7-log-management)
8. [Database Maintenance](#8-database-maintenance)
9. [Upgrading NeuraNAC](#9-upgrading-neuranac)
10. [Legacy NAC Integration Operations](#10-legacy-nac-integration-operations)

**Part 2 — Troubleshooting Guide**
11. [Troubleshooting Methodology](#11-troubleshooting-methodology)
12. [RADIUS Authentication Failures](#12-radius-authentication-failures)
13. [API Gateway Issues](#13-api-gateway-issues)
14. [Policy Engine Issues](#14-policy-engine-issues)
15. [AI Engine Issues](#15-ai-engine-issues)
16. [Sync Engine Issues](#16-sync-engine-issues)
17. [Database Issues](#17-database-issues)
18. [Redis / Cache Issues](#18-redis--cache-issues)
19. [NATS / Event Bus Issues](#19-nats--event-bus-issues)
20. [Web Dashboard Issues](#20-web-dashboard-issues)
21. [Legacy NAC Integration Troubleshooting](#21-legacy-nac-integration-troubleshooting)
22. [Performance Troubleshooting](#22-performance-troubleshooting)
23. [Security Incident Response](#23-security-incident-response)

**Appendices**
- [A. Service Port Reference](#appendix-a-service-port-reference)
- [B. Log Locations & Formats](#appendix-b-log-locations--formats)
- [C. Common Error Codes](#appendix-c-common-error-codes)
- [D. Useful SQL Queries](#appendix-d-useful-sql-queries)
- [E. Emergency Contacts & Escalation](#appendix-e-emergency-contacts--escalation)

---

# Part 1 — Operational Runbooks

## 1. Daily Health Check

**Frequency:** Every morning or via automated monitoring

### 1.1 Quick Health Check Script

```bash
#!/bin/bash
# save as: scripts/healthcheck.sh

echo "=== NeuraNAC Daily Health Check ==="
echo ""

# Core services
echo "--- Core Services ---"
for svc in "API Gateway:8080" "Policy Engine:8082" "AI Engine:8081" "Sync Engine:9100"; do
  name="${svc%%:*}"
  port="${svc##*:}"
  status=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:$port/health 2>/dev/null)
  if [ "$status" = "200" ]; then
    echo "  ✅ $name (:$port) — UP"
  else
    echo "  ❌ $name (:$port) — DOWN (HTTP $status)"
  fi
done

# Infrastructure
echo ""
echo "--- Infrastructure ---"
pg_status=$(docker exec neuranac-postgres pg_isready -U neuranac 2>/dev/null && echo "UP" || echo "DOWN")
echo "  PostgreSQL: $pg_status"

redis_status=$(docker exec neuranac-redis redis-cli -a neuranac_dev_password ping 2>/dev/null | grep -q PONG && echo "UP" || echo "DOWN")
echo "  Redis: $redis_status"

nats_status=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8222/healthz 2>/dev/null)
echo "  NATS: $([ "$nats_status" = "200" ] && echo 'UP' || echo 'DOWN')"

# RADIUS
echo ""
echo "--- RADIUS ---"
echo "  Auth port 1812: $(nc -zu localhost 1812 2>/dev/null && echo 'OPEN' || echo 'CLOSED')"
echo "  Acct port 1813: $(nc -zu localhost 1813 2>/dev/null && echo 'OPEN' || echo 'CLOSED')"

# Dashboard
echo ""
echo "--- Dashboard ---"
dash_status=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3001 2>/dev/null)
echo "  Web Dashboard: $([ "$dash_status" = "200" ] && echo 'UP' || echo 'DOWN')"

# Database counts
echo ""
echo "--- Key Metrics ---"
docker exec neuranac-postgres psql -U neuranac -t -c "
  SELECT 'Active Sessions: ' || count(*) FROM sessions WHERE is_active
  UNION ALL
  SELECT 'Registered NADs: ' || count(*) FROM network_devices
  UNION ALL
  SELECT 'Known Endpoints: ' || count(*) FROM endpoints
  UNION ALL
  SELECT 'Audit Entries (24h): ' || count(*) FROM audit_logs WHERE created_at > NOW() - INTERVAL '24 hours'
" 2>/dev/null

echo ""
echo "=== Health Check Complete ==="
```

### 1.2 Prometheus Alerts to Monitor

| Alert                    | Condition                                    | Severity |
| ------------------------ | -------------------------------------------- | -------- |
| `NeuraNACServiceDown`         | Any health endpoint returns non-200 for >30s | Critical |
| `RADIUSAuthFailRate`     | Auth failure rate >20% in 5 min window       | Warning  |
| `DatabaseConnectionPool` | Pool utilization >80%                        | Warning  |
| `DiskSpaceLow`           | Disk usage >85%                              | Warning  |
| `CertExpiringSoon`       | Certificate expiry <30 days                  | Warning  |
| `SyncLag`                | Twin-node sync lag >60s                      | Warning  |
| `NeuraNACSyncFailed`          | legacy sync status = 'failed'                   | Warning  |

### 1.3 Grafana Dashboards

Access at `http://localhost:3000` (default: admin/admin)

| Dashboard      | What to Check                                                     |
| -------------- | ----------------------------------------------------------------- |
| NeuraNAC Overview   | Service health, request rates, error rates                        |
| RADIUS Metrics | Auth/acct requests per second, latency percentiles                |
| Database       | Connection pool, query latency, table sizes                       |
| AI Engine      | Profiling accuracy, risk score distribution, shadow AI detections |

---

## 2. Service Startup & Shutdown

### 2.1 Full Platform Start (Docker Compose)

```bash
cd deploy

# Start all services (infrastructure first, then apps)
docker compose up -d

# Watch startup logs
docker compose logs -f --tail=50

# Verify all 9 containers are running
docker compose ps
```

**Expected startup order (docker-compose healthchecks enforce this):**
1. PostgreSQL, Redis, NATS (infrastructure)
2. API Gateway, Policy Engine, AI Engine (control plane)
3. RADIUS Server (data plane — waits for API Gateway)
4. Sync Engine (waits for nothing, connects to peer async)
5. Web Dashboard (waits for API Gateway)

### 2.2 Graceful Shutdown

```bash
cd deploy

# Graceful stop (sends SIGTERM, 30s grace period)
docker compose stop

# Or full teardown (stops + removes containers, keeps volumes)
docker compose down

# Nuclear option: remove everything including data volumes
docker compose down -v   # ⚠️ DESTROYS ALL DATA
```

### 2.3 Restart a Single Service

```bash
# Restart just the RADIUS server
docker compose restart radius-server

# Restart with fresh container (rebuild if code changed)
docker compose up -d --build radius-server

# Restart API Gateway (will briefly interrupt API calls)
docker compose restart api-gateway
```

### 2.4 Kubernetes Start/Stop

```bash
# Scale down (stop serving traffic)
kubectl scale deployment neuranac-radius --replicas=0 -n neuranac
kubectl scale deployment neuranac-api --replicas=0 -n neuranac

# Scale back up
kubectl scale deployment neuranac-radius --replicas=2 -n neuranac
kubectl scale deployment neuranac-api --replicas=2 -n neuranac

# Rolling restart (zero-downtime)
kubectl rollout restart deployment/neuranac-api -n neuranac
```

---

## 3. Backup & Restore

### 3.1 Database Backup

```bash
# Full backup (compressed)
docker exec neuranac-postgres pg_dump -U neuranac -Fc neuranac > backup_$(date +%Y%m%d_%H%M%S).dump

# Schema-only backup
docker exec neuranac-postgres pg_dump -U neuranac --schema-only neuranac > schema_backup.sql

# Specific tables only (e.g., just policies and NADs)
docker exec neuranac-postgres pg_dump -U neuranac -t policies -t network_devices neuranac > policies_nads.sql
```

### 3.2 Database Restore

```bash
# Restore from compressed dump (drops and recreates)
docker exec -i neuranac-postgres pg_restore -U neuranac -d neuranac --clean --if-exists < backup_20260220_120000.dump

# Restore from SQL dump
docker exec -i neuranac-postgres psql -U neuranac -d neuranac < schema_backup.sql
```

### 3.3 Redis Backup

```bash
# Trigger RDB snapshot
docker exec neuranac-redis redis-cli -a neuranac_dev_password BGSAVE

# Copy the dump file
docker cp neuranac-redis:/data/dump.rdb ./redis_backup_$(date +%Y%m%d).rdb
```

### 3.4 Configuration Backup

```bash
# Backup all config files
tar czf neuranac_config_$(date +%Y%m%d).tar.gz \
  deploy/docker-compose.yml \
  deploy/.env \
  deploy/monitoring/ \
  deploy/helm/
```

### 3.5 Automated Backup Schedule

```bash
# Add to crontab: daily DB backup at 2 AM, retain 30 days
0 2 * * * docker exec neuranac-postgres pg_dump -U neuranac -Fc neuranac > /backups/neuranac_$(date +\%Y\%m\%d).dump
0 3 * * * find /backups -name "neuranac_*.dump" -mtime +30 -delete
```

---

## 4. Scaling & Capacity

### 4.1 Capacity Guidelines

| Component     | Small (<500 NADs) | Medium (500-5K NADs) | Large (5K+ NADs)             |
| ------------- | ----------------- | -------------------- | ---------------------------- |
| RADIUS Server | 1 instance        | 2 instances (HA)     | 2+ instances + load balancer |
| API Gateway   | 1 instance        | 2 instances          | 3+ instances                 |
| Policy Engine | 1 instance        | 1 instance           | 2 instances                  |
| AI Engine     | 1 instance        | 1 instance           | 2 instances                  |
| PostgreSQL    | 1 node            | 1 node (SSD)         | Primary + read replica       |
| Redis         | 1 node            | 1 node               | Redis Sentinel (3 nodes)     |

### 4.2 Kubernetes Horizontal Scaling

```bash
# Scale API Gateway
kubectl scale deployment neuranac-api --replicas=3 -n neuranac

# Set up HPA (auto-scale based on CPU)
kubectl autoscale deployment neuranac-api --min=2 --max=5 --cpu-percent=70 -n neuranac
kubectl autoscale deployment neuranac-radius --min=2 --max=4 --cpu-percent=60 -n neuranac
```

### 4.3 Performance Tuning

```bash
# PostgreSQL: Increase connection pool
# In .env or Helm values:
POSTGRES_MAX_CONNECTIONS=200
SQLALCHEMY_POOL_SIZE=20
SQLALCHEMY_MAX_OVERFLOW=30

# Redis: Increase max memory
docker exec neuranac-redis redis-cli -a neuranac_dev_password CONFIG SET maxmemory 512mb
docker exec neuranac-redis redis-cli -a neuranac_dev_password CONFIG SET maxmemory-policy allkeys-lru

# RADIUS: Increase worker threads
# In radius-server config:
RADIUS_WORKERS=8
RADIUS_MAX_REQUESTS_PER_SECOND=5000
```

---

## 5. Certificate Lifecycle

### 5.1 Check Certificate Expiry

```bash
# Via API: certificates expiring within 30 days
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8080/api/v1/certificates?expiring_within_days=30"

# Via DB: direct query
docker exec neuranac-postgres psql -U neuranac -c "
  SELECT common_name, issuer, not_after,
    EXTRACT(DAY FROM not_after - NOW()) AS days_remaining
  FROM certificates
  WHERE not_after < NOW() + INTERVAL '30 days'
  ORDER BY not_after ASC"
```

### 5.2 Renew/Generate Certificate

```bash
# Generate new server certificate
curl -X POST http://localhost:8080/api/v1/certificates/generate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "common_name": "neuranac-server",
    "key_type": "RSA",
    "key_size": 2048,
    "validity_days": 365,
    "usage": "server"
  }'

# Generate client certificate (for RadSec or Event Stream)
curl -X POST http://localhost:8080/api/v1/certificates/generate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "common_name": "neuranac-event-stream-client",
    "key_type": "RSA",
    "key_size": 2048,
    "validity_days": 730,
    "usage": "client"
  }'
```

### 5.3 RadSec Certificate Rotation

1. Generate new RadSec server certificate (see above)
2. Update RadSec configuration with new cert paths
3. Restart RADIUS server: `docker compose restart radius-server`
4. Verify RadSec clients can connect on port 2083
5. Delete old certificate after 48h grace period

---

## 6. User & Access Management

### 6.1 Reset Admin Password

```bash
# Via API (requires current valid token)
curl -X PUT http://localhost:8080/api/v1/admin/users/{user_id} \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"password": "new-secure-password"}'

# Emergency: Direct DB reset (bcrypt hash)
docker exec neuranac-postgres psql -U neuranac -c "
  UPDATE admin_users SET password_hash = '\$2b\$12\$LJ3m5ZQxNQxKBH4DvGJE...' 
  WHERE username = 'admin'"
# Then generate a proper bcrypt hash using:
# python3 -c "import bcrypt; print(bcrypt.hashpw(b'newpassword', bcrypt.gensalt()).decode())"
```

### 6.2 Lock/Unlock User Account

```bash
# Lock (disable) an admin user
docker exec neuranac-postgres psql -U neuranac -c "
  UPDATE admin_users SET is_active = FALSE WHERE username = 'jsmith'"

# Unlock
docker exec neuranac-postgres psql -U neuranac -c "
  UPDATE admin_users SET is_active = TRUE WHERE username = 'jsmith'"
```

### 6.3 API Token Management

```bash
# Login to get JWT token
TOKEN=$(curl -s -X POST http://localhost:8080/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"your-password"}' | jq -r '.access_token')

echo $TOKEN

# Verify token is valid
curl -H "Authorization: Bearer $TOKEN" http://localhost:8080/api/v1/auth/me
```

---

## 7. Log Management

### 7.1 View Service Logs

```bash
# Real-time logs (all services)
docker compose logs -f

# Specific service, last 100 lines
docker compose logs --tail=100 radius-server
docker compose logs --tail=100 api-gateway

# Filter by severity
docker compose logs api-gateway 2>&1 | grep -i "error\|critical\|warning"

# RADIUS auth events only
docker compose logs radius-server 2>&1 | grep "Access-"
```

### 7.2 Audit Log Queries

```bash
# Recent admin actions
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8080/api/v1/audit/?limit=50"

# Filter by action type
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8080/api/v1/audit/?action=login&limit=20"

# Direct DB query for audit investigation
docker exec neuranac-postgres psql -U neuranac -c "
  SELECT created_at, username, action, resource_type, ip_address, details
  FROM audit_logs
  WHERE created_at > NOW() - INTERVAL '24 hours'
  ORDER BY created_at DESC
  LIMIT 50"
```

### 7.3 Log Rotation (Docker)

```json
// Add to /etc/docker/daemon.json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "50m",
    "max-file": "5"
  }
}
```

### 7.4 Forward Logs to SIEM

```bash
# Configure SIEM forwarding
curl -X POST http://localhost:8080/api/v1/siem/config \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "protocol": "syslog",
    "format": "cef",
    "host": "siem.example.com",
    "port": 514,
    "facility": "local0",
    "enabled": true
  }'
```

---

## 8. Database Maintenance

### 8.1 Routine Maintenance

```bash
# Check database size
docker exec neuranac-postgres psql -U neuranac -c "
  SELECT pg_size_pretty(pg_database_size('neuranac')) AS db_size"

# Table sizes (top 15)
docker exec neuranac-postgres psql -U neuranac -c "
  SELECT relname AS table_name,
    pg_size_pretty(pg_total_relation_size(relid)) AS total_size,
    n_live_tup AS row_count
  FROM pg_catalog.pg_statio_user_tables
  JOIN pg_stat_user_tables USING (relid)
  ORDER BY pg_total_relation_size(relid) DESC
  LIMIT 15"

# Vacuum and analyze (run weekly)
docker exec neuranac-postgres psql -U neuranac -c "VACUUM ANALYZE"

# Check for bloated tables
docker exec neuranac-postgres psql -U neuranac -c "
  SELECT relname,
    n_dead_tup,
    n_live_tup,
    ROUND(n_dead_tup::numeric / GREATEST(n_live_tup, 1) * 100, 1) AS dead_pct
  FROM pg_stat_user_tables
  WHERE n_dead_tup > 1000
  ORDER BY n_dead_tup DESC"
```

### 8.2 Data Retention / Purge

```bash
# Purge sessions older than 90 days
docker exec neuranac-postgres psql -U neuranac -c "
  DELETE FROM sessions WHERE ended_at < NOW() - INTERVAL '90 days'"

# Purge audit logs older than 1 year
docker exec neuranac-postgres psql -U neuranac -c "
  DELETE FROM audit_logs WHERE created_at < NOW() - INTERVAL '365 days'"

# Purge legacy sync logs older than 60 days
docker exec neuranac-postgres psql -U neuranac -c "
  DELETE FROM legacy_nac_sync_log WHERE started_at < NOW() - INTERVAL '60 days'"

# Purge RADIUS accounting older than 180 days
docker exec neuranac-postgres psql -U neuranac -c "
  DELETE FROM accounting WHERE created_at < NOW() - INTERVAL '180 days'"
```

### 8.3 Connection Pool Check

```bash
# Check active DB connections
docker exec neuranac-postgres psql -U neuranac -c "
  SELECT state, count(*)
  FROM pg_stat_activity
  WHERE datname = 'neuranac'
  GROUP BY state"

# Kill idle connections older than 10 minutes
docker exec neuranac-postgres psql -U neuranac -c "
  SELECT pg_terminate_backend(pid)
  FROM pg_stat_activity
  WHERE datname = 'neuranac'
    AND state = 'idle'
    AND state_change < NOW() - INTERVAL '10 minutes'"
```

---

## 9. Upgrading NeuraNAC

### 9.1 Pre-Upgrade Checklist

- [ ] Take database backup (`pg_dump`)
- [ ] Take Redis backup (`BGSAVE`)
- [ ] Note current version from health endpoints
- [ ] Verify backup can be restored (test on staging)
- [ ] Schedule maintenance window
- [ ] Notify users of expected downtime
- [ ] Review release notes for breaking changes

### 9.2 Docker Compose Upgrade

```bash
# 1. Pull latest images / rebuild
cd deploy
docker compose build --no-cache

# 2. Stop services
docker compose stop

# 3. Run database migrations (if any)
docker exec neuranac-postgres psql -U neuranac -f /migrations/V002_upgrade.sql

# 4. Start with new version
docker compose up -d

# 5. Verify health
./scripts/healthcheck.sh

# 6. Check version
curl http://localhost:8080/health | jq '.version'
```

### 9.3 Kubernetes Rolling Upgrade

```bash
# 1. Update Helm values with new image tag
helm upgrade neuranac helm/neuranac \
  --set global.image.tag=v1.2.0 \
  -n neuranac

# 2. Watch rollout
kubectl rollout status deployment/neuranac-api -n neuranac
kubectl rollout status deployment/neuranac-radius -n neuranac

# 3. Rollback if needed
kubectl rollout undo deployment/neuranac-api -n neuranac
```

### 9.4 Post-Upgrade Verification

```bash
# 1. Health check all services
./scripts/healthcheck.sh

# 2. Test RADIUS auth
radtest testuser testing123 localhost 0 testing123

# 3. Test API login
curl -X POST http://localhost:8080/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin-password"}'

# 4. Verify dashboard loads
curl -s -o /dev/null -w "%{http_code}" http://localhost:3001

# 5. Check sync engine peer connection
curl http://localhost:9100/sync/status
```

---

## 10. Legacy NAC Integration Operations

### 10.1 Add New Legacy Connection

```bash
TOKEN="<your-jwt-token>"

# Create connection
curl -X POST http://localhost:8080/api/v1/legacy-nac/connections \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "NeuraNAC Primary PAN",
    "hostname": "legacy-nac.example.com",
    "port": 443,
    "username": "ers-admin",
    "password": "ers-password",
    "ers_enabled": true,
    "ers_port": 9060,
    "event_stream_enabled": false,
    "verify_ssl": true,
    "deployment_mode": "coexistence"
  }'

# Test connectivity
curl -X POST http://localhost:8080/api/v1/legacy-nac/connections/{id}/test \
  -H "Authorization: Bearer $TOKEN"
```

### 10.2 Run Legacy Sync

```bash
# Full sync
curl -X POST http://localhost:8080/api/v1/legacy-nac/connections/{id}/sync \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"entity_types": ["all"], "sync_type": "full"}'

# Sync specific entity types only
curl -X POST http://localhost:8080/api/v1/legacy-nac/connections/{id}/sync \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"entity_types": ["network_device", "endpoint"], "sync_type": "incremental"}'

# Check sync status
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8080/api/v1/legacy-nac/connections/{id}/sync-status

# View sync log
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8080/api/v1/legacy-nac/connections/{id}/sync-log
```

### 10.3 Migration Operations

```bash
# Start migration
curl -X POST http://localhost:8080/api/v1/legacy-nac/connections/{id}/migration \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"action": "start_migration"}'

# Check migration progress
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8080/api/v1/legacy-nac/connections/{id}/migration-status

# Complete migration (set NeuraNAC to readonly)
curl -X POST http://localhost:8080/api/v1/legacy-nac/connections/{id}/migration \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"action": "complete_migration"}'

# Emergency rollback
curl -X POST http://localhost:8080/api/v1/legacy-nac/connections/{id}/migration \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"action": "rollback"}'
```

---

# Part 2 — Troubleshooting Guide

## 11. Troubleshooting Methodology

### General Approach

```
1. IDENTIFY    → What exactly is broken? (symptom)
2. SCOPE       → How many users/NADs affected? (blast radius)
3. TIMELINE    → When did it start? What changed? (recent change?)
4. ISOLATE     → Which component is at fault? (use health checks)
5. DIAGNOSE    → Read logs, check DB, trace the flow
6. FIX         → Apply minimal fix, verify
7. DOCUMENT    → Record root cause and resolution
```

### Quick Triage Decision Tree

```
Service not responding?
├── Check Docker: docker compose ps
│   ├── Container not running → docker compose logs <service>
│   └── Container running but unhealthy → check health endpoint
│
├── Check dependencies:
│   ├── DB down? → docker exec neuranac-postgres pg_isready -U neuranac
│   ├── Redis down? → docker exec neuranac-redis redis-cli ping
│   └── NATS down? → curl http://localhost:8222/healthz
│
└── Check resources:
    ├── Disk full? → df -h
    ├── Memory exhausted? → docker stats
    └── CPU pegged? → docker stats / top
```

---

## 12. RADIUS Authentication Failures

### Symptom: Users Cannot Authenticate

**Step 1 — Verify RADIUS is running:**
```bash
docker compose ps radius-server
docker compose logs --tail=20 radius-server
```

**Step 2 — Check if NAD is registered:**
```bash
# List registered NADs
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8080/api/v1/network-devices

# Check NAD shared secret matches
docker exec neuranac-postgres psql -U neuranac -c "
  SELECT name, ip_address, created_at
  FROM network_devices
  WHERE ip_address = '<NAD_IP>'"
```

**Step 3 — Test with radtest:**
```bash
# Basic PAP test
radtest testuser testing123 localhost 0 testing123

# Expected: Access-Accept or Access-Reject
# If no response: firewall or RADIUS server down
# If Access-Reject: wrong credentials or policy denial
```

**Step 4 — Check Policy Engine:**
```bash
curl http://localhost:8082/health

# Test policy evaluation directly
curl -X POST http://localhost:8082/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "00000000-0000-0000-0000-000000000000",
    "auth_context": {"username": "testuser", "nas_ip": "10.0.0.1"}
  }'
```

**Step 5 — Check recent auth logs:**
```bash
docker compose logs radius-server 2>&1 | grep -i "access-reject\|error\|fail" | tail -20
```

### Common Root Causes

| Symptom                      | Cause                           | Fix                                    |
| ---------------------------- | ------------------------------- | -------------------------------------- |
| No response from RADIUS      | RADIUS port blocked by firewall | Open UDP 1812/1813                     |
| Access-Reject for valid user | Wrong shared secret on NAD      | Verify NAD shared secret matches NeuraNAC   |
| Access-Reject for valid user | User not in database            | Check `admin_users` or identity source |
| Access-Reject for valid user | Policy denying access           | Check policy rules via API             |
| EAP-TLS failures             | Client certificate not trusted  | Import client CA to NeuraNAC                |
| Timeout on EAP               | Policy Engine slow              | Check PE health and DB latency         |
| `connection refused` from PE | Policy Engine crashed           | `docker compose restart policy-engine` |

---

## 13. API Gateway Issues

### Symptom: API Returns 500 / Not Responding

**Step 1 — Check health:**
```bash
curl -v http://localhost:8080/health
docker compose logs --tail=50 api-gateway
```

**Step 2 — Check DB connection:**
```bash
docker compose logs api-gateway 2>&1 | grep -i "database\|connection\|pool"
```

**Step 3 — Check middleware:**
```bash
# Rate limiting? Check if 429 responses
docker compose logs api-gateway 2>&1 | grep "429\|rate.limit"

# Auth middleware? Check JWT
docker compose logs api-gateway 2>&1 | grep "401\|token\|jwt"
```

### Common API Errors

| HTTP Code | Meaning                  | Fix                                             |
| --------- | ------------------------ | ----------------------------------------------- |
| 401       | JWT expired or invalid   | Re-login to get new token                       |
| 403       | Insufficient permissions | Check user role (`admin` required for most ops) |
| 404       | Endpoint not found       | Check API prefix (`/api/v1/...`)                |
| 422       | Validation error         | Check request body matches expected schema      |
| 429       | Rate limited             | Wait and retry, or increase rate limit          |
| 500       | Internal server error    | Check API Gateway logs for stack trace          |
| 502       | Bad Gateway (nginx)      | API Gateway container is down, restart it       |
| 503       | Service unavailable      | DB or Redis connection failure                  |

---

## 14. Policy Engine Issues

### Symptom: Policy Evaluation Failing / Slow

```bash
# Check health
curl http://localhost:8082/health

# Check gRPC port
nc -zv localhost 9091

# Check logs
docker compose logs --tail=50 policy-engine

# Test direct evaluation
curl -X POST http://localhost:8082/evaluate \
  -H "Content-Type: application/json" \
  -d '{"tenant_id":"00000000-0000-0000-0000-000000000000","auth_context":{"username":"test"}}'
```

### Common Issues

| Issue                    | Cause                                 | Fix                                       |
| ------------------------ | ------------------------------------- | ----------------------------------------- |
| gRPC connection refused  | PE crashed or port conflict           | Restart PE, check port 9091               |
| Slow evaluation (>100ms) | Large policy set, unoptimized queries | Check DB index usage, reduce policy count |
| Wrong policy result      | Condition ordering issue              | Check policy priority/order in DB         |
| `protobuf` import errors | Missing generated stubs               | Run `python scripts/generate_proto.py`    |

---

## 15. AI Engine Issues

### Symptom: AI Modules Not Working

```bash
# Check all 7 modules
curl http://localhost:8081/health

# Test individual modules
# Profiler
curl -X POST http://localhost:8081/api/v1/profile \
  -d '{"mac":"AA:BB:CC:DD:EE:FF","vendor":"Cisco"}'

# Risk scorer
curl -X POST http://localhost:8081/api/v1/risk \
  -d '{"endpoint_mac":"AA:BB:CC:DD:EE:FF","username":"test","failed_auths":0}'

# Shadow AI detector
curl -X POST http://localhost:8081/api/v1/shadow \
  -d '{"dns_queries":["api.openai.com"],"destination_ips":["104.18.0.0"]}'

# NLP policy assistant
curl -X POST http://localhost:8081/api/v1/nlp/translate \
  -d '{"text":"block all guest users after 6pm"}'

# Anomaly detector
curl -X POST http://localhost:8081/api/v1/anomaly/analyze \
  -d '{"endpoint_mac":"AA:BB:CC:DD:EE:FF","username":"test","nas_ip":"10.0.0.1"}'

# Drift detector
curl "http://localhost:8081/api/v1/drift/analyze"
```

### Common Issues

| Issue                         | Cause                             | Fix                                        |
| ----------------------------- | --------------------------------- | ------------------------------------------ |
| ONNX model load failure       | Model file missing or corrupt     | Re-download model, check `profiler.py`     |
| NLP returns empty result      | LLM endpoint unreachable          | Check `LLM_API_URL` env var, verify Ollama |
| High risk scores for everyone | Risk scorer weights miscalibrated | Check `risk.py` thresholds                 |
| Shadow AI false positives     | DNS patterns too broad            | Tune signatures in `shadow.py`             |

---

## 16. Sync Engine Issues

### Symptom: Twin Nodes Not Syncing

```bash
# Check sync status
curl http://localhost:9100/sync/status
curl http://localhost:9100/health

# Check logs
docker compose logs --tail=50 sync-engine

# Check peer connection state
docker compose logs sync-engine 2>&1 | grep -i "peer\|connect\|grpc"

# Check undelivered sync journal entries
docker exec neuranac-postgres psql -U neuranac -c "
  SELECT count(*), operation_type
  FROM sync_journal
  WHERE NOT delivered
  GROUP BY operation_type"
```

### Common Issues

| Issue                  | Cause                       | Fix                                     |
| ---------------------- | --------------------------- | --------------------------------------- |
| "No peer configured"   | `SYNC_PEER_ADDRESS` not set | Set env var to peer's `hostname:9090`   |
| Peer connection failed | Network/firewall issue      | Verify TCP 9090 reachable between nodes |
| TRANSIENT_FAILURE      | Peer node down              | Start peer node, sync will auto-resume  |
| Sync lag growing       | Slow DB writes on peer      | Check DB performance on both nodes      |

---

## 17. Database Issues

### Symptom: Database Connection Failures

```bash
# Check PostgreSQL is running
docker exec neuranac-postgres pg_isready -U neuranac

# Check connection count (max is usually 100)
docker exec neuranac-postgres psql -U neuranac -c "
  SELECT count(*) as total_connections,
    max_conn.max as max_connections
  FROM pg_stat_activity,
    (SELECT setting::int as max FROM pg_settings WHERE name='max_connections') max_conn
  WHERE datname = 'neuranac'
  GROUP BY max_conn.max"

# Check for long-running queries
docker exec neuranac-postgres psql -U neuranac -c "
  SELECT pid, now() - query_start AS duration, state, LEFT(query, 80) AS query
  FROM pg_stat_activity
  WHERE datname = 'neuranac' AND state = 'active'
  ORDER BY duration DESC
  LIMIT 10"

# Kill a stuck query
docker exec neuranac-postgres psql -U neuranac -c "SELECT pg_terminate_backend(<pid>)"
```

### Symptom: Database Disk Full

```bash
# Check disk usage
docker exec neuranac-postgres psql -U neuranac -c "
  SELECT pg_size_pretty(pg_database_size('neuranac'))"

# Find largest tables
docker exec neuranac-postgres psql -U neuranac -c "
  SELECT relname, pg_size_pretty(pg_total_relation_size(relid))
  FROM pg_catalog.pg_statio_user_tables
  ORDER BY pg_total_relation_size(relid) DESC LIMIT 10"

# Emergency: purge old data
docker exec neuranac-postgres psql -U neuranac -c "
  DELETE FROM sessions WHERE ended_at < NOW() - INTERVAL '30 days';
  DELETE FROM audit_logs WHERE created_at < NOW() - INTERVAL '90 days';
  DELETE FROM legacy_nac_sync_log WHERE started_at < NOW() - INTERVAL '30 days';
  VACUUM FULL;"
```

---

## 18. Redis / Cache Issues

### Symptom: Rate Limiting Not Working / Token Errors

```bash
# Check Redis
docker exec neuranac-redis redis-cli -a neuranac_dev_password ping

# Check memory usage
docker exec neuranac-redis redis-cli -a neuranac_dev_password INFO memory | grep used_memory_human

# Check key count
docker exec neuranac-redis redis-cli -a neuranac_dev_password DBSIZE

# Flush rate limit keys (emergency — resets all rate limits)
docker exec neuranac-redis redis-cli -a neuranac_dev_password KEYS "rate_limit:*" | \
  xargs -I {} docker exec neuranac-redis redis-cli -a neuranac_dev_password DEL {}

# Full flush (emergency — clears ALL cache)
docker exec neuranac-redis redis-cli -a neuranac_dev_password FLUSHDB
```

---

## 19. NATS / Event Bus Issues

### Symptom: Events Not Being Delivered

```bash
# Check NATS health
curl http://localhost:8222/healthz

# Check connections
curl http://localhost:8222/connz | jq '.connections | length'

# Check subscriptions
curl http://localhost:8222/subsz | jq '.num_subscriptions'

# Check server info
curl http://localhost:8222/varz | jq '{connections, in_msgs, out_msgs, slow_consumers}'

# Restart NATS if needed
docker compose restart nats
```

---

## 20. Web Dashboard Issues

### Symptom: Dashboard Not Loading / Blank Page

```bash
# Check if dashboard container is running
docker compose ps web

# Check nginx logs
docker compose logs --tail=30 web

# Test static file serving
curl -s -o /dev/null -w "%{http_code}" http://localhost:3001

# Test API connectivity from browser (CORS)
curl -I http://localhost:8080/health
# Look for: Access-Control-Allow-Origin header
```

### Common Issues

| Issue                        | Cause                     | Fix                                                   |
| ---------------------------- | ------------------------- | ----------------------------------------------------- |
| Blank white page             | JS bundle failed to load  | Check browser console (F12), rebuild: `npm run build` |
| "Network Error" on API calls | CORS misconfigured        | Check `API_CORS_ORIGINS` env var                      |
| Login fails                  | API Gateway down          | Check API health endpoint                             |
| Stale data                   | React Query cache         | Hard refresh (Ctrl+Shift+R)                           |
| 502 Bad Gateway              | Nginx can't reach backend | Check API Gateway container is running                |

---

## 21. Legacy NAC Integration Troubleshooting

### Symptom: Legacy Connection Failed

```bash
# Check connection status
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8080/api/v1/legacy-nac/connections/{id}

# Test connectivity
curl -X POST http://localhost:8080/api/v1/legacy-nac/connections/{id}/test \
  -H "Authorization: Bearer $TOKEN"

# Check last error
docker exec neuranac-postgres psql -U neuranac -c "
  SELECT name, hostname, connection_status, last_error, last_connected_at
  FROM legacy_nac_connections WHERE is_active = TRUE"
```

### Legacy Connection Error Matrix

| Error                           | Cause                          | Fix                                              |
| ------------------------------- | ------------------------------ | ------------------------------------------------ |
| `Connection refused`            | NeuraNAC not reachable on port 9060 | Check firewall, verify Legacy ERS port              |
| `401 Unauthorized`              | Wrong ERS credentials          | Verify username/password in NeuraNAC Admin            |
| `403 Forbidden`                 | ERS API not enabled on NeuraNAC     | NeuraNAC Admin → Settings → API Settings → Enable ERS |
| `SSL certificate verify failed` | NeuraNAC using self-signed cert     | Set `verify_ssl: false` or import NeuraNAC CA cert    |
| `Connection timed out`          | Network routing issue          | Verify NeuraNAC can reach NeuraNAC hostname:9060           |
| `404 on /ers/config/*`          | Wrong legacy version or ERS path  | Verify NeuraNAC 3.4+ and ERS URL path                 |

### Symptom: Legacy Sync Failures

```bash
# Check sync status per entity type
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8080/api/v1/legacy-nac/connections/{id}/sync-status

# Check sync log for errors
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8080/api/v1/legacy-nac/connections/{id}/sync-log?limit=10"

# DB query for failed syncs
docker exec neuranac-postgres psql -U neuranac -c "
  SELECT entity_type, last_sync_status, last_sync_error, items_synced, items_failed
  FROM legacy_nac_sync_state
  WHERE connection_id = '<conn_id>'
  ORDER BY entity_type"
```

### Symptom: Event Stream Not Connecting

```bash
# Verify Event Stream is enabled on NeuraNAC
# NeuraNAC Admin → Administration → Event Stream Services → Settings → Enable Event Stream

# Check certificate
# NeuraNAC Admin → Administration → Event Stream Services → Client Management
# Verify NeuraNAC's client certificate is listed and APPROVED

# Common Event Stream issues:
# 1. Certificate not approved in NeuraNAC
# 2. Event Stream service not running on NeuraNAC
# 3. Firewall blocking port 8910
# 4. Certificate CN mismatch
```

---

## 22. Performance Troubleshooting

### Symptom: Slow API Response Times

```bash
# Check Prometheus metrics
curl http://localhost:8080/metrics | grep http_request_duration

# Check DB query latency
docker exec neuranac-postgres psql -U neuranac -c "
  SELECT calls, total_exec_time / calls AS avg_ms, LEFT(query, 100) AS query
  FROM pg_stat_statements
  WHERE calls > 10
  ORDER BY total_exec_time / calls DESC
  LIMIT 10"

# Check container resource usage
docker stats --no-stream
```

### Symptom: RADIUS Latency > 100ms

```bash
# Expected: <20ms for PAP, <50ms for EAP-TLS

# Check if Policy Engine is the bottleneck
docker compose logs radius-server 2>&1 | grep "evaluate.*ms"

# Check DB latency
docker exec neuranac-postgres psql -U neuranac -c "
  SELECT datname, xact_commit, xact_rollback,
    blks_read, blks_hit,
    ROUND(blks_hit::numeric / GREATEST(blks_hit + blks_read, 1) * 100, 1) AS cache_hit_pct
  FROM pg_stat_database
  WHERE datname = 'neuranac'"
# cache_hit_pct should be >95%
```

### Performance Baselines

| Operation              | Expected Latency | Alert Threshold |
| ---------------------- | ---------------- | --------------- |
| PAP Authentication     | <20ms            | >50ms           |
| EAP-TLS Full Handshake | <100ms           | >200ms          |
| Policy Evaluation      | <10ms            | >50ms           |
| API GET (list)         | <50ms            | >200ms          |
| API POST (create)      | <100ms           | >300ms          |
| AI Risk Scoring        | <30ms            | >100ms          |
| Legacy ERS API Call       | <500ms           | >2s             |
| Dashboard Page Load    | <2s              | >5s             |

---

## 23. Security Incident Response

### 23.1 Suspected Unauthorized Access

```bash
# 1. Check recent login attempts
docker exec neuranac-postgres psql -U neuranac -c "
  SELECT created_at, username, action, ip_address, details
  FROM audit_logs
  WHERE action IN ('login', 'login_failed')
  AND created_at > NOW() - INTERVAL '24 hours'
  ORDER BY created_at DESC"

# 2. Check for unusual API activity
docker exec neuranac-postgres psql -U neuranac -c "
  SELECT ip_address, count(*) AS requests, 
    count(*) FILTER (WHERE action = 'login_failed') AS failed_logins
  FROM audit_logs
  WHERE created_at > NOW() - INTERVAL '1 hour'
  GROUP BY ip_address
  HAVING count(*) > 100
  ORDER BY requests DESC"

# 3. Lock compromised accounts
docker exec neuranac-postgres psql -U neuranac -c "
  UPDATE admin_users SET is_active = FALSE WHERE username = '<compromised_user>'"

# 4. Rotate JWT secret (invalidates ALL sessions)
# Update JWT_SECRET in .env and restart API Gateway
docker compose restart api-gateway
```

### 23.2 Suspected Rogue NAD

```bash
# 1. Check recent RADIUS auth from unknown IPs
docker compose logs radius-server 2>&1 | grep "unknown NAS\|no matching NAD"

# 2. Send CoA Disconnect to suspicious session
curl -X POST http://localhost:8080/api/v1/sessions/{session_id}/coa \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"action": "disconnect"}'

# 3. Block the NAD IP in firewall
iptables -A INPUT -s <rogue_nad_ip> -p udp --dport 1812 -j DROP
```

### 23.3 Shadow AI Alert

```bash
# 1. Check shadow AI detections
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8080/api/v1/ai/data-flow

# 2. Get details on flagged endpoint
curl -X POST http://localhost:8081/api/v1/shadow \
  -d '{"dns_queries":["api.openai.com","chat.anthropic.com"]}'

# 3. Quarantine the endpoint (move to restricted VLAN)
curl -X POST http://localhost:8080/api/v1/sessions/{session_id}/coa \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"action": "reauthenticate"}'
```

---

# Appendices

## Appendix A: Service Port Reference

| Service            | Port | Protocol | Internal/External |
| ------------------ | ---- | -------- | ----------------- |
| API Gateway        | 8080 | HTTP     | External          |
| Web Dashboard      | 3001 | HTTP     | External          |
| RADIUS Auth        | 1812 | UDP      | External          |
| RADIUS Acct        | 1813 | UDP      | External          |
| RadSec             | 2083 | TCP/TLS  | External          |
| TACACS+            | 49   | TCP      | External          |
| CoA                | 3799 | UDP      | Internal→NAD      |
| Policy Engine REST | 8082 | HTTP     | Internal          |
| Policy Engine gRPC | 9091 | gRPC     | Internal          |
| AI Engine          | 8081 | HTTP     | Internal          |
| Sync Engine gRPC   | 9090 | gRPC     | Internal          |
| Sync Engine Health | 9100 | HTTP     | Internal          |
| PostgreSQL         | 5432 | TCP      | Internal          |
| Redis              | 6379 | TCP      | Internal          |
| NATS               | 4222 | TCP      | Internal          |
| NATS Monitor       | 8222 | HTTP     | Internal          |
| Prometheus         | 9092 | HTTP     | Internal          |
| Grafana            | 3000 | HTTP     | External          |

## Appendix B: Log Locations & Formats

| Service       | Log Access                          | Format                         |
| ------------- | ----------------------------------- | ------------------------------ |
| API Gateway   | `docker compose logs api-gateway`   | JSON (structlog)               |
| RADIUS Server | `docker compose logs radius-server` | JSON (zap)                     |
| Policy Engine | `docker compose logs policy-engine` | JSON (structlog)               |
| AI Engine     | `docker compose logs ai-engine`     | JSON (structlog)               |
| Sync Engine   | `docker compose logs sync-engine`   | JSON (zap)                     |
| PostgreSQL    | `docker compose logs postgres`      | Plain text                     |
| Redis         | `docker compose logs redis`         | Plain text                     |
| NATS          | `docker compose logs nats`          | Plain text                     |
| Audit Trail   | `GET /api/v1/audit/`                | JSON (DB-backed, tamper-proof) |

## Appendix C: Common Error Codes

### RADIUS Response Codes

| Code | Name             | Meaning                            |
| ---- | ---------------- | ---------------------------------- |
| 2    | Access-Accept    | Authentication successful          |
| 3    | Access-Reject    | Authentication failed              |
| 11   | Access-Challenge | Multi-step auth (EAP) in progress  |
| 40   | Disconnect-ACK   | CoA disconnect successful          |
| 41   | Disconnect-NAK   | CoA disconnect failed              |
| 44   | CoA-ACK          | Change of Authorization successful |
| 45   | CoA-NAK          | Change of Authorization failed     |

### HTTP Status Codes (API Gateway)

| Code | Meaning          | Action                                 |
| ---- | ---------------- | -------------------------------------- |
| 200  | Success          | —                                      |
| 201  | Created          | Resource created successfully          |
| 400  | Bad Request      | Check request body format              |
| 401  | Unauthorized     | Login again / refresh token            |
| 403  | Forbidden        | Insufficient role permissions          |
| 404  | Not Found        | Check URL path                         |
| 409  | Conflict         | Duplicate resource (e.g., same NAD IP) |
| 422  | Validation Error | Check field types and constraints      |
| 429  | Rate Limited     | Wait, then retry                       |
| 500  | Internal Error   | Check API logs for stack trace         |

## Appendix D: Useful SQL Queries

```sql
-- Active session count by NAD
SELECT nd.name, nd.ip_address, count(s.id) AS active_sessions
FROM sessions s
JOIN network_devices nd ON s.nas_ip_address = nd.ip_address
WHERE s.is_active = TRUE
GROUP BY nd.name, nd.ip_address
ORDER BY active_sessions DESC;

-- Failed auth attempts in last hour (by username)
SELECT username, count(*) AS failures, max(created_at) AS last_attempt
FROM audit_logs
WHERE action = 'auth_failed'
  AND created_at > NOW() - INTERVAL '1 hour'
GROUP BY username
HAVING count(*) > 3
ORDER BY failures DESC;

-- Endpoint inventory by device type
SELECT device_type, count(*) AS count
FROM endpoints
GROUP BY device_type
ORDER BY count DESC;

-- legacy sync health overview
SELECT ic.name, ic.hostname, ic.connection_status,
  iss.entity_type, iss.last_sync_status, iss.items_synced, iss.items_failed
FROM legacy_nac_connections ic
LEFT JOIN legacy_nac_sync_state iss ON ic.id = iss.connection_id
WHERE ic.is_active = TRUE
ORDER BY ic.name, iss.entity_type;

-- Policy hit count (which policies are being used)
SELECT p.name, p.policy_type, p.priority, p.hit_count
FROM policies p
WHERE p.is_active = TRUE
ORDER BY p.hit_count DESC
LIMIT 20;

-- Certificate expiry report
SELECT common_name, issuer,
  not_after,
  EXTRACT(DAY FROM not_after - NOW())::int AS days_remaining,
  CASE
    WHEN not_after < NOW() THEN 'EXPIRED'
    WHEN not_after < NOW() + INTERVAL '30 days' THEN 'EXPIRING SOON'
    ELSE 'OK'
  END AS status
FROM certificates
ORDER BY not_after ASC;

-- Database size breakdown
SELECT relname AS table_name,
  pg_size_pretty(pg_total_relation_size(relid)) AS total_size,
  pg_size_pretty(pg_relation_size(relid)) AS data_size,
  pg_size_pretty(pg_indexes_size(relid)) AS index_size,
  n_live_tup AS rows
FROM pg_catalog.pg_statio_user_tables
JOIN pg_stat_user_tables USING (relid)
ORDER BY pg_total_relation_size(relid) DESC
LIMIT 20;
```

## Appendix E: Emergency Contacts & Escalation

| Level | Response Time | Who                           | When to Escalate                                     |
| ----- | ------------- | ----------------------------- | ---------------------------------------------------- |
| L1    | <15 min       | NOC Engineer                  | Service health check failures, dashboard down        |
| L2    | <30 min       | SRE / Platform Engineer       | RADIUS auth failures affecting >10% users, DB issues |
| L3    | <1 hour       | NeuraNAC Dev Team                  | Code bugs, security vulnerabilities, data corruption |
| P1    | Immediate     | Engineering Lead + Management | Full platform outage, security breach, data loss     |

### Escalation Triggers

- **P1 (Critical):** All RADIUS auth failing, platform completely down, security breach
- **P2 (High):** Single service down affecting users, sync engine split-brain, legacy sync completely broken
- **P3 (Medium):** Degraded performance, non-critical feature broken, certificate expiring <7 days
- **P4 (Low):** Cosmetic dashboard issues, log warnings, non-urgent maintenance needed

---

*This runbook is maintained by the NeuraNAC Operations team. Update it whenever a new issue pattern is discovered or a procedure changes.*
