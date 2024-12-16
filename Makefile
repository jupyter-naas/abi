.venv:
	@ docker compose run abi poetry install

install:
	@ docker compose run abi poetry install
	@ docker compose run abi poetry update abi

abi-add: .venv
	@ docker compose run abi bash -c 'cd lib && poetry add $(dep) && poetry lock --no-update'

add:
	@ docker compose run abi bash -c 'poetry add $(dep) && poetry lock --no-update'

lock:
	@ docker compose run abi poetry lock --no-update

path=tests/
test:
	@ docker compose run abi poetry run pytest $(path)

sh: .venv
	@ docker compose run -it abi bash
  
api: .venv
	@ docker compose run -p 9879:9879 abi poetry run api

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

chat-integration-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run chat-integration-agent'

chat-support-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run chat-support-agent'

chat-supervisor-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run chat-supervisor-agent'

chat-onedrive-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run chat-onedrive-agent'

chat-naas-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run chat-naas-agent'

.DEFAULT_GOAL := chat-integration-agent

.PHONY: test chat-supervisor-agent chat-support-agent chat-integration-agent chat-content-agent chat-finance-agent chat-growth-agent chat-opendata-agent chat-operations-agent chat-sales-agent chat-onedrive-agent chat-naas-agent api sh lock add abi-add