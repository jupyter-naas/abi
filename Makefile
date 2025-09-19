# =============================================================================
# ABI Project Makefile
# =============================================================================
# Main entry points for the ABI (Agent-Based Intelligence) project
# This file organizes commands into logical categories for easy navigation

# =============================================================================
# CORE TARGETS (Primary entry points)
# =============================================================================

# Default target - starts the main ABI chat agent
.DEFAULT_GOAL := default

# Default target with help display
default: deps help
	@ LOG_LEVEL=ERROR uv run python -m src.cli AbiAgent

# Main help documentation - displays all available commands organized by category
help:
	@echo "ABI Project Makefile Help"
	@echo "=========================="
	@echo ""
	@echo "CORE TARGETS:"
	@echo "  default                  Show this help message and ensure dependencies"
	@echo "  deps                     Install all dependencies and set up environment"
	@echo "  chat                     Start generic agent (use: make chat agent=AgentName)"
	@echo "  help                     Show this help documentation"
	@echo ""
	@echo "DEPENDENCIES & ENVIRONMENT:"
	@echo "  uv                       Ensure uv package manager and Python 3.10 are installed"
	@echo "  .venv                    Create virtual environment and install dependencies"
	@echo "  .env                     Create environment file (auto-generated on first run)"
	@echo "  git-deps                 Set up git hooks for code quality checks"
	@echo "  install                  Install all dependencies (alternative to .venv)"
	@echo "  lock                     Update dependency lock files"
	@echo "  local-build              Build all Docker containers defined in docker-compose.yml"
	@echo ""
	@echo "CHAT & AGENT COMMANDS:"
	@echo "  chat-abi-agent           Start the main ABI agent (default target)"
	@echo "  chat-naas-agent          Start the Naas platform integration agent"
	@echo "  chat-support-agent       Start the customer support specialized agent"
	@echo ""
	@echo "LOCAL AI AGENTS (Privacy-focused via Ollama):"
	@echo "  chat-qwen-agent          Start Qwen3 8B agent (multilingual, coding)"
	@echo "  chat-deepseek-agent      Start DeepSeek R1 8B agent (reasoning, math)"
	@echo "  chat-gemma-agent         Start Gemma3 4B agent (lightweight, fast)"
	@echo ""
	@echo "DEVELOPMENT SERVERS & TOOLS:"
	@echo "  api                      Start API server for local development (port 9879)"
	@echo "  api-prod                 Build and run production API server in Docker"
	@echo "  api-local                Start local API server in Docker with volume mounting"
	@echo "  mcp                      Start MCP server (STDIO mode for Claude Desktop)"
	@echo "  mcp-http                 Start MCP server (HTTP mode on port 8000)"
	@echo "  mcp-test                 Run MCP server validation tests"
	@echo "  sparql-terminal          Open interactive SPARQL terminal for knowledge graph"
	@echo "  oxigraph-admin           Open Oxigraph administrative interface"
	@echo "  oxigraph-explorer        Open Knowledge Graph Explorer web interface"
	@echo ""
	@echo "TESTING & QUALITY ASSURANCE:"
	@echo "  test                     Run all Python tests using pytest"
	@echo "  test-abi                 Run tests specifically for the abi library"
	@echo "  test-api                 Run API-specific tests"
	@echo "  test-api-init            Test API initialization with production secrets"
	@echo "  test-api-init-container  Test API initialization in containerized environment"
	@echo "  ftest                    Interactive test selector using fzf (fuzzy finder)"
	@echo ""
	@echo "CODE QUALITY & LINTING:"
	@echo "  check                    Run all code quality checks (core, custom, marketplace)"
	@echo "  check-core               Run code quality checks for core modules"
	@echo "  check-custom             Run code quality checks for custom modules"
	@echo "  check-marketplace        Run code quality checks for marketplace modules"
	@echo "  fmt                      Format code using ruff"
	@echo "  bandit                   Run security scanning with bandit"
	@echo "  trivy-container-scan     Run container security scanning with trivy"
	@echo ""
	@echo "PACKAGE MANAGEMENT:"
	@echo "  add                      Add dependency to main project (use: make add dep=package)"
	@echo "  abi-add                  Add dependency to abi library (use: make abi-add dep=package)"
	@echo ""
	@echo "DOCKER BUILD COMMANDS:"
	@echo "  build                    Build Docker image (alias for build.linux.x86_64)"
	@echo "  build.linux.x86_64       Build Docker image for Linux x86_64 architecture"
	@echo ""
	@echo "DOCKER COMPOSE MANAGEMENT:"
	@echo "  check-docker             Check if Docker is running"
	@echo "  docker-cleanup           Clean up Docker conflicts and stuck containers"
	@echo "  oxigraph-up              Start Oxigraph knowledge graph database"
	@echo "  oxigraph-down            Stop Oxigraph database"
	@echo "  oxigraph-status          Check Oxigraph container status"
	@echo "  local-up                 Start all local development services"
	@echo "  local-logs               View logs from all local services"
	@echo "  local-stop               Stop all local services without removing containers"
	@echo "  local-down               Stop and remove all local service containers"
	@echo "  container-up             Start ABI in container mode"
	@echo "  container-down           Stop ABI container"
	@echo ""
	@echo "DAGSTER DATA ORCHESTRATION:"
	@echo "  dagster-dev              Start Dagster development server (foreground)"
	@echo "  dagster-up               Start Dagster in background mode"
	@echo "  dagster-down             Stop Dagster background service"
	@echo "  dagster-logs             View Dagster service logs"
	@echo "  dagster-ui               Open Dagster web interface"
	@echo "  dagster-status           Check status of Dagster assets"
	@echo "  dagster-materialize      Materialize all Dagster assets"
	@echo ""
	@echo "DATA MANAGEMENT & OPERATIONS:"
	@echo "  dvc-login                Set up Data Version Control (DVC) authentication"
	@echo "  datastore-pull           Pull datastore from remote storage"
	@echo "  datastore-push           Push local datastore changes to remote storage"
	@echo "  storage-pull             Pull storage data from remote"
	@echo "  storage-push             Push local storage changes to remote"
	@echo "  triplestore-prod-remove  Remove production triplestore data"
	@echo "  triplestore-prod-override Override production triplestore with local data"
	@echo "  triplestore-prod-pull    Pull triplestore data from production environment"
	@echo "  triplestore-export-excel Export triplestore data to Excel format"
	@echo "  triplestore-export-turtle Export triplestore data to Turtle (RDF) format"
	@echo ""
	@echo "DOCUMENTATION & PUBLISHING:"
	@echo "  docs-ontology            Generate ontology documentation"
	@echo "  publish-remote-agents    Publish remote agents to workspace"
	@echo "  publish-remote-agents-dry-run Preview remote agent publishing (dry-run mode)"
	@echo "  pull-request-description Generate pull request description using AI agent"
	@echo ""
	@echo "CLEANUP & MAINTENANCE:"
	@echo "  clean                    Clean up build artifacts, caches, and Docker containers"
	@echo ""
	@echo "QUICK START:"
	@echo "  1. make deps             # Set up environment"
	@echo "  2. make local-up         # Start local services"
	@echo "  3. make                  # Start ABI agent (default)"
	@echo ""
	@echo "TROUBLESHOOTING:"
	@echo "  If 'make' hangs or times out:"
	@echo "    1. make docker-cleanup"
	@echo "    2. make local-up"
	@echo "    3. make"
	@echo ""
	@echo "DEFAULT TARGET:"
	@echo "  Running 'make' installs dependencies and starts the Abi"
	@echo ""

# =============================================================================
# DEPENDENCIES & ENVIRONMENT SETUP
# =============================================================================

# Master dependency target - ensures all dependencies are satisfied
deps: uv git-deps .venv .env

# Ensure uv package manager is installed and Python 3.10 is available
uv:
	@if ! command -v uv >/dev/null 2>&1; then \
		echo "🚀 Oops! Looks like uv is missing from your system!"; \
		echo "📚 Don't worry - you can get it here: https://docs.astral.sh/uv/getting-started/installation/"; \
		exit 1; \
	fi
	@ uv python find 3.10 > /dev/null || (uv python install 3.10 && uv python pin 3.10)

# Create virtual environment and install all dependencies
.venv:
	@ uv sync --all-extras

# Environment file will be created dynamically by CLI during first boot
.env:
	@# .env will be created dynamically by CLI during first boot

# Set up git hooks for code quality checks before commits
.git/hooks/pre-commit:
	@mkdir -p .git/hooks
	@echo 'cd "$(git rev-parse --show-toplevel)" || exit 1;make check' > .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit

# Install git hooks as dependency
git-deps: .git/hooks/pre-commit

# Create symbolic link to allow importing lib.abi from the virtual environment
python_version=$(shell cat .python-version)
.venv/lib/python$(python_version)/site-packages/abi: deps
	@[ -L .venv/lib/python$(python_version)/site-packages/abi ] || ln -s `pwd`/lib/abi .venv/lib/python$(python_version)/site-packages/abi 

# Install dependencies (alternative to .venv)
install: dep
	@ uv sync

# Update dependency lock files
lock: deps
	@ uv lock

# Build local Docker containers
local-build: deps
	@ docker compose build

# =============================================================================
# CHAT & AGENT COMMANDS
# =============================================================================

# Generic chat command - allows specifying agent via agent=AgentName parameter
agent=AbiAgent
chat: deps
	@ LOG_LEVEL=ERROR uv run python -m src.cli $(agent)

# Main ABI agent - the primary conversational AI interface
chat-abi-agent: deps
	@ LOG_LEVEL=ERROR uv run python -m src.cli AbiAgent

# Naas platform integration agent
chat-naas-agent: deps
	@ LOG_LEVEL=ERROR uv run python -m src.cli NaasAgent

# Customer support specialized agent
chat-support-agent: deps
	@ LOG_LEVEL=ERROR uv run python -m src.cli SupportAgent

# =============================================================================
# LOCAL AI AGENTS (Privacy-focused, runs on local hardware via Ollama)
# =============================================================================

# Qwen3 8B - Multilingual coding assistant (local)
chat-qwen-agent: deps
	@ LOG_LEVEL=DEBUG uv run python -m src.cli QwenAgent

# DeepSeek R1 8B - Advanced reasoning and mathematics (local)
chat-deepseek-agent: deps
	@ LOG_LEVEL=DEBUG uv run python -m src.cli DeepSeekAgent

# Gemma3 4B - Lightweight and fast responses (local)
chat-gemma-agent: deps
	@ LOG_LEVEL=DEBUG uv run python -m src.cli GemmaAgent

# =============================================================================
# DEVELOPMENT SERVERS & TOOLS
# =============================================================================

# Start the main API server for local development
api: deps
	uv run src/api.py

# Start production API server in Docker container
api-prod: deps
	@ docker build -t abi-prod -f docker/images/Dockerfile.linux.x86_64 . --platform linux/amd64
	@ docker run --rm -it -p 9879:9879 --env-file .env -e ENV=prod --platform linux/amd64 abi-prod

# Start local API server in Docker container with volume mounting
api-local: deps
	@ docker build -t abi-local -f docker/images/Dockerfile.linux.x86_64 . --platform linux/amd64
	@ docker run --rm -it -p 9879:9879 -v ./storage:/app/storage --env-file .env -e ENV=dev --platform linux/amd64 abi-local

# MCP (Model Context Protocol) server for Claude Desktop integration
mcp: deps
	@echo "🚀 Starting MCP Server (STDIO mode for Claude Desktop)..."
	uv run mcp-server

# MCP server in HTTP mode for web-based integration
mcp-http: deps
	@echo "🌐 Starting MCP Server (SSE mode on port 8000)..."
	MCP_TRANSPORT=sse uv run mcp-server

# Run MCP server validation tests
mcp-test: deps
	@echo "🔍 Running MCP Server validation tests..."
	uv run python -m src.mcp_server_test

# Interactive SPARQL terminal for querying the knowledge graph
sparql-terminal: deps
	@ uv run python -m src.core.abi.apps.sparql_terminal.main	

# Oxigraph administrative interface for database management
oxigraph-admin: deps
	@ uv run python -m src.core.abi.apps.oxigraph_admin.main

# Knowledge Graph Explorer with integrated web interface
oxigraph-explorer:
	@echo "🚀 Opening Knowledge Graph Explorer..."
	@echo "📍 Visit: http://localhost:7878/explorer/"
	@echo "✨ Features:"
	@echo "   • Interactive overview dashboard"
	@echo "   • Full-featured YasGUI SPARQL editor"
	@echo "   • Pre-built query library with explanations"
	@command -v open >/dev/null 2>&1 && open "http://localhost:7878/explorer/" || echo "Open the URL manually in your browser"

# =============================================================================
# TESTING & QUALITY ASSURANCE
# =============================================================================

# Run all Python tests using pytest
path=tests/
test: deps
	@ uv run python -m pytest .

# Run tests specifically for the abi library
test-abi: deps
	@ uv run python -m pytest lib

# Run API-specific tests
test-api: deps
	@ uv run python -m pytest src/api_test.py -v -s

# Test API initialization with production secrets
test-api-init: deps
	@ echo "🔍 Testing API initialization with production secrets..."
	@ uv run --no-dev src/api.py --test-init

# Test API initialization in containerized environment
test-api-init-container: build
	@ echo "🔍 Testing API initialization in container with production secrets..."
	@ docker run --rm \
		-e ABI_API_KEY="${ABI_API_KEY}" \
		-e NAAS_API_KEY="${NAAS_API_KEY}" \
		-e NAAS_CREDENTIALS_JWT_TOKEN="${NAAS_CREDENTIALS_JWT_TOKEN}" \
		-e OPENAI_API_KEY="${OPENAI_API_KEY}" \
		-e GITHUB_ACCESS_TOKEN="${GITHUB_ACCESS_TOKEN}" \
		abi:latest uv run --no-dev src/api.py --test-init

# Interactive test selector using fzf (fuzzy finder)
q=''
ftest: deps
	@ uv run python -m pytest $(shell find lib src tests -name '*_test.py' -type f | fzf -q $(q)) $(args)

# Test command for debugging
hello:
	@echo 'hello' | make

# =============================================================================
# CODE QUALITY & LINTING
# =============================================================================

# Master check target - runs all code quality checks
check: deps .venv/lib/python$(python_version)/site-packages/abi check-core check-custom check-marketplace

# Code quality checks for core modules
check-core: deps
	@echo ""
	@echo "  _____ _____ _____ _____"
	@echo " |     |     |     |     |"
	@echo " |  C  |  O  |  R  |  E  |"
	@echo " |_____|_____|_____|_____|"
	@echo ""
	@echo "\033[1;4m🔍 Running code quality checks...\033[0m\n"
	@echo "📝 Linting with ruff..."
	@uvx ruff check lib src/core --exclude "src/core/**/sandbox/**"

	@echo "\n\033[1;4m🔍 Running static type analysis...\033[0m\n"
	@echo "• Checking lib.abi..."
	@.venv/bin/mypy -p lib.abi --follow-untyped-imports
	@echo "• Checking src.core..."
	@.venv/bin/mypy -p src.core --follow-untyped-imports --exclude "src/core/.*/sandbox/.*"

	@#echo "\n⚠️ Skipping pyrefly checks (disabled)"
	@#uv run pyrefly check lib src/core

	@#echo "\n\033[1;4m🔍 Running security checks...\033[0m\n"
	@#echo "⚠️ Skipping bandit... (disabled)"
	@#@docker run --rm -v `pwd`:/data --workdir /data ghcr.io/pycqa/bandit/bandit -c bandit.yaml src/core lib -r
	@echo "\n✅ CORE security checks passed!"

# Code quality checks for custom modules
check-custom: deps
	@echo ""
	@echo "  _____ _____ _____ _____ _____ _____"
	@echo " |     |     |     |     |     |     |"
	@echo " |  C  |  U  |  S  |  T  |  O  |  M  |"
	@echo " |_____|_____|_____|_____|_____|_____|"
	@echo ""
	@echo "\n\033[1;4m🔍 Running code quality checks...\033[0m\n"
	@echo "📝 Linting with ruff..."
	@uvx ruff check src/custom --exclude "src/custom/**/sandbox/**"

	@echo "\n\033[1;4m🔍 Running static type analysis...\033[0m\n"
	@.venv/bin/mypy -p src.custom --follow-untyped-imports --exclude "src/custom/.*/sandbox/.*"

	@#echo "\n⚠️ Skipping pyrefly checks (disabled)"
	@#uv run pyrefly check src/custom

	@echo "\n✅ CUSTOM security checks passed!"

# Code quality checks for marketplace modules
check-marketplace: deps
	@echo ""
	@echo "  _____ _____ _____ _____ _____ _____ _____ _____ _____ _____ _____ "
	@echo " |     |     |     |     |     |     |     |     |     |     |     |"
	@echo " |  M  |  A  |  R  |  K  |  E  |  T  |  P  |  L  |  A  |  C  |  E  |"
	@echo " |_____|_____|_____|_____|_____|_____|_____|_____|_____|_____|_____|"
	@echo ""
	@echo "\n\033[1;4m🔍 Running code quality checks...\033[0m\n"
	@echo "📝 Linting with ruff..."
	@uvx ruff check src/marketplace --exclude "src/marketplace/**/sandbox/**"

	@echo "\n\033[1;4m🔍 Running static type analysis...\033[0m\n"
	@.venv/bin/mypy -p src.marketplace --follow-untyped-imports --exclude "src/marketplace/.*/sandbox/.*"

	@#echo "\n⚠️ Skipping pyrefly checks (disabled)"
	@#uv run pyrefly check src/marketplace

	@echo "\n✅ MARKETPLACE security checks passed!"

# Code formatting with ruff
fmt: deps
	@ uvx ruff format

# Security scanning with bandit
bandit:
	@docker run --rm -v `pwd`:/data --workdir /data ghcr.io/pycqa/bandit/bandit -c bandit.yaml tests src/ lib -r

# Container security scanning with trivy
trivy-container-scan: build
	docker save abi:latest -o abi.tar && trivy image --input abi.tar && rm abi.tar

# =============================================================================
# PACKAGE MANAGEMENT
# =============================================================================

# Add dependency to the main project
add: deps
	uv add $(dep) && uv lock

# Add dependency to the abi library
abi-add: deps
	cd lib && uv add $(dep) && uv lock

# =============================================================================
# DOCKER BUILD COMMANDS
# =============================================================================

# Default build target - builds for Linux x86_64
build: build.linux.x86_64

# Build Docker image for Linux x86_64 architecture with size reporting
build.linux.x86_64: deps
	DOCKER_BUILDKIT=1 docker build . -t abi -f docker/images/Dockerfile.linux.x86_64 --platform linux/amd64
	
	@# Show container size
	@docker image ls abi

# =============================================================================
# DOCKER COMPOSE MANAGEMENT
# =============================================================================

# Check if Docker is running before executing docker commands
check-docker:
	@if ! docker info > /dev/null 2>&1; then \
		echo "❌ Docker is not running. Please start Docker Desktop first."; \
		echo "💡 After starting Docker, run: make docker-cleanup && make local-up"; \
		exit 1; \
	fi

# Enhanced cleanup with conflict detection
docker-cleanup: check-docker
	@echo "🧹 Running Docker cleanup to prevent conflicts..."
	@./docker/scripts/cleanup.sh

# Start Oxigraph knowledge graph database
oxigraph-up: check-docker
	@docker-compose -f docker-compose.yml --profile local up -d oxigraph || (echo "❌ Failed to start Oxigraph. Try: make docker-cleanup"; exit 1)
	@echo "✓ Oxigraph started on http://localhost:7878"

# Stop Oxigraph database
oxigraph-down: check-docker
	@docker-compose -f docker-compose.yml --profile local stop oxigraph || true
	@echo "✓ Oxigraph stopped"

# Check Oxigraph container status
oxigraph-status: check-docker
	@echo "Oxigraph status:"
	@docker-compose -f docker-compose.yml --profile local ps oxigraph

# Start all local development services
local-up: check-docker
	@echo "🚀 Starting local services..."
	@if ! docker-compose -f docker-compose.yml --profile local up -d --timeout 60; then \
		echo "❌ Failed to start services. Running cleanup..."; \
		./docker/scripts/cleanup.sh; \
		echo "🔄 Retrying..."; \
		docker-compose -f docker-compose.yml --profile local up -d --timeout 60 || (echo "❌ Still failing. Check Docker Desktop status."; exit 1); \
	fi
	@echo "✓ Local containers started"
	@make dagster-up
	@echo ""
	@echo "🌟 Local environment ready!"
	@echo "✓ Services available at:"
	@echo "  - Oxigraph (Knowledge Graph): http://localhost:7878"
	@echo "  - YasGUI (SPARQL Editor): http://localhost:3000"
	@echo "  - PostgreSQL (Agent Memory): localhost:5432"
	@echo "  - Dagster (Orchestration): http://localhost:3001"

# View logs from all local services
local-logs: check-docker
	@docker-compose -f docker-compose.yml --profile local logs -f

# Stop all local services without removing containers
local-stop: check-docker
	@docker-compose -f docker-compose.yml --profile local stop
	@echo "✓ All local services stopped"

# Stop and remove all local service containers
local-down: check-docker
	@make dagster-down
	@docker-compose -f docker-compose.yml --profile local down --timeout 10 || true
	@echo "✓ All local services stopped"

# Start ABI in container mode
container-up:
	@docker-compose -f docker-compose.yml --profile container up -d
	@echo "✓ ABI container started"

# Stop ABI container
container-down:
	@docker-compose -f docker-compose.yml --profile container down
	@echo "✓ ABI container stopped"

# =============================================================================
# DAGSTER DATA ORCHESTRATION
# =============================================================================

# Start Dagster development server in foreground
dagster-dev:
	@echo "🚀 Starting Dagster development server..."
	@docker-compose -f docker-compose.yml --profile local up dagster

# Start Dagster in background mode
dagster-up:
	@echo "🚀 Starting Dagster in background..."
	@docker-compose -f docker-compose.yml --profile local up -d dagster
	@echo "✓ Dagster started on http://localhost:3001"
	@echo "📝 Logs: make dagster-logs"

# Stop Dagster background service
dagster-down:
	@echo "🛑 Stopping Dagster..."
	@docker-compose -f docker-compose.yml --profile local down dagster
	@echo "✓ Dagster stopped"

# View Dagster service logs
dagster-logs:
	@echo "📄 Showing Dagster logs..."
	@docker-compose -f docker-compose.yml --profile local logs -f dagster

# Open Dagster web interface
dagster-ui:
	@echo "🌐 Opening Dagster web interface..."
	@echo "📍 Visit: http://localhost:3001"
	@command -v open >/dev/null 2>&1 && open "http://localhost:3001" || echo "Open the URL manually in your browser"
	@docker-compose -f docker-compose.yml --profile local up dagster

# Check status of Dagster assets
dagster-status:
	@echo "📊 Checking Dagster asset status..."
	@docker-compose -f docker-compose.yml --profile local exec dagster uv run dagster asset list -m src.marketplace.__demo__.orchestration.definitions

# Materialize all Dagster assets
dagster-materialize:
	@echo "⚙️ Materializing all Dagster assets..."
	@docker-compose -f docker-compose.yml --profile local exec dagster uv run dagster asset materialize --select "*" -m src.marketplace.__demo__.orchestration.definitions

# =============================================================================
# DATA MANAGEMENT & OPERATIONS
# =============================================================================

# Set up Data Version Control (DVC) authentication
dvc-login: deps
	@ uv run run python scripts/setup_dvc.py | sh

# Pull datastore from remote storage
datastore-pull: deps
	@ echo "Pulling datastore..."
	@ uv run --no-dev python scripts/datastore_pull.py | sh

# Push local datastore changes to remote storage
datastore-push: deps datastore-pull
	@ echo "Pushing datastore..."
	@ uv run --no-dev python scripts/datastore_push.py | sh

# Pull storage data from remote
storage-pull: deps
	@ echo "Pulling storage..."
	@ docker compose run --rm --remove-orphans abi bash -c 'uv run --no-dev python scripts/storage_pull.py | sh'

# Push local storage changes to remote
storage-push: deps storage-pull
	@ echo "Pushing storage..."
	@ docker compose run --rm --remove-orphans abi bash -c 'uv run --no-dev python scripts/storage_push.py | sh'

# Remove production triplestore data
triplestore-prod-remove: deps
	@ echo "Removing production triplestore..."
	@ docker compose run --rm --remove-orphans abi bash -c 'uv run --no-dev python scripts/triplestore_prod_remove.py'

# Override production triplestore with local data
triplestore-prod-override: deps
	@ echo "Overriding production triplestore..."
	@ docker compose run --rm --remove-orphans abi bash -c 'uv run --no-dev python scripts/triplestore_prod_override.py'

# Pull triplestore data from production environment
triplestore-prod-pull: deps
	@ echo "Pulling production triplestore..."
	@ docker compose run --rm --remove-orphans abi bash -c 'uv run --no-dev python scripts/triplestore_prod_pull.py'

# Export triplestore data to Excel format
triplestore-export-excel: deps
	@ echo "Exporting triplestore to Excel..."
	@ uv run python scripts/export_triplestore_excel.py

# Export triplestore data to Turtle (RDF) format
triplestore-export-turtle: deps
	@ echo "Exporting triplestore to turtle..."
	@ uv run python scripts/export_triplestore_turtle.py

# =============================================================================
# DOCUMENTATION & PUBLISHING
# =============================================================================

# Generate ontology documentation
docs-ontology: deps
	@ echo "Generating ontology documentation..."
	@ uv run python scripts/generate_docs.py

# Publish remote agents to workspace
publish-remote-agents: deps
	@ echo "Publishing remote agents..."
	@ uv run python scripts/publish_remote_agents.py

# Preview remote agent publishing (dry-run mode)
publish-remote-agents-dry-run: deps
	@ echo "Dry-run: Previewing remote agent publishing..."
	@ uv run python scripts/publish_remote_agents.py --dry-run

# Generate pull request description using AI agent
pull-request-description: deps
	@ uv run python -m src.core.abi.apps.terminal_agent.main generic_run_agent PullRequestDescriptionAgent

# =============================================================================
# CLEANUP & MAINTENANCE
# =============================================================================

# Clean up build artifacts, caches, and Docker containers
clean:
	@echo "Cleaning up build artifacts..."
	rm -rf __pycache__ .pytest_cache build dist *.egg-info lib/.venv .venv
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -delete
	docker compose down
	docker compose rm -f
	rm -rf src/core/modules/common/integrations/siteanalyzer/target
	rm -f dagster.pid dagster.log

# =============================================================================
# PHONY TARGETS
# =============================================================================
# Declare all targets as phony to avoid conflicts with files of the same name

.PHONY: test chat-abi-agent chat-naas-agent chat-ontology-agent chat-support-agent chat-qwen-agent chat-deepseek-agent chat-gemma-agent api sh lock add abi-add help uv oxigraph-up oxigraph-down oxigraph-status local-up local-down container-up container-down dagster-dev dagster-up dagster-down dagster-ui dagster-logs dagster-status dagster-materialize