.venv:
	@ docker compose run abi poetry install

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

chat-single-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run chat-single-agent'

chat-supervisor-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run chat-supervisor-agent'

.DEFAULT_GOAL := chat-single-agent

.PHONY: test chat-supervisor-agent chat-single-agent api sh lock add abi-add