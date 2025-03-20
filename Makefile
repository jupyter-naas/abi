.venv: $(DEPENDENCIES)
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
	@ docker compose run --rm --remove-orphans abi poetry run pytest $(path)

sh: .venv
	@ docker compose run --rm --remove-orphans -it abi bash
  
api: .venv
	@ docker compose run --rm --remove-orphans -p 9879:9879 abi poetry run api


dvc-login: .venv
	@ docker compose run --rm --remove-orphans  abi bash -c 'poetry run python scripts/setup_dvc.py | sh'

storage-pull: .venv
	@ docker compose run --rm --remove-orphans abi bash -c 'poetry run python scripts/storage_pull.py | sh'

storage-push: .venv
	@ docker compose run --rm --remove-orphans  abi bash -c 'poetry run python scripts/storage_push.py | sh'

clean:
	docker compose down
	docker compose rm -f
	rm -rf src/core/modules/common/integrations/siteanalyzer/target
	rm -rf .venv
	rm -rf dist
	rm -rf lib/.venv
	docker compose build --no-cache

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

chat-supervisor-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run python -m src.core.apps.terminal_agent.main generic_run_agent SupervisorAssistant'

chat-support-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run python -m src.core.apps.terminal_agent.main generic_run_agent SupportAssistant'

chat-opendata-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run python -m src.core.apps.terminal_agent.main generic_run_agent OpenDataAssistant'

chat-osint-investigator-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run python -m src.core.apps.terminal_agent.main generic_run_agent OSINTInvestigatorAssistant'

chat-content-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run python -m src.core.apps.terminal_agent.main generic_run_agent ContentAssistant'

chat-growth-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run python -m src.core.apps.terminal_agent.main generic_run_agent GrowthAssistant'

chat-sales-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run python -m src.core.apps.terminal_agent.main generic_run_agent SalesAssistant'

chat-operations-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run python -m src.core.apps.terminal_agent.main generic_run_agent OperationsAssistant'

chat-finance-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run python -m src.core.apps.terminal_agent.main generic_run_agent FinanceAssistant'

chat-powerpoint-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run python -m src.core.apps.terminal_agent.main generic_run_agent PowerPointAssistant'

chat-trading-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run python -m src.core.apps.terminal_agent.main generic_run_agent StockTradingAgent'

.DEFAULT_GOAL := chat-supervisor-agent

.PHONY: test chat-supervisor-agent chat-support-agent chat-content-agent chat-finance-agent chat-growth-agent chat-opendata-agent chat-operations-agent chat-sales-agent api sh lock add abi-add