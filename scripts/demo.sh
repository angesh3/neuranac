#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# NeuraNAC Demo — Zero-Install Setup & Interactive Runner
#
# This script sets up the entire NeuraNAC platform AND all demo client tools
# inside Docker containers. The only prerequisite is Docker Desktop.
#
# Usage:
#   ./scripts/demo.sh              # Full setup + interactive demo menu
#   ./scripts/demo.sh --setup      # Setup only (start stack + build demo tools)
#   ./scripts/demo.sh --run        # Launch interactive demo runner (skip setup)
#   ./scripts/demo.sh --run pap    # Run a specific demo non-interactively
#   ./scripts/demo.sh --shell      # Open a shell inside the demo-tools container
#   ./scripts/demo.sh --stop       # Stop everything
#   ./scripts/demo.sh --monitoring # Include Prometheus + Grafana
#
# No Go, Python, radtest, or k6 installation needed on your Mac.
# Everything runs inside containers.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="$PROJECT_ROOT/deploy/docker-compose.yml"
COMPOSE_CMD="docker compose -f $COMPOSE_FILE"

# ── Colors ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
fail() { echo -e "  ${RED}✗${NC} $1"; }
info() { echo -e "  ${BLUE}ℹ${NC} $1"; }
warn() { echo -e "  ${YELLOW}⚠${NC} $1"; }

banner() {
    echo ""
    echo -e "${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║${NC}                                                              ${CYAN}║${NC}"
    echo -e "${CYAN}║${NC}  ${BOLD}NeuraNAC — NeuraNAC${NC}                                    ${CYAN}║${NC}"
    echo -e "${CYAN}║${NC}  ${BOLD}Zero-Install Demo${NC}                                          ${CYAN}║${NC}"
    echo -e "${CYAN}║${NC}                                                              ${CYAN}║${NC}"
    echo -e "${CYAN}║${NC}  Only requires: Docker Desktop (8 GB RAM)                    ${CYAN}║${NC}"
    echo -e "${CYAN}║${NC}  Includes: radtest, Go RADIUS, k6, Python, curl, jq          ${CYAN}║${NC}"
    echo -e "${CYAN}║${NC}                                                              ${CYAN}║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

# ── Prerequisite check ────────────────────────────────────────────────────────
check_docker() {
    if ! command -v docker >/dev/null 2>&1; then
        fail "Docker is not installed. Please install Docker Desktop."
        echo "  https://www.docker.com/products/docker-desktop/"
        exit 1
    fi

    if ! docker info >/dev/null 2>&1; then
        fail "Docker daemon is not running. Please start Docker Desktop."
        exit 1
    fi

    # Check memory allocation
    local mem
    mem=$(docker info --format '{{.MemTotal}}' 2>/dev/null || echo "0")
    local mem_gb=$((mem / 1073741824))
    if [ "$mem_gb" -lt 6 ]; then
        warn "Docker has ${mem_gb}GB RAM. Recommend at least 8GB for full demo."
        warn "Docker Desktop → Settings → Resources → Memory → 8 GB"
    else
        ok "Docker has ${mem_gb}GB RAM allocated"
    fi
}

# ── Setup: NeuraNAC stack + demo tools ─────────────────────────────────────────────
setup_stack() {
    local monitoring="${1:-false}"

    echo -e "\n${BOLD}Step 1/5: Checking prerequisites${NC}"
    check_docker

    echo -e "\n${BOLD}Step 2/5: Setting up environment${NC}"
    cd "$PROJECT_ROOT"
    if [ ! -f .env ]; then
        if [ -f .env.example ]; then
            cp .env.example .env
            ok "Created .env from .env.example"
        else
            ok "No .env.example found — using defaults"
        fi
    else
        ok ".env already exists"
    fi

    # Generate TLS certs if needed
    local cert_dir="deploy/certs"
    if [ ! -f "$cert_dir/ca.crt" ]; then
        info "Generating development TLS certificates..."
        mkdir -p "$cert_dir"
        openssl req -x509 -newkey rsa:4096 -keyout "$cert_dir/ca.key" -out "$cert_dir/ca.crt" \
            -days 3650 -nodes -subj "/CN=NeuraNAC Dev CA" 2>/dev/null
        openssl req -newkey rsa:2048 -keyout "$cert_dir/server.key" -out "$cert_dir/server.csr" \
            -nodes -subj "/CN=localhost" 2>/dev/null
        openssl x509 -req -in "$cert_dir/server.csr" -CA "$cert_dir/ca.crt" -CAkey "$cert_dir/ca.key" \
            -CAcreateserial -out "$cert_dir/server.crt" -days 365 2>/dev/null
        cp "$cert_dir/server.crt" "$cert_dir/radsec.crt"
        cp "$cert_dir/server.key" "$cert_dir/radsec.key"
        ok "TLS certificates generated"
    else
        ok "TLS certificates already exist"
    fi

    echo -e "\n${BOLD}Step 3/5: Starting infrastructure (PostgreSQL, Redis, NATS)${NC}"
    $COMPOSE_CMD up -d postgres redis nats

    info "Waiting for PostgreSQL..."
    for i in $(seq 1 30); do
        if $COMPOSE_CMD exec -T postgres pg_isready -U neuranac -q 2>/dev/null; then
            ok "PostgreSQL is ready"
            break
        fi
        [ "$i" -eq 30 ] && { fail "PostgreSQL did not start in time"; exit 1; }
        sleep 2
    done

    echo -e "\n${BOLD}Step 4/5: Running migrations + building services${NC}"
    for migration in database/migrations/V*.sql; do
        if [ -f "$migration" ]; then
            info "Applying $(basename "$migration")..."
            $COMPOSE_CMD exec -T postgres psql -U neuranac -d neuranac < "$migration" 2>/dev/null || true
        fi
    done
    if [ -f database/seeds/seed_data.sql ]; then
        info "Loading seed data..."
        $COMPOSE_CMD exec -T postgres psql -U neuranac -d neuranac < database/seeds/seed_data.sql 2>/dev/null || true
    fi

    info "Building and starting all NeuraNAC services..."
    $COMPOSE_CMD build
    $COMPOSE_CMD up -d

    # Start monitoring if requested
    if [ "$monitoring" = "true" ]; then
        info "Starting monitoring stack (Prometheus + Grafana)..."
        $COMPOSE_CMD --profile monitoring up -d
    fi

    echo -e "\n${BOLD}Step 5/5: Building & starting demo-tools container${NC}"
    info "Building demo-tools image (first time may take 2-3 minutes)..."
    $COMPOSE_CMD --profile demo build demo-tools
    $COMPOSE_CMD --profile demo up -d demo-tools
    ok "Demo-tools container started"

    # Wait for API Gateway
    info "Waiting for API Gateway..."
    for i in $(seq 1 30); do
        if curl -sf http://localhost:8080/health > /dev/null 2>&1; then
            ok "API Gateway is ready"
            break
        fi
        [ "$i" -eq 30 ] && warn "API Gateway not responding yet — it may still be starting"
        sleep 2
    done

    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║${NC}  ${BOLD}NeuraNAC Setup Complete!${NC}                                        ${GREEN}║${NC}"
    echo -e "${GREEN}╠══════════════════════════════════════════════════════════════╣${NC}"
    echo -e "${GREEN}║${NC}                                                              ${GREEN}║${NC}"
    echo -e "${GREEN}║${NC}  Dashboard:    ${BOLD}http://localhost:3001${NC}                         ${GREEN}║${NC}"
    echo -e "${GREEN}║${NC}  Topology:     ${BOLD}http://localhost:3001/topology${NC}                ${GREEN}║${NC}"
    echo -e "${GREEN}║${NC}  API Docs:     ${BOLD}http://localhost:8080/api/docs${NC}                ${GREEN}║${NC}"
    if [ "$monitoring" = "true" ]; then
    echo -e "${GREEN}║${NC}  Prometheus:   ${BOLD}http://localhost:9092${NC}                         ${GREEN}║${NC}"
    echo -e "${GREEN}║${NC}  Grafana:      ${BOLD}http://localhost:3000${NC}                         ${GREEN}║${NC}"
    fi
    echo -e "${GREEN}║${NC}                                                              ${GREEN}║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

# ── Run interactive demo inside the container ─────────────────────────────────
run_demo() {
    local args="${*:-}"

    # Check if demo-tools container is running
    if ! docker ps --format '{{.Names}}' | grep -q "neuranac-demo-tools"; then
        warn "Demo-tools container is not running."
        info "Starting it now..."
        $COMPOSE_CMD --profile demo up -d demo-tools
        sleep 3
    fi

    if [ -n "$args" ]; then
        docker exec -it neuranac-demo-tools /opt/demo/demo-runner.sh $args
    else
        docker exec -it neuranac-demo-tools /opt/demo/demo-runner.sh
    fi
}

# ── Open a shell inside demo-tools ────────────────────────────────────────────
open_shell() {
    if ! docker ps --format '{{.Names}}' | grep -q "neuranac-demo-tools"; then
        warn "Demo-tools container is not running. Starting it..."
        $COMPOSE_CMD --profile demo up -d demo-tools
        sleep 3
    fi
    echo -e "${BOLD}Opening shell in demo-tools container...${NC}"
    echo -e "  All tools available: radtest, go, k6, python3, curl, jq, openssl"
    echo -e "  NeuraNAC services accessible via Docker DNS (api-gateway, radius-server, etc.)"
    echo -e "  Type ${BOLD}exit${NC} to leave.\n"
    docker exec -it neuranac-demo-tools bash
}

# ── Stop everything ───────────────────────────────────────────────────────────
stop_all() {
    echo -e "${BOLD}Stopping all NeuraNAC services and demo tools...${NC}"
    $COMPOSE_CMD --profile demo --profile monitoring down
    ok "All containers stopped"
}

# ── Status check ──────────────────────────────────────────────────────────────
show_status() {
    echo -e "\n${BOLD}NeuraNAC Container Status${NC}\n"
    $COMPOSE_CMD --profile demo --profile monitoring ps 2>/dev/null || $COMPOSE_CMD ps
    echo ""

    echo -e "${BOLD}Service Health${NC}\n"
    for svc in "API Gateway|http://localhost:8080/health" "RADIUS Server|http://localhost:9100/health" "Policy Engine|http://localhost:8082/health" "AI Engine|http://localhost:8081/health"; do
        IFS='|' read -r name url <<< "$svc"
        if curl -sf "$url" > /dev/null 2>&1; then
            ok "$name"
        else
            fail "$name"
        fi
    done
    echo ""
}

# ── Usage ─────────────────────────────────────────────────────────────────────
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  (no args)          Full setup + interactive demo menu"
    echo "  --setup            Setup only (start NeuraNAC stack + build demo tools)"
    echo "  --monitoring       Include Prometheus + Grafana in setup"
    echo "  --run [DEMO]       Launch interactive demo runner (or run specific demo)"
    echo "                     Demos: health, pap, bulk, go-radius, k6, topology,"
    echo "                            ai, legacy-nac, radsec, sanity, full"
    echo "  --shell            Open a bash shell in the demo-tools container"
    echo "  --status           Show container and service health status"
    echo "  --stop             Stop all containers"
    echo "  --help             Show this help"
    echo ""
    echo "Examples:"
    echo "  ./scripts/demo.sh                      # Full setup + interactive menu"
    echo "  ./scripts/demo.sh --monitoring          # Setup with Grafana/Prometheus"
    echo "  ./scripts/demo.sh --run pap             # Quick RADIUS PAP test"
    echo "  ./scripts/demo.sh --run full            # Run all demos in sequence"
    echo "  ./scripts/demo.sh --run sanity          # Run 344 sanity tests"
    echo "  ./scripts/demo.sh --shell               # Explore with all tools"
    echo ""
}

# ── Main ──────────────────────────────────────────────────────────────────────
main() {
    cd "$PROJECT_ROOT"
    local monitoring=false

    # Parse --monitoring from any position
    local args=()
    for arg in "$@"; do
        if [ "$arg" = "--monitoring" ]; then
            monitoring=true
        else
            args+=("$arg")
        fi
    done
    set -- "${args[@]+"${args[@]}"}"

    case "${1:-}" in
        --setup)
            banner
            setup_stack "$monitoring"
            ;;
        --run)
            shift
            run_demo "$@"
            ;;
        --shell)
            open_shell
            ;;
        --status)
            show_status
            ;;
        --stop)
            stop_all
            ;;
        --help|-h)
            usage
            ;;
        "")
            # Default: full setup + interactive demo
            banner
            setup_stack "$monitoring"
            echo -e "${BOLD}Launching interactive demo runner...${NC}\n"
            sleep 2
            run_demo
            ;;
        *)
            fail "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
}

main "$@"
