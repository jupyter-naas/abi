.PHONY: deps test lint build
deps:
	uv sync --group dev
test:
	uv run pytest tests -q
lint:
	uv run ruff check .
build:
	uv build
