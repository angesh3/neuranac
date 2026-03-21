.PHONY: build test lint run stop proto docker-build migrate-up migrate-down seed clean help

# Variables
COMPOSE := docker-compose
COMPOSE_FILE := deploy/docker-compose.yml
GO_SERVICES := radius-server sync-engine ingestion-collector
PY_SERVICES := api-gateway policy-engine ai-engine neuranac-bridge
PROTO_DIR := proto
PROTO_OUT_GO := services
PROTO_OUT_PY := services

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ─── Build ───────────────────────────────────────────────────────────────────

build: build-go build-py build-web ## Build all services

build-go: ## Build Go services
	@for svc in $(GO_SERVICES); do \
		echo "Building $$svc..."; \
		cd services/$$svc && go build -o bin/$$svc ./cmd/server/ && cd ../..; \
	done

build-py: ## Install Python dependencies
	@for svc in $(PY_SERVICES); do \
		echo "Installing $$svc dependencies..."; \
		cd services/$$svc && pip install -r requirements.txt -q && cd ../..; \
	done

build-web: ## Build React dashboard
	cd web && npm install && npm run build

# ─── Test ────────────────────────────────────────────────────────────────────

test: test-go test-py test-web ## Run all tests

test-go: ## Run Go tests
	@for svc in $(GO_SERVICES); do \
		echo "Testing $$svc..."; \
		cd services/$$svc && go test ./... -v -cover && cd ../..; \
	done

test-py: ## Run Python tests
	@for svc in $(PY_SERVICES); do \
		echo "Testing $$svc..."; \
		cd services/$$svc && python -m pytest tests/ -v --cov=app && cd ../..; \
	done

test-web: ## Run React tests
	cd web && npm run test

test-integration: ## Run integration tests
	cd tests/integration && python -m pytest -v

test-e2e: ## Run E2E tests
	cd tests/e2e && npx playwright test

test-load: ## Run load tests
	cd tests/load && k6 run radius-load.js

# ─── Lint ────────────────────────────────────────────────────────────────────

lint: lint-go lint-py lint-web ## Lint all code

lint-go: ## Lint Go code
	@for svc in $(GO_SERVICES); do \
		echo "Linting $$svc..."; \
		cd services/$$svc && golangci-lint run ./... && cd ../..; \
	done

lint-py: ## Lint Python code
	@for svc in $(PY_SERVICES); do \
		echo "Linting $$svc..."; \
		cd services/$$svc && ruff check app/ && cd ../..; \
	done

lint-web: ## Lint React code
	cd web && npm run lint

# ─── Run ─────────────────────────────────────────────────────────────────────

run: ## Start all services with docker-compose
	$(COMPOSE) -f $(COMPOSE_FILE) up -d

stop: ## Stop all services
	$(COMPOSE) -f $(COMPOSE_FILE) down

restart: stop run ## Restart all services

logs: ## Tail logs from all services
	$(COMPOSE) -f $(COMPOSE_FILE) logs -f

# ─── Proto ───────────────────────────────────────────────────────────────────

proto: proto-go proto-py ## Generate all gRPC stubs

proto-go: ## Generate Go gRPC stubs
	@echo "Generating Go protobuf stubs..."
	@for proto_file in $(PROTO_DIR)/*.proto; do \
		protoc --go_out=. --go-grpc_out=. $$proto_file; \
	done

proto-py: ## Generate Python gRPC stubs
	@echo "Generating Python protobuf stubs..."
	@python -m grpc_tools.protoc -I$(PROTO_DIR) \
		--python_out=services/api-gateway/app/generated \
		--grpc_python_out=services/api-gateway/app/generated \
		$(PROTO_DIR)/*.proto

# ─── Docker ──────────────────────────────────────────────────────────────────

docker-build: ## Build all Docker images
	@for svc in $(GO_SERVICES); do \
		echo "Building Docker image for $$svc..."; \
		docker build -t neuranac/$$svc:latest -f services/$$svc/Dockerfile services/$$svc; \
	done
	@for svc in $(PY_SERVICES); do \
		echo "Building Docker image for $$svc..."; \
		docker build -t neuranac/$$svc:latest -f services/$$svc/Dockerfile services/$$svc; \
	done
	docker build -t neuranac/web:latest -f web/Dockerfile web

docker-push: ## Push Docker images
	@for svc in $(GO_SERVICES) $(PY_SERVICES) web; do \
		docker push neuranac/$$svc:latest; \
	done

# ─── Database ────────────────────────────────────────────────────────────────

migrate-up: ## Run database migrations (all pending)
	python scripts/migrate.py upgrade

migrate-down: ## Rollback last migration
	python scripts/migrate.py rollback

migrate-status: ## Show migration status
	python scripts/migrate.py status

migrate-validate: ## Validate migration checksums
	python scripts/migrate.py validate

seed: ## Load seed data
	cd services/api-gateway && python -m app.database.seeds

# ─── Setup ───────────────────────────────────────────────────────────────────

setup: ## One-command dev environment setup
	./scripts/setup.sh

generate-certs: ## Generate development TLS certificates
	./scripts/generate-certs.sh

# ─── Demo ────────────────────────────────────────────────────────────────────

demo-record: ## Record sales demo video (requires stack + demo-tools)
	@DEMO_PASSWORD=$$(docker compose -f deploy/docker-compose.yml exec -T api-gateway python -c "try:p=__import__('pathlib').Path('/tmp/neuranac-initial-password');print([l.split('=',1)[1] for l in p.read_text().splitlines() if l.startswith('password=')][0]);except:print('admin')" 2>/dev/null || echo "admin") \
		node tests/e2e/sales-demo-recording.mjs

demo-audio: ## Generate demo narration audio (macOS say or Piper)
	./scripts/generate-demo-audio.sh

demo-build: ## Full sales demo: record + audio + mux → MP4
	./scripts/build-sales-demo.sh

# ─── Clean ───────────────────────────────────────────────────────────────────

clean: ## Clean build artifacts
	@for svc in $(GO_SERVICES); do \
		rm -rf services/$$svc/bin; \
	done
	rm -rf web/dist
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
