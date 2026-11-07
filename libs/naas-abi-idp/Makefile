.PHONY: deps test lint build
deps:
	uv sync --group dev
test:
	uv run pytest tests -q
lint:
	uvx ruff check .
build:
	uv build
