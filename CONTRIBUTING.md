# Contributing to NeuraNAC

Thank you for your interest in contributing to the NeuraNAC (NeuraNAC) project.

## Development Setup

### Prerequisites

- **Go** 1.22+
- **Python** 3.12+
- **Node.js** 20+
- **Docker** & **Docker Compose**
- **Helm** 3.14+

### Quick Start

```bash
# Clone the repository
git clone <repo-url> && cd NeuraNAC

# Start infrastructure (PostgreSQL, Redis, NATS)
cd deploy && docker compose up -d postgres redis nats

# Run database migrations
bash scripts/setup.sh

# Start services (pick one)
cd services/api-gateway && pip install -r requirements.txt && uvicorn app.main:app --port 8080
cd services/radius-server && go run ./cmd/radius/
cd web && npm ci && npm run dev
```

## Repository Structure

| Directory | Description |
|---|---|
| `services/radius-server` | Go — RADIUS/TACACS+ authentication server |
| `services/api-gateway` | Python (FastAPI) — REST API gateway |
| `services/policy-engine` | Python (FastAPI) — Policy evaluation + gRPC |
| `services/ai-engine` | Python (FastAPI) — ML profiling, risk scoring |
| `services/sync-engine` | Go — Hub-spoke replication engine |
| `services/neuranac-bridge` | Python (FastAPI) — Pluggable adapter bridge (NeuraNAC, NeuraNAC-to-NeuraNAC, REST) |
| `web` | React + TypeScript — Dashboard UI |
| `deploy/helm/neuranac` | Helm chart for Kubernetes deployment |
| `deploy/docker-compose.yml` | Local development compose stack |
| `tests/` | Integration, E2E, and load tests |

## Code Standards

### Go
- Run `golangci-lint run` before committing
- Minimum test coverage: **70%**
- Use `zap` for structured logging

### Python
- Run `ruff check` before committing
- Minimum test coverage: **70%**
- Use `structlog` for structured logging

### TypeScript / React
- Run `npm run lint` before committing
- Use React Query for server state
- Use Zustand for client state

## Testing

```bash
# Go unit tests
cd services/radius-server && go test ./... -race -v

# Python tests
cd services/api-gateway && python -m pytest tests/ -v --cov=app

# Web tests
cd web && npm test

# Integration tests
cd tests/integration && go test -v -tags integration ./...

# E2E tests (requires running frontend)
cd tests/e2e && npx playwright test

# Load tests
k6 run tests/load/k6_api_gateway.js
```

## Pull Request Process

1. Create a feature branch from `develop`
2. Write tests for new functionality
3. Ensure all CI checks pass (lint, test, security scan)
4. Keep PRs focused — one logical change per PR
5. Update documentation if you change public APIs or configuration

## Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(radius): add EAP-FAST support
fix(api): correct rate limit header calculation
docs: update deployment guide
test(handler): add EAP-TLS state machine tests
```

## Security

- Never commit secrets, API keys, or passwords
- Use environment variables for all sensitive configuration
- Report security vulnerabilities privately — do not open public issues
