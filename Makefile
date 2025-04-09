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

.DEFAULT_GOAL := chat-supervisor-agent

.PHONY: test chat-supervisor-agent chat-support-agent api sh lock add abi-add
