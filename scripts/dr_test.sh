#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# NeuraNAC Disaster Recovery / Failover Test Script
#
# Validates backup integrity and simulates infrastructure failures to verify
# the system degrades gracefully and recovers correctly.
#
# Usage:  ./scripts/dr_test.sh [--skip-backup] [--skip-failover]
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DEPLOY_DIR="$PROJECT_ROOT/deploy"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PASS=0
FAIL=0
SKIP=0

SKIP_BACKUP=false
SKIP_FAILOVER=false

for arg in "$@"; do
  case "$arg" in
    --skip-backup)   SKIP_BACKUP=true ;;
    --skip-failover) SKIP_FAILOVER=true ;;
  esac
done

log_pass() { echo -e "${GREEN}✓ PASS${NC}: $1"; PASS=$((PASS+1)); }
log_fail() { echo -e "${RED}✗ FAIL${NC}: $1"; FAIL=$((FAIL+1)); }
log_skip() { echo -e "${YELLOW}⊘ SKIP${NC}: $1"; SKIP=$((SKIP+1)); }
log_info() { echo -e "  ℹ $1"; }

api_health() {
  curl -sf --max-time 5 http://localhost:8080/api/v1/health > /dev/null 2>&1
}

echo "═══════════════════════════════════════════════════════════"
echo " NeuraNAC Disaster Recovery Test Suite"
echo "═══════════════════════════════════════════════════════════"
echo ""

# ─── Phase 1: Backup Integrity ─────────────────────────────────────────────
echo "── Phase 1: Backup Integrity ──"
if [ "$SKIP_BACKUP" = true ]; then
  log_skip "Backup tests (--skip-backup)"
else
  # 1a. Run backup script
  BACKUP_FILE="/tmp/neuranac_dr_test_backup_$(date +%s).sql"
  if docker exec neuranac-postgres pg_dump -U neuranac neuranac > "$BACKUP_FILE" 2>/dev/null; then
    log_pass "pg_dump backup created ($(du -h "$BACKUP_FILE" | cut -f1))"
  else
    log_fail "pg_dump backup failed"
  fi

  # 1b. Verify backup is non-empty and contains expected tables
  if [ -f "$BACKUP_FILE" ] && [ -s "$BACKUP_FILE" ]; then
    TABLE_COUNT=$(grep -c "CREATE TABLE" "$BACKUP_FILE" 2>/dev/null || echo 0)
    if [ "$TABLE_COUNT" -gt 30 ]; then
      log_pass "Backup contains $TABLE_COUNT CREATE TABLE statements"
    else
      log_fail "Backup only has $TABLE_COUNT tables (expected > 30)"
    fi
  else
    log_fail "Backup file is empty or missing"
  fi

  # 1c. Restore to a temp database
  if docker exec neuranac-postgres psql -U neuranac -c "DROP DATABASE IF EXISTS neuranac_dr_test;" > /dev/null 2>&1 && \
     docker exec neuranac-postgres psql -U neuranac -c "CREATE DATABASE neuranac_dr_test;" > /dev/null 2>&1; then
    if docker exec -i neuranac-postgres psql -U neuranac neuranac_dr_test < "$BACKUP_FILE" > /dev/null 2>&1; then
      RESTORED_TABLES=$(docker exec neuranac-postgres psql -U neuranac -t -c \
        "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';" neuranac_dr_test 2>/dev/null | tr -d ' ')
      if [ "$RESTORED_TABLES" -gt 30 ] 2>/dev/null; then
        log_pass "Restore verified: $RESTORED_TABLES tables in test database"
      else
        log_fail "Restore produced only $RESTORED_TABLES tables"
      fi
    else
      log_fail "Restore to test database failed"
    fi
    # Cleanup
    docker exec neuranac-postgres psql -U neuranac -c "DROP DATABASE IF EXISTS neuranac_dr_test;" > /dev/null 2>&1
  else
    log_fail "Could not create test database for restore verification"
  fi

  rm -f "$BACKUP_FILE"
fi

echo ""

# ─── Phase 2: PostgreSQL Failover ──────────────────────────────────────────
echo "── Phase 2: PostgreSQL Failover ──"
if [ "$SKIP_FAILOVER" = true ]; then
  log_skip "Failover tests (--skip-failover)"
else
  # Verify API is healthy before test
  if api_health; then
    log_pass "API healthy before Postgres failover"
  else
    log_fail "API unhealthy before Postgres failover test (skipping)"
    SKIP=$((SKIP+3))
    echo ""
    echo "── Phase 3: Redis Failover ──"
    log_skip "Redis failover (API was unhealthy)"
    echo ""
    echo "── Phase 4: NATS Failover ──"
    log_skip "NATS failover (API was unhealthy)"
    echo ""
    # Jump to summary
    echo "═══════════════════════════════════════════════════════════"
    echo -e " Results: ${GREEN}$PASS passed${NC}, ${RED}$FAIL failed${NC}, ${YELLOW}$SKIP skipped${NC}"
    echo "═══════════════════════════════════════════════════════════"
    exit $FAIL
  fi

  # Stop Postgres
  log_info "Stopping PostgreSQL..."
  docker stop neuranac-postgres > /dev/null 2>&1 || true
  sleep 3

  # API should report unhealthy or 503
  if api_health; then
    log_fail "API still reports healthy after Postgres stopped (expected failure)"
  else
    log_pass "API correctly reports unhealthy after Postgres stopped"
  fi

  # Restart Postgres
  log_info "Restarting PostgreSQL..."
  docker start neuranac-postgres > /dev/null 2>&1
  sleep 8  # wait for healthcheck

  # API should recover
  RECOVERED=false
  for i in $(seq 1 10); do
    if api_health; then
      RECOVERED=true
      break
    fi
    sleep 2
  done
  if [ "$RECOVERED" = true ]; then
    log_pass "API recovered after Postgres restart"
  else
    log_fail "API did not recover within 20s after Postgres restart"
  fi
fi

echo ""

# ─── Phase 3: Redis Failover ──────────────────────────────────────────────
echo "── Phase 3: Redis Failover ──"
if [ "$SKIP_FAILOVER" = true ]; then
  log_skip "Redis failover (--skip-failover)"
else
  log_info "Stopping Redis..."
  docker stop neuranac-redis > /dev/null 2>&1 || true
  sleep 3

  # API should still be reachable (graceful degradation)
  if api_health; then
    log_pass "API still healthy with Redis down (graceful degradation)"
  else
    log_fail "API became unhealthy with Redis down (should degrade gracefully)"
  fi

  log_info "Restarting Redis..."
  docker start neuranac-redis > /dev/null 2>&1
  sleep 5

  if api_health; then
    log_pass "API healthy after Redis restart"
  else
    log_fail "API unhealthy after Redis restart"
  fi
fi

echo ""

# ─── Phase 4: NATS Failover ──────────────────────────────────────────────
echo "── Phase 4: NATS Failover ──"
if [ "$SKIP_FAILOVER" = true ]; then
  log_skip "NATS failover (--skip-failover)"
else
  log_info "Stopping NATS..."
  docker stop neuranac-nats > /dev/null 2>&1 || true
  sleep 3

  # API should still be reachable (NATS is async, not in critical path)
  if api_health; then
    log_pass "API still healthy with NATS down"
  else
    log_fail "API became unhealthy with NATS down"
  fi

  log_info "Restarting NATS..."
  docker start neuranac-nats > /dev/null 2>&1
  sleep 5

  if api_health; then
    log_pass "API healthy after NATS restart"
  else
    log_fail "API unhealthy after NATS restart"
  fi
fi

echo ""

# ─── Summary ──────────────────────────────────────────────────────────────
echo "═══════════════════════════════════════════════════════════"
TOTAL=$((PASS+FAIL+SKIP))
echo -e " DR Test Results: ${GREEN}$PASS passed${NC}, ${RED}$FAIL failed${NC}, ${YELLOW}$SKIP skipped${NC} (total: $TOTAL)"
echo "═══════════════════════════════════════════════════════════"

if [ "$FAIL" -gt 0 ]; then
  exit 1
fi
exit 0
