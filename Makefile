.venv:
	docker compose run abi poetry install

add:
	docker compose run abi poetry add $(dep)

chat: .venv
	docker compose run abi bash -c 'poetry install && poetry run chat-single-assistant'

.DEFAULT_GOAL := chat