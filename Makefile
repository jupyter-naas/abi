.venv:
	docker compose run abi poetry install

chat: chat-single-assistant
chat-single-assistant: .venv
	docker compose run abi bash -c 'poetry install && poetry run chat-single-assistant'

.DEFAULT_GOAL := chat