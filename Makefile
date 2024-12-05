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
chat: .venv
	docker compose run abi bash -c 'poetry install && poetry run chat-single-assistant'

.DEFAULT_GOAL := chat