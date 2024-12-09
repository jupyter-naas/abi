.venv:
	docker compose run abi poetry install

abi-add: .venv
	docker compose run abi bash -c 'cd lib && poetry add $(dep)'

add:
	docker compose run abi poetry add $(dep)

lock:
	docker compose run abi poetry lock --no-update

test:
	docker compose run abi poetry run pytest tests/

sh: .venv
	docker compose run -it abi bash
chat: .venv
	docker compose run abi bash -c 'poetry install && poetry run chat-single-assistant'

.DEFAULT_GOAL := chat

.PHONY: test