.venv:
	docker compose run abi poetry install

abi-add: .venv
	docker compose run abi bash -c 'cd lib && poetry add $(dep) && poetry lock --no-update'

add:
	docker compose run abi bash -c 'poetry add $(dep) && poetry lock --no-update'

lock:
	docker compose run abi poetry lock --no-update

sh: .venv
	docker compose run -it abi bash

chat-single-agent: .venv
	docker compose run abi bash -c 'poetry install && poetry run chat-single-agent'

chat-supervisor-agent: .venv
	docker compose run abi bash -c 'poetry install && poetry run chat-supervisor-agent'

.DEFAULT_GOAL := chat-single-agent
