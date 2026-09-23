.PHONY: deps test lint build generate
deps:
	uv sync --group dev
test:
	uv run pytest tests -q
lint:
	uv run ruff check .
build:
	uv build

generate:
	uv run python tools/generate_services.py
	uv run ruff check --fix naas_abi_sdk/services
	uv run ruff format naas_abi_sdk/services
