# NeuraNAC Incident Response Runbook

## 1. Severity Levels

| Severity  | Description             | Response Time     | Example                                            |
| --------- | ----------------------- | ----------------- | -------------------------------------------------- |
| **SEV-1** | Complete service outage | 15 min            | RADIUS auth down, all users unable to authenticate |
| **SEV-2** | Degraded service        | 30 min            | High auth latency, partial failures, EAP timeouts  |
| **SEV-3** | Minor impact            | 2 hours           | AI features unavailable, dashboard slow            |
| **SEV-4** | No user impact          | Next business day | Log aggregation gap, non-critical alert            |

---

## 2. RADIUS Authentication Failures

### Symptoms
- Alert: `RADIUSAuthDown` or `RADIUSAuthHighErrorRate`
- Users unable to authenticate to network
- Switches/APs reporting RADIUS timeout

### Diagnosis Steps
```bash
# 1. Check RADIUS server health
curl http://radius-server:9100/health

# 2. Check metrics for error patterns
curl -s http://radius-server:9100/metrics | grep radius_auth

# 3. Check RADIUS server logs
docker compose -f deploy/docker-compose.yml logs --tail=100 radius-server

# 4. Check Policy Engine connectivity (gRPC)
curl http://policy-engine:8082/health

# 5. Check database connectivity
docker compose -f deploy/docker-compose.yml exec postgres pg_isready -U neuranac

# 6. Check Redis for EAP sessions
docker compose -f deploy/docker-compose.yml exec redis redis-cli -a $REDIS_PASSWORD INFO keyspace
```

### Resolution
| Cause                         | Fix                                                                      |
| ----------------------------- | ------------------------------------------------------------------------ |
| RADIUS process crashed        | `docker compose restart radius-server`                                   |
| Policy Engine down            | `docker compose restart policy-engine` — RADIUS will use cached policies |
| Database unreachable          | Check PostgreSQL health, restore from backup if needed                   |
| Redis down (EAP failures)     | `docker compose restart redis` — EAP sessions will reset                 |
| High latency from policy eval | Check circuit breaker state, scale Policy Engine replicas                |
| Certificate expired           | Rotate TLS certs: `./scripts/rotate_secrets.sh jwt`                      |

### Escalation
If RADIUS auth is down > 5 minutes and above steps don't resolve:
1. Enable RADIUS fallback to local auth (if configured)
2. Check network connectivity between RADIUS and switches
3. Verify shared secrets match on NADs

---

## 3. API Gateway Outage

### Symptoms
- Alert: `APIGatewayDown` or `APIHighErrorRate`
- Dashboard inaccessible
- API returns 5xx errors

### Diagnosis Steps
```bash
# 1. Check API Gateway health
curl http://localhost:8080/health

# 2. Check logs
docker compose -f deploy/docker-compose.yml logs --tail=100 api-gateway

# 3. Check database connection pool
curl http://localhost:8080/api/v1/diagnostics/health | python3 -m json.tool

# 4. Check Redis connectivity
docker compose -f deploy/docker-compose.yml exec redis redis-cli PING
```

### Resolution
| Cause                  | Fix                                                                                     |
| ---------------------- | --------------------------------------------------------------------------------------- |
| OOM kill               | Increase memory limits, restart: `docker compose restart api-gateway`                   |
| DB pool exhausted      | Check for long-running queries: `SELECT * FROM pg_stat_activity WHERE state = 'active'` |
| Redis connection error | Restart Redis or check network; API Gateway degrades gracefully                         |
| Python exception loop  | Check logs for traceback, fix and redeploy                                              |

---

## 4. Database Issues

### PostgreSQL Down
```bash
# Check status
docker compose -f deploy/docker-compose.yml exec postgres pg_isready -U neuranac

# Check disk space
docker compose -f deploy/docker-compose.yml exec postgres df -h

# Check connections
docker compose -f deploy/docker-compose.yml exec postgres psql -U neuranac -c "SELECT count(*) FROM pg_stat_activity;"

# Emergency: kill idle connections
docker compose -f deploy/docker-compose.yml exec postgres psql -U neuranac -c \
  "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'idle' AND query_start < NOW() - INTERVAL '10 minutes';"
```

### Schema Mismatch
```bash
# Run schema validation
curl http://localhost:8080/api/v1/diagnostics/db-schema-check | python3 -m json.tool

# Re-run migrations
./scripts/setup.sh  # This applies all V*.sql migrations in order
```

### Restore from Backup
```bash
./scripts/restore.sh backups/postgres/neuranac_pg_YYYYMMDD.dump
```

---

## 5. EAP Session Failures (Multi-Replica)

### Symptoms
- 802.1X users fail after initial challenge
- `radius_eap_sessions_timedout_total` increasing
- Works with 1 replica, fails with multiple

### Diagnosis
```bash
# Check if Redis-backed EAP store is active
docker compose -f deploy/docker-compose.yml exec radius-server env | grep EAP_SESSION_STORE

# Check Redis EAP session keys
docker compose -f deploy/docker-compose.yml exec redis redis-cli -a $REDIS_PASSWORD KEYS "eap_session:*"
```

### Resolution
1. Ensure `EAP_SESSION_STORE=redis` in environment
2. Verify Redis is accessible from RADIUS server
3. If Redis is down, scale RADIUS to 1 replica temporarily

---

## 6. NATS Messaging Issues

### Symptoms
- CoA requests not being sent
- Session events not publishing
- Sync engine not replicating

### Diagnosis
```bash
# Check NATS health
curl http://nats:8222/healthz

# Check NATS connections
curl http://nats:8222/connz

# Check JetStream status
curl http://nats:8222/jsz
```

---

## 7. Performance Degradation

### High Auth Latency
```bash
# Check RADIUS metrics
curl -s http://radius-server:9100/metrics | grep duration

# Check Policy Engine load
curl -s http://policy-engine:8082/metrics | grep policy_eval

# Check DB query performance
docker compose exec postgres psql -U neuranac -c \
  "SELECT query, mean_exec_time, calls FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 10;"
```

### Memory Pressure
```bash
# Check container memory usage
docker stats --no-stream

# Check PostgreSQL memory
docker compose exec postgres psql -U neuranac -c "SHOW shared_buffers; SHOW work_mem; SHOW effective_cache_size;"
```

---

## 8. Recovery Procedures

### Full System Recovery
```bash
# 1. Stop all services
docker compose -f deploy/docker-compose.yml down

# 2. Start infrastructure first
docker compose -f deploy/docker-compose.yml up -d postgres redis nats

# 3. Wait for health
sleep 10

# 4. Run migrations
for f in database/migrations/V*.sql; do
  docker compose -f deploy/docker-compose.yml exec -T postgres psql -U neuranac -d neuranac < "$f" || true
done

# 5. Start application services
docker compose -f deploy/docker-compose.yml up -d

# 6. Verify
curl http://localhost:8080/health
curl http://localhost:8080/api/v1/diagnostics/db-schema-check
```

### Rollback Deployment
```bash
# Revert to previous image tag
docker compose -f deploy/docker-compose.yml pull  # with previous tag in .env
docker compose -f deploy/docker-compose.yml up -d --force-recreate

# For Helm deployments
helm rollback neuranac <revision-number>
```

---

## 9. Contact & Escalation

| Role               | Contact                     | When                    |
| ------------------ | --------------------------- | ----------------------- |
| On-call engineer   | PagerDuty/OpsGenie rotation | SEV-1, SEV-2            |
| Platform team lead | Slack #neuranac-platform         | SEV-1 after 15 min      |
| Database admin     | Slack #neuranac-dba              | DB-specific issues      |
| Network team       | Slack #neuranac-network          | NAD/switch connectivity |
