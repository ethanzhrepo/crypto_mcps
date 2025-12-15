# Hubrium MCP Server Test Makefile

.PHONY: help start stop restart build build-prod clean clean-prod test test-unit test-integration test-live test-live-free test-cov clean logs shell

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

start: ## Start MCP HTTP server (production)
	docker-compose -f docker-compose.yml up -d
	@echo ""
	@echo "✅ MCP HTTP Server started on http://localhost:8001"
	@echo "   Health check: curl http://localhost:8001/health"
	@echo "   Tools list:   curl http://localhost:8001/tools"
	@echo "   Tool registry: curl http://localhost:8001/tools/registry"
	@echo "   Tool detail:  curl http://localhost:8001/tools/{tool_name}"
	@echo "   Logs:         make logs"
	@echo "   Stop:         make stop"

stop: ## Stop MCP HTTP server (production)
	docker-compose -f docker-compose.yml down

restart: ## Restart MCP HTTP server
	$(MAKE) stop
	$(MAKE) start

build: ## Build test containers
	docker-compose -f docker-compose.test.yml build --no-cache

build-prod: ## Build production containers
	docker-compose -f docker-compose.yml build --no-cache

test: ## Run all tests
	./run-tests.sh

test-unit: ## Run unit tests only
	./run-tests.sh -m unit

test-integration: ## Run integration tests only
	./run-tests.sh -m integration

test-live: ## Run live API tests (requires real API keys)
	./run-tests.sh -m live

test-live-free: ## Run live tests with free APIs only (no keys required)
	./run-tests.sh -m live_free

test-all: ## Run all tests (unit + integration + live)
	./run-tests.sh

test-cov: ## Run tests with coverage report
	./run-tests.sh --cov=src --cov-report=html:/app/htmlcov --cov-report=term-missing

test-failed: ## Re-run last failed tests
	./run-tests.sh --lf

test-verbose: ## Run tests with verbose output
	./run-tests.sh -vvs

test-pattern: ## Run tests matching pattern (usage: make test-pattern PATTERN=crypto)
	./run-tests.sh -k "$(PATTERN)"

clean: ## Remove test containers and volumes
	docker-compose -f docker-compose.test.yml down -v --remove-orphans
	rm -rf reports/*

clean-prod: ## Remove production containers and volumes
	docker-compose -f docker-compose.yml down -v --remove-orphans

logs: ## Show test container logs
	docker-compose -f docker-compose.test.yml logs -f

logs-prod:
	docker-compose -f docker-compose.yml logs -f

shell: ## Open shell in test container
	docker-compose -f docker-compose.test.yml run --rm mcp-test /bin/bash

redis-cli: ## Connect to test Redis
	docker-compose -f docker-compose.test.yml exec redis-test redis-cli
