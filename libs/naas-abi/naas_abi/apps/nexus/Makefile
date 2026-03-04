.PHONY: help up down restart build clean install test lint format check db-migrate db-seed db-reset logs api web kill-ports status

# Colors for output
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m # No Color

help: ## Show this help message
	@echo "$(BLUE)NEXUS Platform - Development Commands$(NC)"
	@echo ""
	@echo "$(GREEN)Quick Start:$(NC)"
	@echo "  make install    Install all dependencies"
	@echo "  make up         Start dev servers (API + Web)"
	@echo "  make down       Stop all servers"
	@echo "  make restart    Restart servers"
	@echo ""
	@echo "$(GREEN)Available Commands:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-15s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(BLUE)Full reference:$(NC) docs/reference/MAKEFILE.md"

# =============================================================================
# Installation & Dependencies
# =============================================================================

install: ## Install all dependencies (API + Web)
	@echo "$(BLUE)Installing frontend dependencies...$(NC)"
	@pnpm install
	@echo "$(BLUE)Installing API dependencies...$(NC)"
	@cd apps/api && uv sync
	@echo "$(GREEN)✓ All dependencies installed$(NC)"

install-api: ## Install API dependencies only
	@echo "$(BLUE)Installing API dependencies...$(NC)"
	@cd apps/api && uv sync
	@echo "$(GREEN)✓ API dependencies installed$(NC)"

install-web: ## Install Web dependencies only
	@echo "$(BLUE)Installing Web dependencies...$(NC)"
	@pnpm install
	@echo "$(GREEN)✓ Web dependencies installed$(NC)"

# =============================================================================
# Docker & Database
# =============================================================================

db-up: ## Start PostgreSQL (Docker)
	@echo "$(BLUE)Starting PostgreSQL...$(NC)"
	@if ! docker info > /dev/null 2>&1; then \
		echo "$(YELLOW)Docker is not running. Starting Docker...$(NC)"; \
		open -a Docker && \
		echo "$(YELLOW)Waiting for Docker to start...$(NC)" && \
		for i in {1..30}; do \
			if docker info > /dev/null 2>&1; then \
				echo "$(GREEN)✓ Docker started$(NC)"; \
				break; \
			fi; \
			sleep 2; \
			if [ $$i -eq 30 ]; then \
				echo "$(RED)✗ Docker failed to start after 60s$(NC)"; \
				echo "$(YELLOW)Please start Docker manually and run 'make db-up' again$(NC)"; \
				exit 1; \
			fi; \
		done; \
	fi
	@docker-compose up -d postgres
	@echo "$(GREEN)✓ PostgreSQL started$(NC)"
	@echo "Waiting for PostgreSQL to be ready..."
	@sleep 3
	@docker-compose exec -T postgres pg_isready -U nexus || (echo "$(YELLOW)Still starting...$(NC)" && sleep 3)
	@echo "$(GREEN)✓ PostgreSQL ready$(NC)"

db-down: ## Stop PostgreSQL
	@echo "$(YELLOW)Stopping PostgreSQL...$(NC)"
	@docker-compose down
	@echo "$(GREEN)✓ PostgreSQL stopped$(NC)"

db-logs: ## Show PostgreSQL logs
	@docker-compose logs -f postgres

db-shell: ## Open PostgreSQL shell
	@docker-compose exec postgres psql -U nexus -d nexus

db-reset: ## Reset database (WARNING: deletes all data)
	@echo "$(RED)WARNING: This will delete all data!$(NC)"
	@read -p "Are you sure? (yes/no): " confirm && [ "$$confirm" = "yes" ] || exit 1
	@docker-compose down -v
	@$(MAKE) db-up
	@sleep 3
	@$(MAKE) db-migrate
	@$(MAKE) db-seed

# =============================================================================
# Database Migrations
# =============================================================================

db-migrate: ## Run database migrations
	@echo "$(BLUE)Running database migrations...$(NC)"
	@cd apps/api && uv run python -c "import asyncio; from app.core.database import init_db; asyncio.run(init_db())"
	@echo "$(GREEN)✓ Migrations complete$(NC)"

db-seed: ## Seed database with demo data
	@echo "$(BLUE)Seeding database...$(NC)"
	@cd apps/api && uv run python seed.py
	@echo "$(GREEN)✓ Database seeded$(NC)"

db-seed-reset: ## Reset demo tables and reseed (destructive)
	@echo "$(RED)WARNING: This will TRUNCATE demo tables and reseed$(NC)"
	@cd apps/api && uv run python seed.py --reset
	@echo "$(GREEN)✓ Demo tables reset and reseeded$(NC)"

# =============================================================================
# Development Servers (updated)
# =============================================================================

up: kill-ports ## Start dev servers (API + Web)
	@echo "$(BLUE)Checking Docker & PostgreSQL...$(NC)"
	@if ! docker info > /dev/null 2>&1; then \
		echo "$(YELLOW)Docker not running - starting it now...$(NC)"; \
		$(MAKE) db-up; \
	elif ! docker-compose ps postgres | grep -q "Up"; then \
		echo "$(YELLOW)PostgreSQL not running - starting it now...$(NC)"; \
		$(MAKE) db-up; \
	else \
		echo "$(GREEN)✓ PostgreSQL is running$(NC)"; \
	fi
	@./dev.sh

down: ## Stop all dev servers
	@echo "$(YELLOW)Stopping dev servers...$(NC)"
	@pkill -f "pnpm dev" || true
	@pkill -f "next dev" || true
	@pkill -f "uvicorn" || true
	@$(MAKE) kill-ports
	@echo "$(GREEN)✓ Servers stopped$(NC)"

restart: down ## Restart all dev servers
	@sleep 2
	@$(MAKE) up

api: kill-ports ## Start API server only
	@echo "$(BLUE)Starting API server...$(NC)"
	@cd apps/api && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

web: ## Start Web server only
	@echo "$(BLUE)Starting Web server...$(NC)"
	@cd apps/web && pnpm dev

kill-ports: ## Kill processes on ports 3000 and 8000
	@echo "$(YELLOW)Checking for processes on ports 3000 and 8000...$(NC)"
	@lsof -ti:3000 | xargs kill -9 2>/dev/null || true
	@lsof -ti:8000 | xargs kill -9 2>/dev/null || true
	@sleep 1

status: ## Show server status
	@echo "$(BLUE)Server Status:$(NC)"
	@echo ""
	@echo -n "$(YELLOW)API (8000):$(NC)  "
	@lsof -ti:8000 > /dev/null 2>&1 && echo "$(GREEN)Running$(NC)" || echo "$(RED)Stopped$(NC)"
	@echo -n "$(YELLOW)Web (3000):$(NC)  "
	@lsof -ti:3000 > /dev/null 2>&1 && echo "$(GREEN)Running$(NC)" || echo "$(RED)Stopped$(NC)"
	@echo ""
	@lsof -ti:8000 > /dev/null 2>&1 && echo "  → API:  http://localhost:8000" || true
	@lsof -ti:3000 > /dev/null 2>&1 && echo "  → Web:  http://localhost:3000" || true
	@lsof -ti:8000 > /dev/null 2>&1 && echo "  → Docs: http://localhost:8000/docs" || true

# =============================================================================
# Build & Clean
# =============================================================================

build: ## Build production bundles
	@echo "$(BLUE)Building production bundles...$(NC)"
	@pnpm build
	@echo "$(GREEN)✓ Build complete$(NC)"

clean: ## Clean all build artifacts and dependencies
	@echo "$(YELLOW)Cleaning build artifacts...$(NC)"
	@rm -rf node_modules apps/web/.next apps/web/node_modules apps/api/.pytest_cache apps/api/__pycache__ apps/api/app/__pycache__
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@echo "$(GREEN)✓ Cleaned$(NC)"

clean-cache: ## Clean Next.js cache only
	@echo "$(YELLOW)Cleaning Next.js cache...$(NC)"
	@rm -rf apps/web/.next
	@echo "$(GREEN)✓ Cache cleaned$(NC)"

# =============================================================================
# Database (removed - see Docker & Database section above)
# =============================================================================

# =============================================================================
# Testing & Quality
# =============================================================================

test: db-up ## Run all tests (requires PostgreSQL)
	@echo "$(BLUE)Running tests...$(NC)"
	@cd apps/api && uv run pytest tests/ -v
	@echo "$(GREEN)✓ Tests complete$(NC)"

test-watch: ## Run tests in watch mode
	@echo "$(BLUE)Running tests in watch mode...$(NC)"
	@cd apps/api && uv run pytest tests/ -v --lf --tb=short -x

test-cov: ## Run tests with coverage report
	@echo "$(BLUE)Running tests with coverage...$(NC)"
	@cd apps/api && uv run pytest tests/ --cov=app --cov-report=term-missing --cov-report=html
	@echo "$(GREEN)✓ Coverage report generated in apps/api/htmlcov/$(NC)"

lint: ## Run linters (API + Web)
	@echo "$(BLUE)Running linters...$(NC)"
	@echo "$(YELLOW)API:$(NC)"
	@cd apps/api && uv run ruff check .
	@echo "$(YELLOW)Web:$(NC)"
	@cd apps/web && pnpm lint
	@echo "$(GREEN)✓ Linting complete$(NC)"

lint-fix: ## Fix linting issues
	@echo "$(BLUE)Fixing linting issues...$(NC)"
	@cd apps/api && uv run ruff check --fix .
	@cd apps/web && pnpm lint --fix
	@echo "$(GREEN)✓ Fixed$(NC)"

format: ## Format code (API + Web)
	@echo "$(BLUE)Formatting code...$(NC)"
	@cd apps/api && uv run ruff format .
	@pnpm format
	@echo "$(GREEN)✓ Formatted$(NC)"

typecheck: ## Run type checking
	@echo "$(BLUE)Running type checks...$(NC)"
	@cd apps/api && uv run mypy app/
	@pnpm typecheck
	@echo "$(GREEN)✓ Type checks complete$(NC)"

check: lint typecheck test ## Run all checks (lint + typecheck + test)

# =============================================================================
# Logs & Debugging
# =============================================================================

logs: ## Show recent logs
	@echo "$(BLUE)Recent logs (last 50 lines):$(NC)"
	@tail -50 apps/api/logs/*.log 2>/dev/null || echo "No logs found"

logs-api: ## Tail API logs
	@echo "$(BLUE)Tailing API logs...$(NC)"
	@tail -f apps/api/logs/*.log 2>/dev/null || echo "No API logs found"

logs-clear: ## Clear all logs
	@echo "$(YELLOW)Clearing logs...$(NC)"
	@rm -rf apps/api/logs/*.log
	@echo "$(GREEN)✓ Logs cleared$(NC)"

# =============================================================================
# Production
# =============================================================================

prod-build: ## Build for production
	@echo "$(BLUE)Building for production...$(NC)"
	@NODE_ENV=production pnpm build
	@echo "$(GREEN)✓ Production build complete$(NC)"

prod-test: ## Run production smoke tests
	@echo "$(BLUE)Running production smoke tests...$(NC)"
	@cd apps/api && ENVIRONMENT=production uv run pytest tests/test_auth.py -v
	@echo "$(GREEN)✓ Smoke tests passed$(NC)"

# =============================================================================
# Docker (if docker-compose.yml exists)
# =============================================================================

docker-up: ## Start services with Docker
	@echo "$(BLUE)Starting Docker services...$(NC)"
	@docker-compose up -d
	@echo "$(GREEN)✓ Docker services started$(NC)"

docker-down: ## Stop Docker services
	@echo "$(YELLOW)Stopping Docker services...$(NC)"
	@docker-compose down
	@echo "$(GREEN)✓ Docker services stopped$(NC)"

docker-logs: ## Show Docker logs
	@docker-compose logs -f

docker-rebuild: ## Rebuild Docker images
	@echo "$(BLUE)Rebuilding Docker images...$(NC)"
	@docker-compose build --no-cache
	@echo "$(GREEN)✓ Docker images rebuilt$(NC)"

# =============================================================================
# Utilities
# =============================================================================

env-check: ## Check environment setup
	@echo "$(BLUE)Environment Check:$(NC)"
	@echo ""
	@echo -n "$(YELLOW)Node.js:$(NC)       "
	@node --version || echo "$(RED)Not installed$(NC)"
	@echo -n "$(YELLOW)PNPM:$(NC)          "
	@pnpm --version || echo "$(RED)Not installed$(NC)"
	@echo -n "$(YELLOW)Python:$(NC)        "
	@python3 --version || echo "$(RED)Not installed$(NC)"
	@echo -n "$(YELLOW)uv:$(NC)            "
	@uv --version || echo "$(RED)Not installed$(NC)"
	@echo -n "$(YELLOW)Docker:$(NC)        "
	@docker --version 2>/dev/null || echo "$(RED)Not installed$(NC)"
	@echo ""
	@echo -n "$(YELLOW).env exists:$(NC)   "
	@test -f apps/api/.env && echo "$(GREEN)Yes$(NC)" || echo "$(YELLOW)No (using .env.example)$(NC)"

urls: ## Show application URLs
	@echo "$(BLUE)NEXUS Platform URLs:$(NC)"
	@echo ""
	@echo "  $(GREEN)Web:$(NC)       http://localhost:3000"
	@echo "  $(GREEN)API:$(NC)       http://localhost:8000"
	@echo "  $(GREEN)API Docs:$(NC)  http://localhost:8000/docs"
	@echo "  $(GREEN)ReDoc:$(NC)     http://localhost:8000/redoc"
	@echo ""

quick: kill-ports up ## Quick restart (alias for kill-ports + up)
