
DEPENDENCIES = src/core/integrations/siteanalyzer/target/wheels/siteanalyzer-*.whl

src/core/integrations/siteanalyzer/target/wheels/siteanalyzer-*.whl:
	@ make -C src/core/integrations/siteanalyzer release

.venv: $(DEPENDENCIES)
	#@ make src/core/integrations/siteanalyzer/target/wheels/siteanalyzer-*.whl
	@ docker compose run --rm --remove-orphans abi poetry install
	@ docker compose run --rm --remove-orphans abi bash -c 'poetry run python -m pip install --force-reinstall /app/src/core/integrations/siteanalyzer/target/wheels/*.whl'

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
build.linux.x86_64:
	docker build . -t abi -f Dockerfile.linux.x86_64 --platform linux/amd64

# -------------------------------------------------------------------------------------------------

chat-supervisor-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run chat-supervisor-agent'

chat-support-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run chat-support-agent'

chat-content-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run chat-content-agent'

chat-finance-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run chat-finance-agent'

chat-growth-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run chat-growth-agent'

chat-opendata-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run chat-opendata-agent'

chat-operations-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run chat-operations-agent'

chat-sales-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run chat-sales-agent'

chat-airtable-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run chat-airtable-agent'

chat-algolia-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run chat-algolia-agent'

chat-aws-s3-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run chat-aws-s3-agent'

chat-clockify-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run chat-clockify-agent'

chat-discord-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run chat-discord-agent'

chat-github-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run chat-github-agent'

chat-gladia-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run chat-gladia-agent'

chat-gmail-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run chat-gmail-agent'

chat-google-analytics-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run chat-google-analytics-agent'

chat-google-calendar-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run chat-google-calendar-agent'

chat-google-drive-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run chat-google-drive-agent'

chat-google-sheets-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run chat-google-sheets-agent'

chat-harvest-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run chat-harvest-agent'

chat-hubspot-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run chat-hubspot-agent'

chat-linkedin-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run chat-linkedin-agent'

chat-naas-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run chat-naas-agent'

chat-news-api-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run chat-news-api-agent'

chat-notion-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run chat-notion-agent'

chat-onedrive-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run chat-onedrive-agent'

chat-pennylane-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run chat-pennylane-agent'

chat-pipedrive-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run chat-pipedrive-agent'

chat-postgres-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run chat-postgres-agent'

chat-qonto-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run chat-qonto-agent'

chat-serper-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run chat-serper-agent'

chat-slack-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run chat-slack-agent'

chat-stripe-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run chat-stripe-agent'

chat-supabase-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run chat-supabase-agent'

chat-yahoo-finance-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run chat-yahoo-finance-agent'

chat-youtube-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run chat-youtube-agent'

chat-zerobounce-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run chat-zerobounce-agent'

chat-sendgrid-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run chat-sendgrid-agent'

chat-plotly-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run chat-plotly-agent'

chat-matplotlib-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run chat-matplotlib-agent'

chat-mercury-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run chat-mercury-agent'

chat-agicap-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run chat-agicap-agent'

chat-brevo-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run chat-brevo-agent'

chat-mailchimp-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run chat-mailchimp-agent'

chat-instagram-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run chat-instagram-agent'

chat-whatsapp-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run chat-whatsapp-agent'

chat-glassdoor-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run chat-glassdoor-agent'

chat-powerpoint-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run chat-powerpoint-agent'

chat-osint-investigator-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run python -m src.core.apps.terminal_agent.main generic_run_agent OSINTInvestigatorAssistant'


.DEFAULT_GOAL := chat-supervisor-agent

.PHONY: test chat-supervisor-agent chat-support-agent chat-content-agent chat-finance-agent chat-growth-agent chat-opendata-agent chat-operations-agent chat-sales-agent api sh lock add abi-add