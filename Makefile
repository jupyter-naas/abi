.venv:
	@ docker compose run --rm --remove-orphans abi poetry install

dev-build:
	@ docker compose build

install:
	@ docker compose run --rm --remove-orphans abi poetry install
	@ docker compose run --rm --remove-orphans abi poetry update abi

abi-add: .venv
	@ docker compose run --rm abi bash -c 'cd lib && poetry add $(dep) && poetry lock'

add:
	@ docker compose run --rm abi bash -c 'poetry add $(dep) && poetry lock'

lock:
	@ docker compose run --rm --remove-orphans abi poetry lock

path=tests/
test: 
	@ docker compose run --rm --remove-orphans abi bash -c 'poetry run python -m pytest tests'



sh: .venv
	@ docker compose run --rm --remove-orphans -it abi bash
  
api: .venv
	@ docker compose run --rm --remove-orphans -p 9879:9879 abi poetry run api

api-prod:
	@ docker build -t abi-prod -f Dockerfile.linux.x86_64 . --platform linux/amd64
	@ docker run --rm -it -p 9879:9879 --env-file .env -e ENV=prod --platform linux/amd64 abi-prod

sparql-terminal: .venv
	@ docker compose run --rm --remove-orphans -it abi bash -c 'poetry run python -m src.core.apps.sparql_terminal.main'

dvc-login: .venv
	@ docker compose run --rm --remove-orphans  abi bash -c 'poetry run python scripts/setup_dvc.py | sh'

storage-pull: .venv
	@ echo "Pulling storage..."
	@ docker compose run --rm --remove-orphans abi bash -c 'poetry run python scripts/storage_pull.py | sh'

storage-push: .venv storage-pull
	@ echo "Pushing storage..."
	@ docker compose run --rm --remove-orphans  abi bash -c 'poetry run python scripts/storage_push.py | sh'

triplestore-prod-remove: .venv
	@ echo "Removing production triplestore..."
	@ docker compose run --rm -it --remove-orphans  abi bash -c 'poetry run python scripts/triplestore_prod_remove.py'

triplestore-prod-override: .venv
	@ echo "Overriding production triplestore..."
	@ docker compose run -it --rm --remove-orphans  abi bash -c 'poetry run python scripts/triplestore_prod_override.py'

triplestore-prod-pull: .venv
	@ echo "Pulling production triplestore..."
	@ docker compose run --rm --remove-orphans abi bash -c 'poetry run python scripts/triplestore_prod_pull.py'

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
	@echo "  dev-build                Build all Docker containers defined in docker-compose.yml"
	@echo "  install                  Install all dependencies and update the abi package"
	@echo "  add dep=<package>        Add a new dependency to the project"
	@echo "  abi-add dep=<package>    Add a new dependency to the lib directory"
	@echo "  lock                     Update the Poetry lock file without installing packages"
	@echo ""
	@echo "DEVELOPMENT:"
	@echo "  sh                       Open an interactive bash shell in the ABI Docker container"
	@echo "  api                      Start the API server on port 9879 for local development"
	@echo "  api-prod                 Build and run the production API server in a Docker container"
	@echo "  sparql-terminal          Open an interactive SPARQL terminal for querying the triplestore"
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
	@echo ""
	@echo "BUILDING:"
	@echo "  build                    Build the Docker image (alias for build.linux.x86_64)"
	@echo "  build.linux.x86_64       Build a Docker image for Linux x86_64 architecture"
	@echo ""
	@echo "AGENTS:"
	@echo "  chat-naas-agent          Start the Naas agent in terminal mode"
	@echo "  chat-supervisor-agent    Start the Supervisor agent in terminal mode (default target)"
	@echo "  chat-ontology-agent      Start the Ontology agent in terminal mode"
	@echo "  chat-support-agent       Start the Support agent in terminal mode"
	@echo ""
	@echo "CLEANUP:"
	@echo "  clean                    Clean up build artifacts, caches, and Docker containers"
	@echo ""
	@echo "DEFAULT:"
	@echo "  The default target is help (running 'make' with no arguments displays this help menu)"

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
build.linux.x86_64: .venv
	docker build . -t abi -f Dockerfile.linux.x86_64 --platform linux/amd64

# -------------------------------------------------------------------------------------------------

chat-naas-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run python -m src.core.apps.terminal_agent.main generic_run_agent NaasAgent'

chat-supervisor-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run python -m src.core.apps.terminal_agent.main generic_run_agent SupervisorAgent'

chat-ontology-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run python -m src.core.apps.terminal_agent.main generic_run_agent OntologyAgent'

chat-support-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run python -m src.core.apps.terminal_agent.main generic_run_agent SupportAgent'

chat-multi-model-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run python -m src.core.apps.terminal_agent.main generic_run_agent MultiModelAgent'

chat: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run python -m src.core.apps.terminal_agent.main generic_run_agent $(agent)'

.DEFAULT_GOAL := help

.PHONY: test chat-supervisor-agent chat-support-agent api sh lock add abi-add help
