#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# NeuraNAC Interactive Demo Runner
# Runs inside the demo-tools container with all client tools pre-installed.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

# ── Colors ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

# ── Config (from environment, set in docker-compose) ──────────────────────────
API_URL="${NeuraNAC_API_URL:-http://api-gateway:8080}"
API="${API_URL}/api/v1"
RADIUS_HOST="${NeuraNAC_RADIUS_IP:-radius-server}"
RADIUS_SECRET="${RADIUS_SECRET:-testing123}"
RADIUS_USER="${RADIUS_USER:-testuser}"
RADIUS_PASS="${RADIUS_PASS:-testing123}"
ADMIN_USER="${ADMIN_USER:-admin}"
ADMIN_PASS="${ADMIN_PASS:-admin123}"
TOKEN=""

# ── Helpers ───────────────────────────────────────────────────────────────────
banner() {
    echo ""
    echo -e "${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║${NC}  ${BOLD}NeuraNAC Demo Runner${NC} — All tools containerized                  ${CYAN}║${NC}"
    echo -e "${CYAN}║${NC}  radtest • Go RADIUS • k6 • sanity runner • curl/jq        ${CYAN}║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
fail() { echo -e "  ${RED}✗${NC} $1"; }
info() { echo -e "  ${BLUE}ℹ${NC} $1"; }
warn() { echo -e "  ${YELLOW}⚠${NC} $1"; }
header() { echo -e "\n${BOLD}── $1 ──${NC}\n"; }

get_token() {
    if [ -z "$TOKEN" ]; then
        TOKEN=$(curl -sf -X POST "${API}/auth/login" \
            -H "Content-Type: application/json" \
            -d "{\"username\":\"${ADMIN_USER}\",\"password\":\"${ADMIN_PASS}\"}" | jq -r '.access_token // .token // empty' 2>/dev/null || true)
        if [ -n "$TOKEN" ]; then
            ok "JWT token obtained"
        else
            warn "Could not obtain JWT token — some API calls may fail"
        fi
    fi
}

auth_header() {
    echo "Authorization: Bearer ${TOKEN}"
}

wait_for_services() {
    header "Checking NeuraNAC Services"
    local all_ok=true

    for svc in "API Gateway|${API_URL}/health" "RADIUS Server|http://radius-server:9100/health" "Policy Engine|http://policy-engine:8082/health" "AI Engine|http://ai-engine:8081/health"; do
        IFS='|' read -r name url <<< "$svc"
        if curl -sf "$url" > /dev/null 2>&1; then
            ok "$name is healthy"
        else
            fail "$name is not reachable at $url"
            all_ok=false
        fi
    done

    if [ "$all_ok" = false ]; then
        warn "Some services are not ready. Demo results may be incomplete."
        echo -e "  Run ${BOLD}docker compose -f deploy/docker-compose.yml ps${NC} to check."
    fi
    echo ""
}

# ── Demo Functions ────────────────────────────────────────────────────────────

demo_health_check() {
    header "Health Check — All Services"
    for svc in "API Gateway|${API_URL}/health" "RADIUS Server|http://radius-server:9100/health" "Policy Engine|http://policy-engine:8082/health" "AI Engine|http://ai-engine:8081/health"; do
        IFS='|' read -r name url <<< "$svc"
        local result
        result=$(curl -sf "$url" 2>/dev/null || echo '{"status":"unreachable"}')
        echo -e "  ${BOLD}$name${NC}: $(echo "$result" | jq -c '.status // .service // .' 2>/dev/null || echo "$result")"
    done

    header "DB Schema Check"
    curl -sf "${API}/diagnostics/db-schema-check" -H "$(auth_header)" 2>/dev/null | jq '.overall_status' || fail "DB schema check failed"

    header "Topology Health Matrix"
    curl -sf "${API}/topology/health-matrix" -H "$(auth_header)" 2>/dev/null | jq '.' || fail "Topology health-matrix failed"
}

demo_radius_pap() {
    header "RADIUS PAP Authentication (radtest)"
    info "Sending Access-Request: user=${RADIUS_USER} to ${RADIUS_HOST}:1812"
    echo ""
    radtest "$RADIUS_USER" "$RADIUS_PASS" "$RADIUS_HOST" 0 "$RADIUS_SECRET" && ok "radtest completed" || fail "radtest failed"
}

demo_radius_bulk() {
    header "RADIUS Bulk Traffic (20 PAP requests)"
    local pass=0 total=20
    for i in $(seq 1 $total); do
        if radtest "$RADIUS_USER" "$RADIUS_PASS" "$RADIUS_HOST" 0 "$RADIUS_SECRET" > /dev/null 2>&1; then
            ((pass++))
        fi
        printf "\r  Sending... %d/%d" "$i" "$total"
        sleep 0.2
    done
    echo ""
    ok "Completed: ${pass}/${total} successful"
}

demo_go_radius() {
    header "Go RADIUS Protocol Tests (PAP, MAB, EAP, Accounting)"
    if [ -f /workspace/tests/integration/radius_protocol_test.go ]; then
        cd /workspace/tests/integration
        info "Running live RADIUS tests against ${RADIUS_HOST}..."
        NeuraNAC_RADIUS_HOST="$RADIUS_HOST" go test -v -run "TestRADIUS_Live" -timeout 30s 2>&1 | tail -30
        cd /workspace
    else
        fail "Go test files not found at /workspace/tests/integration/"
        info "Ensure tests/ is volume-mounted into the container"
    fi
}

demo_k6_load() {
    header "k6 API Load Test (60s, 5 VUs)"
    if [ -f /workspace/tests/load/k6_api_gateway.js ]; then
        K6_API_URL="${API_URL}" k6 run --duration 30s --vus 5 /workspace/tests/load/k6_api_gateway.js 2>&1 | tail -40
    else
        fail "k6 script not found at /workspace/tests/load/k6_api_gateway.js"
    fi
}

demo_topology() {
    header "Topology API — All 4 Views"
    get_token

    for view in physical logical dataflow legacy-nac; do
        echo -e "\n  ${BOLD}View: ${view}${NC}"
        curl -sf "${API}/topology/?view=${view}" -H "$(auth_header)" 2>/dev/null | jq '.summary // .view // .layers | keys' 2>/dev/null || fail "  ${view} view failed"
    done

    echo -e "\n  ${BOLD}Health Matrix:${NC}"
    curl -sf "${API}/topology/health-matrix" -H "$(auth_header)" 2>/dev/null | jq '.' 2>/dev/null || fail "  health-matrix failed"
}

demo_ai_chat() {
    header "AI Chat — Natural Language Queries"
    get_token

    local queries=("Show me all active sessions" "Show network topology" "Show service health matrix" "Create a policy to allow employees on VLAN 100")
    for q in "${queries[@]}"; do
        echo -e "  ${BOLD}Q:${NC} $q"
        local resp
        resp=$(curl -sf -X POST "${API}/ai/chat" \
            -H "$(auth_header)" \
            -H "Content-Type: application/json" \
            -d "{\"message\":\"${q}\"}" 2>/dev/null)
        echo "  A: $(echo "$resp" | jq -r '.response // .message // .intent // .' 2>/dev/null | head -3)"
        echo ""
    done
}

demo_legacy_nac_flow() {
    header "Legacy Integration Flow"
    get_token

    info "Creating NeuraNAC connection..."
    local conn
    conn=$(curl -sf -X POST "${API}/legacy-nac/connections" \
        -H "$(auth_header)" \
        -H "Content-Type: application/json" \
        -d '{"name":"Demo NeuraNAC","hostname":"10.10.10.1","port":443,"username":"ersadmin","password":"NeuraNACPassword","ers_enabled":true,"ers_port":9060,"event_stream_enabled":true,"verify_ssl":false,"deployment_mode":"coexistence"}' 2>/dev/null)
    local conn_id
    conn_id=$(echo "$conn" | jq -r '.id // empty' 2>/dev/null)

    if [ -n "$conn_id" ]; then
        ok "Connection created: $conn_id"

        info "Detecting NeuraNAC version..."
        curl -sf -X POST "${API}/legacy-nac/connections/${conn_id}/detect-version" -H "$(auth_header)" 2>/dev/null | jq '.version // .' || true

        info "Running full sync..."
        curl -sf -X POST "${API}/legacy-nac/connections/${conn_id}/sync" \
            -H "$(auth_header)" \
            -H "Content-Type: application/json" \
            -d '{"entity_types":["all"],"sync_type":"full","direction":"legacy_to_neuranac"}' 2>/dev/null | jq '.status // .' || true

        info "Simulating event stream event..."
        curl -sf -X POST "${API}/legacy-nac/connections/${conn_id}/event-stream/connect" -H "$(auth_header)" > /dev/null 2>&1
        curl -sf -X POST "${API}/legacy-nac/connections/${conn_id}/event-stream/simulate-event?event_type=session_created" -H "$(auth_header)" 2>/dev/null | jq '.event_type // .' || true

        ok "NeuraNAC demo flow completed"
    else
        fail "Could not create NeuraNAC connection"
        echo "  Response: $(echo "$conn" | jq -c '.' 2>/dev/null || echo "$conn")"
    fi
}

demo_sanity() {
    header "Sanity Test Suite (344 tests)"
    if [ -f /workspace/scripts/sanity_runner.py ]; then
        cd /workspace
        python3 scripts/sanity_runner.py "$@"
        cd /workspace
    else
        fail "Sanity runner not found at /workspace/scripts/sanity_runner.py"
    fi
}

demo_radsec() {
    header "RadSec (RADIUS over TLS) — Verify Listener"
    info "Connecting to ${RADIUS_HOST}:2083 via TLS..."
    echo | openssl s_client -connect "${RADIUS_HOST}:2083" 2>&1 | head -15
}

demo_full() {
    header "Running Full Demo Sequence"
    demo_health_check
    demo_radius_pap
    demo_radius_bulk
    demo_topology
    demo_ai_chat
    demo_legacy_nac_flow
    demo_radsec
    ok "Full demo sequence completed!"
    info "For load testing, run option 5 (k6) separately"
    info "For Go RADIUS tests, run option 4 separately"
}

# ── Interactive Menu ──────────────────────────────────────────────────────────

show_menu() {
    echo -e "${BOLD}Choose a demo to run:${NC}"
    echo ""
    echo -e "  ${CYAN}1)${NC}  Health Check          — All services + DB schema + topology matrix"
    echo -e "  ${CYAN}2)${NC}  RADIUS PAP Auth        — Single radtest Access-Request"
    echo -e "  ${CYAN}3)${NC}  RADIUS Bulk Traffic    — 20 PAP requests for dashboard activity"
    echo -e "  ${CYAN}4)${NC}  Go RADIUS Suite        — PAP, MAB, EAP, Accounting (Go tests)"
    echo -e "  ${CYAN}5)${NC}  k6 Load Test           — API stress test (30s, 5 VUs)"
    echo -e "  ${CYAN}6)${NC}  Topology Views         — All 4 topology tabs via API"
    echo -e "  ${CYAN}7)${NC}  AI Chat                — Natural language queries"
    echo -e "  ${CYAN}8)${NC}  Legacy Integration        — Create connection, sync, event stream"
    echo -e "  ${CYAN}9)${NC}  RadSec TLS Check       — Verify RadSec listener"
    echo -e "  ${CYAN}10)${NC} Sanity Suite            — Run all 344 tests"
    echo -e "  ${CYAN}11)${NC} Full Demo               — Run all demos in sequence"
    echo ""
    echo -e "  ${CYAN}s)${NC}  Shell                  — Drop into bash"
    echo -e "  ${CYAN}q)${NC}  Quit"
    echo ""
}

interactive() {
    banner
    wait_for_services
    get_token

    while true; do
        show_menu
        read -rp "$(echo -e "${BOLD}Select [1-11, s, q]:${NC} ")" choice
        case "$choice" in
            1)  demo_health_check ;;
            2)  demo_radius_pap ;;
            3)  demo_radius_bulk ;;
            4)  demo_go_radius ;;
            5)  demo_k6_load ;;
            6)  demo_topology ;;
            7)  demo_ai_chat ;;
            8)  demo_legacy_nac_flow ;;
            9)  demo_radsec ;;
            10) demo_sanity ;;
            11) demo_full ;;
            s|S) echo -e "\n${BOLD}Type 'exit' to return to the menu${NC}\n"; bash; ;;
            q|Q) echo -e "\n${GREEN}Goodbye!${NC}\n"; exit 0 ;;
            *)  warn "Invalid choice: $choice" ;;
        esac
        echo ""
        read -rp "Press Enter to continue..." _
        echo ""
    done
}

# ── CLI mode (run a specific demo non-interactively) ─────────────────────────
if [ $# -gt 0 ]; then
    case "$1" in
        health)     get_token; demo_health_check ;;
        pap)        demo_radius_pap ;;
        bulk)       demo_radius_bulk ;;
        go-radius)  demo_go_radius ;;
        k6)         demo_k6_load ;;
        topology)   get_token; demo_topology ;;
        ai)         get_token; demo_ai_chat ;;
        legacy-nac)  get_token; demo_legacy_nac_flow ;;
        radsec)     demo_radsec ;;
        sanity)     get_token; shift; demo_sanity "$@" ;;
        full)       get_token; demo_full ;;
        *)          echo "Usage: $0 {health|pap|bulk|go-radius|k6|topology|ai|legacy-nac|radsec|sanity|full}"; exit 1 ;;
    esac
else
    interactive
fi
