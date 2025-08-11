# Git hooks setups

.git/hooks/pre-commit:
	@mkdir -p .git/hooks
	@echo 'cd "$(git rev-parse --show-toplevel)" || exit 1;make check' > .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit


git-deps: .git/hooks/pre-commit

###############@

deps: uv git-deps .venv .env

# Make sure uv exists otherwise tell the user to install it.
uv:
	@if ! command -v uv >/dev/null 2>&1; then \
		echo "🚀 Oops! Looks like uv is missing from your system!"; \
		echo "📚 Don't worry - you can get it here: https://docs.astral.sh/uv/getting-started/installation/"; \
		exit 1; \
	fi
	@ uv python find 3.10 > /dev/null || (uv python install 3.10 && uv python pin 3.10)

.env:
	@# .env will be created dynamically by CLI during first boot

.venv:
	@ uv sync --all-extras

python_version=$(shell cat .python-version)
.venv/lib/python$(python_version)/site-packages/abi: deps
	@[ -L .venv/lib/python$(python_version)/site-packages/abi ] || ln -s `pwd`/lib/abi .venv/lib/python$(python_version)/site-packages/abi 


install: dep
	@ uv sync

dev-build: deps
	@ docker compose build

abi-add: deps
	cd lib && uv add $(dep) && uv lock

add: deps
	uv add $(dep) && uv lock

lock: deps
	@ uv lock

path=tests/
test:  deps
	@ uv run python -m pytest .

test-abi: deps
	@ uv run python -m pytest lib

test-api: deps
	@ uv run python -m pytest src/api_test.py -v -s

hello:
	@echo 'hello' | make

q=''
ftest: deps
	@ uv run python -m pytest $(shell find lib src tests -name '*_test.py' -type f | fzf -q $(q)) $(args)

fmt: deps
	@ uvx ruff format

#########################
# Linting, Static Analysis, Security
#########################

check: deps .venv/lib/python$(python_version)/site-packages/abi check-core check-custom

check-core: deps
	@echo ""
	@echo "  _____ _____ _____ _____"
	@echo " |     |     |     |     |"
	@echo " |  C  |  O  |  R  |  E  |"
	@echo " |_____|_____|_____|_____|"
	@echo ""
	@echo "\033[1;4m🔍 Running code quality checks...\033[0m\n"
	@echo "📝 Linting with ruff..."
	@uvx ruff check lib src/core

	@echo "\n\033[1;4m🔍 Running static type analysis...\033[0m\n"
	@echo "• Checking lib.abi..."
	@.venv/bin/mypy -p lib.abi --follow-untyped-imports
	@echo "• Checking src.core..."
	@.venv/bin/mypy -p src.core --follow-untyped-imports

	@echo "\n⚠️ Skipping pyrefly checks (disabled)"
	@#uv run pyrefly check lib src tests

	@echo "\n\033[1;4m🔍 Running security checks...\033[0m\n"
	@echo "⚠️ Skipping bandit... (disabled)"
	@#@docker run --rm -v `pwd`:/data --workdir /data ghcr.io/pycqa/bandit/bandit -c bandit.yaml src/core lib -r
	@echo "\n✅ CORE security checks passed!"

check-custom: deps
	@echo ""
	@echo "  _____ _____ _____ _____ _____ _____"
	@echo " |     |     |     |     |     |     |"
	@echo " |  C  |  U  |  S  |  T  |  O  |  M  |"
	@echo " |_____|_____|_____|_____|_____|_____|"
	@echo ""
	@echo "\n\033[1;4m🔍 Running code quality checks...\033[0m\n"
	@echo "📝 Linting with ruff..."
	@uvx ruff check src/custom

	@echo "\n\033[1;4m🔍 Running static type analysis...\033[0m\n"
	@.venv/bin/mypy -p src.custom --follow-untyped-imports

	@echo "\n⚠️ Skipping pyrefly checks (disabled)"
	@#uv run pyrefly check src/custom

	@echo "\n✅ CUSTOM security checks passed!"

bandit:
	@docker run --rm -v `pwd`:/data --workdir /data ghcr.io/pycqa/bandit/bandit -c bandit.yaml tests src/ lib -r


trivy-container-scan: build
	docker save abi:latest -o abi.tar && trivy image --input abi.tar && rm abi.tar

#########################

api: deps
	uv run src/api.py

api-prod: deps
	@ docker build -t abi-prod -f Dockerfile.linux.x86_64 . --platform linux/amd64
	@ docker run --rm -it -p 9879:9879 --env-file .env -e ENV=prod --platform linux/amd64 abi-prod

api-dev: deps
	@ docker build -t abi-dev -f Dockerfile.linux.x86_64 . --platform linux/amd64
	@ docker run --rm -it -p 9879:9879 -v ./storage:/app/storage --env-file .env -e ENV=dev --platform linux/amd64 abi-dev

sparql-terminal: deps
	@ uv run python -m src.core.apps.sparql_terminal.main	

oxigraph-admin: deps
	@ uv run python -m src.core.apps.oxigraph_admin.main

oxigraph-explorer:
	@echo "🚀 Opening Knowledge Graph Explorer..."
	@echo "📍 Visit: http://localhost:7878/explorer/"
	@echo "✨ Features:"
	@echo "   • Interactive overview dashboard"
	@echo "   • Full-featured YasGUI SPARQL editor"
	@echo "   • Pre-built query library with explanations"
	@command -v open >/dev/null 2>&1 && open "http://localhost:7878/explorer/" || echo "Open the URL manually in your browser"


dvc-login: deps
	@ uv run run python scripts/setup_dvc.py | sh

datastore-pull: deps
	@ echo "Pulling datastore..."
	@ docker compose run --rm --remove-orphans abi bash -c 'uv run --no-dev python scripts/datastore_pull.py | sh'

datastore-push: deps datastore-pull
	@ echo "Pushing datastore..."
	@ docker compose run --rm --remove-orphans abi bash -c 'uv run run --no-dev python scripts/datastore_push.py | sh'

storage-pull: deps
	@ echo "Pulling storage..."
	@ docker compose run --rm --remove-orphans abi bash -c 'uv run --no-dev python scripts/storage_pull.py | sh'

storage-push: deps storage-pull
	@ echo "Pushing storage..."
	@ docker compose run --rm --remove-orphans abi bash -c 'uv run run --no-dev python scripts/storage_push.py | sh'

triplestore-prod-remove: deps
	@ echo "Removing production triplestore..."
	@ docker compose run --rm --remove-orphans abi bash -c 'uv run --no-dev python scripts/triplestore_prod_remove.py'

triplestore-prod-override: deps
	@ echo "Overriding production triplestore..."
	@ docker compose run --rm --remove-orphans abi bash -c 'uv run --no-dev python scripts/triplestore_prod_override.py'

triplestore-prod-pull: deps
	@ echo "Pulling production triplestore..."
	@ docker compose run --rm --remove-orphans abi bash -c 'uv run --no-dev python scripts/triplestore_prod_pull.py'

triplestore-export-excel: deps
	@ echo "Exporting triplestore to Excel..."
	@ uv run python scripts/export_triplestore_excel.py

triplestore-export-turtle: deps
	@ echo "Exporting triplestore to turtle..."
	@ uv run python scripts/export_triplestore_turtle.py

docs-ontology: deps
	@ echo "Generating ontology documentation..."
	@ uv run python scripts/generate_docs.py

publish-remote-agents: deps
	@ echo "Publishing remote agents..."
	@ uv run python scripts/publish_remote_agents.py

clean:
	@echo "Cleaning up build artifacts..."
	rm -rf __pycache__ .pytest_cache build dist *.egg-info lib/.venv .venv
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -delete
	docker compose down
	docker compose rm -f
	rm -rf src/core/modules/common/integrations/siteanalyzer/target

help:
	@echo "ABI Project Makefile Help"
	@echo "=========================="
	@echo ""
	@echo "ENVIRONMENT SETUP:"
	@echo "  .venv                    Create virtual environment (automatically called by other commands)"
	@echo "  install                  Install all dependencies (similar to .venv)"
	@echo "  dev-build                Build all Docker containers defined in docker-compose.yml"
	@echo "  lock                     Update the Poetry lock file without installing packages"
	@echo ""
	@echo "DEVELOPMENT:"
	@echo "  api                      Start the API server on port 9879 for local development"
	@echo "  api-prod                 Build and run the production API server in a Docker container"
	@echo "  sparql-terminal          Open an interactive SPARQL terminal for querying the triplestore"
	@echo "  oxigraph-admin           Open Oxigraph administrative interface for monitoring and management"
	@echo "  oxigraph-explorer        Open unified Knowledge Graph Explorer with iframe integration"
	@echo ""
	@echo ""
	@echo "TESTING:"
	@echo "  test                     Run all Python tests using pytest"
	@echo ""
	@echo "DATA MANAGEMENT:"
	@echo "  dvc-login                Set up Data Version Control (DVC) authentication"
	@echo "  storage-pull             Pull data from the remote storage"
	@echo "  storage-push             Push local data changes to the remote storage"
	@echo "  triplestore-prod-remove  Remove the production triplestore data"
	@echo "  triplestore-prod-override Override the production triplestore with local data"
	@echo "  triplestore-prod-pull    Pull triplestore data from production"
	@echo "  docs-ontology            Generate ontology documentation"
	@echo "  publish-remote-agents    Publish remote agents"
	@echo ""
	@echo "BUILDING:"
	@echo "  build                    Build the Docker image (alias for build.linux.x86_64)"
	@echo "  build.linux.x86_64       Build a Docker image for Linux x86_64 architecture"
	@echo ""
	@echo "AGENTS:"
	@echo "  chat-naas-agent          Start the Naas agent in terminal mode"
	@echo "  chat-abi-agent           Start the Abi agent in terminal mode (default target)"
	@echo "  chat-ontology-agent      Start the Ontology agent in terminal mode"
	@echo "  chat-support-agent       Start the Support agent in terminal mode"
	@echo ""
	@echo "LOCAL AGENTS (Ollama):"
	@echo "  chat-qwen-agent          Start Qwen3 8B agent (local, multilingual, coding)"
	@echo "  chat-deepseek-agent      Start DeepSeek R1 8B agent (local, reasoning, math)"
	@echo "  chat-gemma-agent         Start Gemma3 4B agent (local, lightweight, fast)"
	@echo ""
	@echo "DOCKER COMPOSE:"
	@echo "  oxigraph-up              Start Oxigraph container"
	@echo "  oxigraph-down            Stop Oxigraph container"
	@echo "  oxigraph-status          Check Oxigraph container status"
	@echo "  dev-up                   Start development services (Oxigraph, YasGUI)"
	@echo "  dev-down                 Stop development services"
	@echo "  container-up             Start ABI in container mode (if needed)"
	@echo "  container-down           Stop ABI container"
	@echo ""
	@echo "CLEANUP:"
	@echo "  clean                    Clean up build artifacts, caches, and Docker containers"
	@echo ""
	@echo "DEFAULT:"
	@echo "  The default target is chat-abi-agent (running 'make' starts ABI conversation)"

# Docker Build Commands
# -------------------
# These commands are used to build the Docker image for the ABI project

# Default build target that triggers the Linux x86_64 build
build: build.linux.x86_64

# Builds a Docker image for Linux x86_64 architecture
# Usage: make build.linux.x86_64
# 
# Parameters:
#   - Image name: abi
#   - Dockerfile: Dockerfile.linux.x86_64
#   - Platform: linux/amd64 (ensures consistent builds on x86_64/amd64 architecture)
build.linux.x86_64: deps
	DOCKER_BUILDKIT=1 docker build . -t abi -f Dockerfile.linux.x86_64 --platform linux/amd64
	
	@# Show container size
	@docker image ls abi

# -------------------------------------------------------------------------------------------------

chat-naas-agent: deps
	@ uv run python -m src.core.apps.terminal_agent.main generic_run_agent NaasAgent

chat-abi-agent: deps
	@uv run python -m src.core.apps.startup_sequence.main
	@ LOG_LEVEL=CRITICAL uv run python -m src.cli

chat-ontology-agent: deps
	@ uv run python -m src.core.apps.terminal_agent.main generic_run_agent OntologyAgent

chat-support-agent: deps
	@ uv run python -m src.core.apps.terminal_agent.main generic_run_agent SupportAgent

# Local Ollama-based agents for privacy-focused interactions
chat-qwen-agent: deps
	@ uv run python -m src.core.apps.terminal_agent.main generic_run_agent QwenAgent

chat-deepseek-agent: deps
	@ uv run python -m src.core.apps.terminal_agent.main generic_run_agent DeepSeekAgent

chat-gemma-agent: deps
	@ uv run python -m src.core.apps.terminal_agent.main generic_run_agent GemmaAgent

pull-request-description: deps
	@ echo "Generate the description of the pull request please." | uv run python -m src.core.apps.terminal_agent.main generic_run_agent PullRequestDescriptionAgent

default: deps help

console: deps
	@ LOG_LEVEL=ERROR uv run python -m src.cli

.DEFAULT_GOAL := chat-abi-agent

agent=AbiAgent
chat: deps
	@ uv run python -m src.core.apps.terminal_agent.main generic_run_agent $(agent)


# Docker Compose Commands
# -----------------------
# These commands manage Docker containers for development

oxigraph-up:
	@docker-compose --profile dev up -d oxigraph
	@echo "✓ Oxigraph started on http://localhost:7878"

oxigraph-down:
	@docker-compose --profile dev stop oxigraph
	@echo "✓ Oxigraph stopped"

oxigraph-status:
	@echo "Oxigraph status:"
	@docker-compose --profile dev ps oxigraph

dev-up:
	@docker-compose --profile dev up -d
	@echo "✓ All development containers started"

dev-down:
	@docker-compose --profile dev down
	@echo "✓ All development services stopped"

startup-sequence:
	@uv run python -m src.core.apps.startup_sequence.main

container-up:
	@docker-compose --profile container up -d
	@echo "✓ ABI container started"

container-down:
	@docker-compose --profile container down
	@echo "✓ ABI container stopped"

.PHONY: test chat-abi-agent chat-naas-agent chat-ontology-agent chat-support-agent chat-qwen-agent chat-deepseek-agent chat-gemma-agent api sh lock add abi-add help uv oxigraph-up oxigraph-down oxigraph-status dev-up dev-down container-up container-down
