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
log_level=ERROR
default: deps local-up airgap
	@ LOG_LEVEL=$(log_level) uv run cli chat naas_abi AbiAgent

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
	@echo "  chat                     Start generic chat (default agent: AbiAgent, override: agent=AgentName)"
	@echo "  chat-abi-agent           Start the main ABI conversational agent"
	@echo ""
	@echo "MARKETPLACE AI AGENTS:"
	@echo "  chat-chatgpt-agent       Start ChatGPT-based agent"
	@echo "  chat-claude-agent        Start Claude-based agent"
	@echo "  chat-deepseek-agent      Start DeepSeek-based agent"
	@echo "  chat-gemini-agent        Start Gemini-based agent"
	@echo "  chat-gemma-agent         Start Gemma-based agent"
	@echo "  chat-grok-agent          Start Grok-based agent"
	@echo "  chat-llama-agent         Start Llama-based agent"
	@echo "  chat-mistral-agent       Start Mistral-based agent"
	@echo "  chat-perplexity-agent    Start Perplexity-based agent"
	@echo "  chat-qwen-agent          Start Qwen-based agent"
	@echo ""
	@echo "MARKETPLACE APPLICATION AGENTS:"
	@echo "  chat-agicap-agent        Start Agicap integration agent"
	@echo "  chat-airtable-agent      Start Airtable integration agent"
	@echo "  chat-algolia-agent       Start Algolia integration agent"
	@echo "  chat-arxiv-agent         Start ArXiv integration agent"
	@echo "  chat-aws-agent           Start AWS integration agent"
	@echo "  chat-bodo-agent          Start Bodo integration agent"
	@echo "  chat-datagouv-agent      Start DataGouv integration agent"
	@echo "  chat-exchangeratesapi-agent Start ExchangeRatesAPI integration agent"
	@echo "  chat-github-agent        Start GitHub integration agent"
	@echo "  chat-gmail-agent          Start Gmail integration agent"
	@echo "  chat-google-analytics-agent Start Google Analytics integration agent"
	@echo "  chat-google-calendar-agent Start Google Calendar integration agent"
	@echo "  chat-google-drive-agent   Start Google Drive integration agent"
	@echo "  chat-google-maps-agent   Start Google Maps integration agent"
	@echo "  chat-google-search-agent Start Google Search integration agent"
	@echo "  chat-google-sheets-agent  Start Google Sheets integration agent"
	@echo "  chat-hubspot-agent        Start HubSpot integration agent"
	@echo "  chat-instagram-agent     Start Instagram integration agent"
	@echo "  chat-linkedin-agent      Start LinkedIn integration agent"
	@echo "  chat-mercury-agent       Start Mercury integration agent"
	@echo "  chat-naas-agent          Start Naas platform integration agent"
	@echo "  chat-nebari-agent        Start Nebari integration agent"
	@echo "  chat-newsapi-agent        Start NewsAPI integration agent"
	@echo "  chat-notion-agent        Start Notion integration agent"
	@echo "  chat-openalex-agent      Start OpenAlex integration agent"
	@echo "  chat-openrouter-agent    Start OpenRouter integration agent"
	@echo "  chat-openweathermap-agent Start OpenWeatherMap integration agent"
	@echo "  chat-pennylane-agent     Start Pennylane integration agent"
	@echo "  chat-postgres-agent      Start PostgreSQL integration agent"
	@echo "  chat-powerpoint-agent    Start PowerPoint integration agent"
	@echo "  chat-pubmed-agent        Start PubMed integration agent"
	@echo "  chat-qonto-agent         Start Qonto integration agent"
	@echo "  chat-salesforce-agent    Start Salesforce integration agent"
	@echo "  chat-sanax-agent         Start Sanax integration agent"
	@echo "  chat-sendgrid-agent      Start SendGrid integration agent"
	@echo "  chat-sharepoint-agent    Start SharePoint integration agent"
	@echo "  chat-slack-agent         Start Slack integration agent"
	@echo "  chat-spotify-agent       Start Spotify integration agent"
	@echo "  chat-stripe-agent        Start Stripe integration agent"
	@echo "  chat-twilio-agent        Start Twilio integration agent"
	@echo "  chat-whatsapp-business-agent Start WhatsApp Business integration agent"
	@echo "  chat-worldbank-agent     Start World Bank integration agent"
	@echo "  chat-yahoofinance-agent  Start Yahoo Finance integration agent"
	@echo "  chat-youtube-agent       Start YouTube integration agent"
	@echo "  chat-zoho-agent          Start Zoho integration agent"
	@echo "  pull-request-description Generate pull request description using AI"
	@echo ""
	@echo "MARKETPLACE DOMAIN AGENTS:"
	@echo "  chat-support-agent       Start customer support specialized agent"
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
	@echo "  test-coverage            Run tests with coverage reporting and badge generation"
	@echo "  test-ci                  Run basic tests for CI (no external dependencies)"
	@echo "  test-abi                 Run tests specifically for the abi library"
	@echo "  test-api                 Run API-specific tests"
	@echo "  test-api-init            Test API initialization with production secrets"
	@echo "  test-api-init-container  Test API initialization in containerized environment"
	@echo "  ftest                    Interactive test selector using fzf (fuzzy finder)"
	@echo ""
	@echo "CODE QUALITY & LINTING:"
	@echo "  check                    Run all code quality checks (core, custom, marketplace)"
	@echo "  check-core               Run code quality checks for core modules"
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
	@echo "  local-reload             Stop and remove all local service containers and restart them"
	@echo "  container-up             Start ABI in container mode"
	@echo "  container-down           Stop ABI container"
	@echo "  model-up                 Start Docker model for airgap AI operation"
	@echo "  model-down               Stop Docker model"
	@echo "  model-status             Check Docker model status"
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

# Ensure airgap model is running if AI_MODE=airgap
airgap:
	@if grep -q "AI_MODE=airgap" .env 2>/dev/null; then \
		echo "🤖 Docker AI models managed by Compose specification"; \
		echo "✓ Models will auto-start when services are launched"; \
	fi

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

deps-upgrade:
	@ uv sync --all-extras --upgrade

# Environment file will be created dynamically by CLI during first boot
.env:
	@# .env will be created dynamically by CLI during first boot

# Set up git hooks for code quality checks before commits
.git/hooks/pre-commit:
	@if [ -d .git ]; then \
		mkdir -p .git/hooks \
		&& echo 'cd "$(git rev-parse --show-toplevel)" || exit 1;make check' > .git/hooks/pre-commit \
		&& chmod +x .git/hooks/pre-commit \
	; fi

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
# CHAT WITH CORE AGENTS
# =============================================================================

agent=AbiAgent
# Generic chat command - allows specifying agent via agent=AgentName parameter
chat: deps
	@ LOG_LEVEL=DEBUG uv run cli chat $(module_name) $(agent_name)

# Main ABI agent - the primary conversational AI interface
chat-abi-agent: deps
	@ LOG_LEVEL=$(log_level) uv run cli chat naas_abi AbiAgent

# =============================================================================
# CHAT WITH MARKETPLACE AI AGENTS
# =============================================================================

chat-chatgpt-agent: deps
	@ LOG_LEVEL=$(log_level) uv run cli chat naas_abi_marketplace.ai.chatgpt ChatGPTAgent

chat-claude-agent: deps
	@ LOG_LEVEL=$(log_level) uv run cli chat naas_abi_marketplace.ai.claude ClaudeAgent

chat-deepseek-agent: deps
	@ LOG_LEVEL=DEBUG uv run cli chat naas_abi_marketplace.ai.deepseek DeepSeekAgent

chat-gemini-agent: deps
	@ LOG_LEVEL=$(log_level) uv run cli chat naas_abi_marketplace.ai.gemini GeminiAgent

chat-gemma-agent: deps
	@ LOG_LEVEL=DEBUG uv run cli chat naas_abi_marketplace.ai.gemma GemmaAgent

chat-grok-agent: deps
	@ LOG_LEVEL=$(log_level) uv run cli chat naas_abi_marketplace.ai.grok GrokAgent

chat-llama-agent: deps
	@ LOG_LEVEL=$(log_level) uv run cli chat naas_abi_marketplace.ai.llama LlamaAgent

chat-mistral-agent: deps
	@ LOG_LEVEL=$(log_level) uv run cli chat naas_abi_marketplace.ai.mistral MistralAgent

chat-perplexity-agent: deps
	@ LOG_LEVEL=$(log_level) uv run cli chat naas_abi_marketplace.ai.perplexity PerplexityAgent

chat-qwen-agent: deps
	@ LOG_LEVEL=$(log_level) uv run cli chat naas_abi_marketplace.ai.qwen QwenAgent

# =============================================================================
# CHAT WITH MARKETPLACE APPLICATIONS AGENTS
# =============================================================================

chat-agicap-agent: deps
	@ LOG_LEVEL=$(log_level) uv run cli chat naas_abi_marketplace.applications.agicap AgicapAgent

chat-algolia-agent: deps
	@ LOG_LEVEL=$(log_level) uv run cli chat naas_abi_marketplace.applications.algolia AlgoliaAgent

chat-github-agent: deps
	@ LOG_LEVEL=$(log_level) uv run cli chat naas_abi_marketplace.applications.github GitHubAgent

chat-google-search-agent: deps
	@ LOG_LEVEL=$(log_level) uv run cli chat naas_abi_marketplace.applications.google_search GoogleSearchAgent

chat-linkedin-agent: deps
	@ LOG_LEVEL=$(log_level) uv run cli chat naas_abi_marketplace.applications.linkedin LinkedInAgent

chat-naas-agent: deps
	@ LOG_LEVEL=$(log_level) uv run cli chat naas_abi_marketplace.applications.naas NaasAgent

chat-powerpoint-agent: deps
	@ LOG_LEVEL=$(log_level) uv run cli chat naas_abi_marketplace.applications.powerpoint PowerPointAgent

chat-aws-agent: deps
	@ LOG_LEVEL=$(log_level) uv run cli chat naas_abi_marketplace.applications.aws AWSAgent

chat-arxiv-agent: deps
	@ LOG_LEVEL=$(log_level) uv run cli chat naas_abi_marketplace.applications.arxiv ArXivAgent

chat-bodo-agent: deps
	@ LOG_LEVEL=$(log_level) uv run cli chat naas_abi_marketplace.applications.bodo BodoAgent

chat-exchangeratesapi-agent: deps
	@ LOG_LEVEL=$(log_level) uv run cli chat naas_abi_marketplace.applications.exchangeratesapi ExchangeRatesAPIAgent

chat-sendgrid-agent: deps
	@ LOG_LEVEL=$(log_level) uv run cli chat naas_abi_marketplace.applications.sendgrid SendGridAgent

chat-openrouter-agent: deps
	@ LOG_LEVEL=$(log_level) uv run cli chat naas_abi_marketplace.applications.openrouter OpenRouterAgent

chat-hubspot-agent: deps
	@ LOG_LEVEL=$(log_level) uv run cli chat naas_abi_marketplace.applications.hubspot HubSpotAgent

chat-airtable-agent: deps
	@ LOG_LEVEL=$(log_level) uv run cli chat naas_abi_marketplace.applications.airtable AirtableAgent

chat-gmail-agent: deps
	@ LOG_LEVEL=$(log_level) uv run cli chat naas_abi_marketplace.applications.gmail GmailAgent

chat-google-calendar-agent: deps
	@ LOG_LEVEL=$(log_level) uv run cli chat naas_abi_marketplace.applications.google_calendar GoogleCalendarAgent

chat-google-drive-agent: deps
	@ LOG_LEVEL=$(log_level) uv run cli chat naas_abi_marketplace.applications.google_drive GoogleDriveAgent

chat-google-sheets-agent: deps
	@ LOG_LEVEL=$(log_level) uv run cli chat naas_abi_marketplace.applications.google_sheets GoogleSheetsAgent

chat-google-maps-agent: deps
	@ LOG_LEVEL=$(log_level) uv run cli chat naas_abi_marketplace.applications.google_maps GoogleMapsAgent

chat-google-analytics-agent: deps
	@ LOG_LEVEL=$(log_level) uv run cli chat naas_abi_marketplace.applications.google_analytics GoogleAnalyticsAgent

chat-instagram-agent: deps
	@ LOG_LEVEL=$(log_level) uv run cli chat naas_abi_marketplace.applications.instagram InstagramAgent

chat-mercury-agent: deps
	@ LOG_LEVEL=$(log_level) uv run cli chat naas_abi_marketplace.applications.mercury MercuryAgent

chat-nebari-agent: deps
	@ LOG_LEVEL=$(log_level) uv run cli chat naas_abi_marketplace.applications.nebari NebariAgent

chat-notion-agent: deps
	@ LOG_LEVEL=$(log_level) uv run cli chat naas_abi_marketplace.applications.notion NotionAgent

chat-newsapi-agent: deps
	@ LOG_LEVEL=$(log_level) uv run cli chat naas_abi_marketplace.applications.newsapi NewsAPIAgent

chat-openweathermap-agent: deps
	@ LOG_LEVEL=$(log_level) uv run cli chat naas_abi_marketplace.applications.openweathermap OpenWeatherMapAgent

chat-openalex-agent: deps
	@ LOG_LEVEL=$(log_level) uv run cli chat naas_abi_marketplace.applications.openalex OpenAlexAgent

chat-pennylane-agent: deps
	@ LOG_LEVEL=$(log_level) uv run cli chat naas_abi_marketplace.applications.pennylane PennylaneAgent

chat-postgres-agent: deps
	@ LOG_LEVEL=$(log_level) uv run cli chat naas_abi_marketplace.applications.postgres PostgresAgent

chat-pubmed-agent: deps
	@ LOG_LEVEL=$(log_level) uv run cli chat naas_abi_marketplace.applications.pubmed PubMedAgent

chat-qonto-agent: deps
	@ LOG_LEVEL=$(log_level) uv run cli chat naas_abi_marketplace.applications.qonto QontoAgent

chat-salesforce-agent: deps
	@ LOG_LEVEL=$(log_level) uv run cli chat naas_abi_marketplace.applications.salesforce SalesforceAgent

chat-sanax-agent: deps
	@ LOG_LEVEL=$(log_level) uv run cli chat naas_abi_marketplace.applications.sanax SanaxAgent

chat-sharepoint-agent: deps
	@ LOG_LEVEL=$(log_level) uv run cli chat naas_abi_marketplace.applications.sharepoint SharePointAgent

chat-slack-agent: deps
	@ LOG_LEVEL=$(log_level) uv run cli chat naas_abi_marketplace.applications.slack SlackAgent

chat-spotify-agent: deps
	@ LOG_LEVEL=$(log_level) uv run cli chat naas_abi_marketplace.applications.spotify SpotifyAgent

chat-stripe-agent: deps
	@ LOG_LEVEL=$(log_level) uv run cli chat naas_abi_marketplace.applications.stripe StripeAgent

chat-twilio-agent: deps
	@ LOG_LEVEL=$(log_level) uv run cli chat naas_abi_marketplace.applications.twilio TwilioAgent

chat-whatsapp-business-agent: deps
	@ LOG_LEVEL=$(log_level) uv run cli chat naas_abi_marketplace.applications.whatsapp_business WhatsAppBusinessAgent

chat-worldbank-agent: deps
	@ LOG_LEVEL=$(log_level) uv run cli chat naas_abi_marketplace.applications.worldbank WorldBankAgent

chat-yahoofinance-agent: deps
	@ LOG_LEVEL=$(log_level) uv run cli chat naas_abi_marketplace.applications.yahoofinance YfinanceAgent

chat-youtube-agent: deps
	@ LOG_LEVEL=$(log_level) uv run cli chat naas_abi_marketplace.applications.youtube YouTubeAgent

chat-zoho-agent: deps
	@ LOG_LEVEL=$(log_level) uv run cli chat naas_abi_marketplace.applications.zoho ZohoAgent

chat-datagouv-agent: deps
	@ LOG_LEVEL=$(log_level) uv run cli chat naas_abi_marketplace.applications.datagouv DataGouvAgent

pull-request-description: deps
	@ echo "generate the pull request description please."
	@ LOG_LEVEL=$(log_level) uv run cli chat naas_abi_marketplace.applications.git PullRequestDescriptionAgent

# =============================================================================
# CHAT WITH MARKETPLACE DOMAINS AGENTS
# =============================================================================

chat-support-agent: deps
	@ LOG_LEVEL=$(log_level) uv run cli chat naas_abi_marketplace.domains.support SupportAgent


# =============================================================================
# DEVELOPMENT SERVERS & TOOLS
# =============================================================================

# Start the main API server for local development
api: deps
	# uv run src/api.py
	uv run python -m naas_abi_core.apps.api.api

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

# Run tests with coverage reporting
test-coverage: deps
	@ uv run python -m pytest tests/ lib/abi/services/cache/ lib/abi/services/secret/ lib/abi/services/triple_store/ --cov=lib --cov-report=html --cov-report=term --cov-report=xml
	@ uv run coverage-badge -f -o coverage.svg
	@ echo "📊 Coverage report generated:"
	@ echo "  - HTML: htmlcov/index.html"
	@ echo "  - XML: coverage.xml"
	@ echo "  - Badge: coverage.svg"

# Run basic tests for CI (no external dependencies)
test-ci: deps
	@ uv run python -m pytest tests/unit/test_basic.py --cov=lib --cov-report=xml --cov-report=term -v

# Run tests specifically for the abi library
test-abi: deps
	@ uv run python -m pytest lib

# Run API-specific tests
test-api: deps
	@ uv run python -m pytest libs/naas-abi-core/naas_abi_core/apps/api/api_test.py -v -s

# Test API initialization with production secrets
test-api-init: deps
	@ echo "🔍 Testing API initialization with production secrets..."
	@ uv run --no-dev python -m naas_abi_core.apps.api.test_init

# Test API initialization in containerized environment
test-api-init-container: build
	@ echo "🔍 Testing API initialization in container with production secrets..."
	@ docker run --rm \
		-e ABI_API_KEY="${ABI_API_KEY}" \
		-e NAAS_API_KEY="${NAAS_API_KEY}" \
		-e NAAS_CREDENTIALS_JWT_TOKEN="${NAAS_CREDENTIALS_JWT_TOKEN}" \
		-e OPENAI_API_KEY="${OPENAI_API_KEY}" \
		-e GITHUB_ACCESS_TOKEN="${GITHUB_ACCESS_TOKEN}" \
		abi:latest uv run --no-dev python -m naas_abi_core.apps.api.test_init

# Interactive test selector using fzf (fuzzy finder)
q=''
ftest: deps
	@ clear
	LOG_LEVEL=DEBUG uv run python -m pytest $(shell find lib src tests -name '*_test.py' -type f | fzf -q $(q)) $(args)

dtest: deps
	@ uv run python -m pytest $(shell find lib src tests -type d | fzf -q $(q)) $(args)

frun: deps
	@ uv run $(shell find lib src tests -name '*.py' -type f | fzf -q $(q)) $(args)

# TTL_FILES := $(wildcard src/*/*/ontologies/*.ttl src/marketplace/*/*/ontologies/*.ttl)
TTL_FILES := $(shell find src -name '*.ttl')
PY_FILES := $(patsubst %.ttl, %.py, $(TTL_FILES))

onto2py-force: onto2py-clean $(PY_FILES) onto2py-ruff-fix

onto2py-ruff-fix: $(PY_FILES)
	@uv run ruff check --fix $(PY_FILES)

onto2py-clean:
	@rm -f $(PY_FILES)

onto2py-list:
	@echo $(PY_FILES)

onto2py: $(PY_FILES)

%.py: %.ttl
	@printf "📦 Converting ttl to py for $< ... "
	@uv run python -m lib.abi.utils.onto2py '$<' '$@'

# Test command for debugging
hello:
	@echo 'hello' | make

# =============================================================================
# CODE QUALITY & LINTING
# =============================================================================

# Master check target - runs all code quality checks
check: deps .venv/lib/python$(python_version)/site-packages/abi check-core # check-custom # check-marketplace #(Disable marketplace checks for now)

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
	@uvx ruff check libs/naas-abi-core libs/naas-abi-cli libs/naas-abi

	@echo "\n\033[1;4m🔍 Running static type analysis...\033[0m\n"
	@echo "• Checking naas_abi_core..."
	@cd libs/naas-abi-core && uv sync --all-extras && .venv/bin/mypy -p naas_abi_core --follow-untyped-imports

	@echo "• Checking naas_abi_cli..."
	@cd libs/naas-abi-cli && uv sync --all-extras && .venv/bin/mypy -p naas_abi_cli --follow-untyped-imports

	@echo "• Checking naas_abi..."
	@#@cd libs/naas-abi && uv sync --all-extras && .venv/bin/mypy -p naas_abi --follow-untyped-imports
	@echo "\n⚠️ Skipping libs/naas_abi type analysis (disabled) WE NEED TO REMEDIATE THIS\n"

	@#echo "\n⚠️ Skipping pyrefly checks (disabled)"
	@#uv run pyrefly check libs/naas-abi-core

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
	@uvx ruff check libs/naas-abi

	@echo "\n\033[1;4m🔍 Running static type analysis...\033[0m\n"
	@cd libs/naas-abi && uv sync --all-extras && uv run mypy -p naas_abi --follow-untyped-imports

	@#echo "\n⚠️ Skipping pyrefly checks (disabled)"
	@#uv run pyrefly check libs/naas-abi

	@echo "\n✅ CUSTOM security checks passed!"

# Code quality checks for marketplace modules
package=naas_abi_marketplace
check-marketplace: deps
	@echo ""
	@echo "  _____ _____ _____ _____ _____ _____ _____ _____ _____ _____ _____ "
	@echo " |     |     |     |     |     |     |     |     |     |     |     |"
	@echo " |  M  |  A  |  R  |  K  |  E  |  T  |  P  |  L  |  A  |  C  |  E  |"
	@echo " |_____|_____|_____|_____|_____|_____|_____|_____|_____|_____|_____|"
	@echo ""
	@echo "\n\033[1;4m🔍 Running code quality checks...\033[0m\n"
	@echo "📝 Linting with ruff..."
	@uvx ruff check libs/naas-abi-marketplace

	@echo "\n\033[1;4m🔍 Running static type analysis...\033[0m\n"
	cd libs/naas-abi-marketplace && uv run mypy -p $(package) --follow-untyped-imports

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
	uv add $(dep)

# Add dependency to the abi library
add-abi: deps
	cd libs/naas-abi && uv add $(dep)

# Add dependency to the naas-abi-cli library
add-cli: deps
	cd libs/naas-abi-cli && uv add $(dep)

# Add dependency to the naas-abi-core library
add-core: deps
	cd libs/naas-abi-core && uv add $(dep)

# Add dependency to the naas-abi-marketplace library
add-marketplace: deps
	cd libs/naas-abi-marketplace && uv add $(dep)

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
		echo "🐳 Docker not running. Attempting to start..."; \
		if [ "$$(uname)" = "Darwin" ]; then \
			echo "🍎 Starting Docker Desktop on macOS..."; \
			open -a Docker && echo "⏳ Waiting for Docker Desktop to start..." && sleep 10; \
			for i in 1 2 3 4 5 6; do \
				if docker info > /dev/null 2>&1; then \
					echo "✅ Docker Desktop started successfully!"; \
					break; \
				fi; \
				echo "⏳ Still waiting for Docker ($$i/6)..."; \
				sleep 5; \
			done; \
		elif [ "$$(uname)" = "Linux" ]; then \
			echo "🐧 Starting Docker service on Linux..."; \
			if command -v systemctl > /dev/null 2>&1; then \
				sudo systemctl start docker && echo "✅ Docker service started!"; \
			elif command -v service > /dev/null 2>&1; then \
				sudo service docker start && echo "✅ Docker service started!"; \
			else \
				echo "❌ Cannot auto-start Docker. Please start Docker manually."; \
				exit 1; \
			fi; \
		else \
			echo "❌ Unsupported OS. Please start Docker manually."; \
			exit 1; \
		fi; \
		if ! docker info > /dev/null 2>&1; then \
			echo "❌ Docker failed to start. Please start Docker Desktop manually."; \
			echo "💡 After starting Docker, run: make docker-cleanup && make local-up"; \
			exit 1; \
		fi; \
	fi

# Enhanced cleanup with conflict detection
docker-cleanup: check-docker
	@echo "🧹 Running Docker cleanup to prevent conflicts..."
	@chmod +x ./docker/scripts/cleanup.sh 2>/dev/null || true
	@./docker/scripts/cleanup.sh || ( \
		echo "🔧 Fallback cleanup for WSL/Windows..."; \
		docker compose --profile local down --remove-orphans || true; \
		docker container prune -f || true; \
		docker network prune -f || true; \
		echo "✅ Cleanup complete"; \
	)

# Start Oxigraph knowledge graph database
oxigraph-up: check-docker
	@docker compose --profile local up -d oxigraph || (echo "❌ Failed to start Oxigraph. Try: make docker-cleanup"; exit 1)
	@echo "✓ Oxigraph started on http://localhost:7878"

# Stop Oxigraph database
oxigraph-down: check-docker
	@docker compose --profile local stop oxigraph || true
	@echo "✓ Oxigraph stopped"

# Check Oxigraph container status
oxigraph-status: check-docker
	@echo "Oxigraph status:"
	@docker compose --profile local ps oxigraph

# Start all local development services
local-up: check-docker
	@echo "🚀 Starting local services..."
	@if ! docker compose --profile local up -d --timeout 60; then \
		echo "❌ Failed to start services. Running cleanup..."; \
		./docker/scripts/cleanup.sh; \
		echo "🔄 Retrying..."; \
		docker compose --profile local up -d --timeout 60 || (echo "❌ Still failing. Check Docker Desktop status."; exit 1); \
	fi
	@echo "✓ Local containers started"
	@echo ""
	@echo "🌟 Local environment ready!"
	@echo "✓ Services available at:"
	@echo "  - Oxigraph (Knowledge Graph): http://localhost:7878"
	@echo "  - YasGUI (SPARQL Editor): http://localhost:3000"
	@echo "  - PostgreSQL (Agent Memory): localhost:5432"
	@echo "  - Dagster (Orchestration): http://localhost:3001"
	@echo "  - Docker Models (Airgapped AI): ai/gemma3 ready via 'docker model run'"

# View logs from all local services
local-logs: check-docker
	@docker compose --profile local logs -f

# Stop all local services without removing containers
local-stop: check-docker
	@docker compose --profile local stop
	@echo "✓ All local services stopped"

# Stop and remove all local service containers
local-down: check-docker
	@docker compose --profile local down --timeout 10 || true
	@echo "✓ All local services stopped"

local-clean: check-docker
	@docker compose --profile local down -v --timeout 10 || true
	@echo "✓ All local services stopped and volumes removed"

local-reload: check-docker
	@docker compose --profile local down -v
	@make local-up
	@echo "✓ Local services reloaded"

# Start ABI in container mode
container-up:
	@docker compose --profile container up -d
	@echo "✓ ABI container started"

# Stop ABI container
container-down:
	@docker compose --profile container down
	@echo "✓ ABI container stopped"

# Docker AI models are managed by Compose specification
model-up: check-docker
	@echo "🤖 Docker AI models are managed by Compose specification"
	@echo "💡 Models auto-start when services with model dependencies launch"
	@echo "✓ Use 'make container-up' to start services with AI models"

# Stop Docker AI models
model-down: check-docker
	@echo "🛑 Docker AI models are managed by Compose specification"
	@echo "💡 Models stop automatically when services are stopped"
	@echo "✓ Use 'make container-down' to stop services and their models"

# Check Docker AI models status
model-status: check-docker
	@echo "🤖 Docker AI models status:"
	@echo "💡 Models are managed by Compose - check service status:"
	@docker compose ps abi 2>/dev/null || echo "ABI service not running"
	@echo "💡 Available models:"
	@docker model ls

# =============================================================================
# DAGSTER DATA ORCHESTRATION
# =============================================================================

# Start Dagster development server in foreground
dagster-dev:
	@echo "🚀 Starting Dagster development server..."
	@docker compose --profile local up dagster

# Start Dagster in background mode
dagster-up:
	@echo "🚀 Starting Dagster in background..."
	@docker compose --profile local up -d dagster
	@echo "✓ Dagster started on http://localhost:3001"
	@echo "📝 Logs: make dagster-logs"

# Stop Dagster background service
dagster-down:
	@echo "🛑 Stopping Dagster..."
	@docker compose --profile local down dagster
	@echo "✓ Dagster stopped"

# View Dagster service logs
dagster-logs:
	@echo "📄 Showing Dagster logs..."
	@docker compose --profile local logs -f dagster

# Open Dagster web interface
dagster-ui:
	@echo "🌐 Opening Dagster web interface..."
	@echo "📍 Visit: http://localhost:3001"
	@command -v open >/dev/null 2>&1 && open "http://localhost:3001" || echo "Open the URL manually in your browser"
	@docker compose --profile local up dagster

# Check status of Dagster assets
dagster-status:
	@echo "📊 Checking Dagster asset status..."
	@docker compose --profile local exec dagster uv run dagster asset list -m src.marketplace.__demo__.orchestration.definitions

# Materialize all Dagster assets
dagster-materialize:
	@echo "⚙️ Materializing all Dagster assets..."
	@docker compose --profile local exec dagster uv run dagster asset materialize --select "*" -m src.marketplace.__demo__.orchestration.definitions

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

# =============================================================================
# CLEANUP & MAINTENANCE
# =============================================================================

# Clean up build artifacts, caches, and Docker containers
clean:
	@echo "Cleaning up build artifacts..."
	rm -rf __pycache__ .pytest_cache build dist *.egg-info lib/.venv .venv .mypy_cache
	sudo find . -name "*.pyc" -delete
	sudo find . -name "__pycache__" -delete
	docker compose down
	docker compose rm -f
	rm -f dagster.pid dagster.log

# =============================================================================
# PHONY TARGETS
# =============================================================================
# Declare all targets as phony to avoid conflicts with files of the same name

.PHONY: test chat-abi-agent chat-naas-agent chat-ontology-agent chat-support-agent chat-qwen-agent chat-deepseek-agent chat-gemma-agent api sh lock add abi-add help uv oxigraph-up oxigraph-down oxigraph-status local-up local-down container-up container-down model-up model-down model-status airgap dagster-dev dagster-up dagster-down dagster-ui dagster-logs dagster-status dagster-materialize create-module create-agent create-integration create-workflow create-pipeline create-ontology
