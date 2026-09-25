.PHONY: deps demo test lint build
deps:
	uv sync --project ../.. --all-extras
demo:
	uv run --project ../.. --no-sync python run.py
test: demo
lint:
	uvx ruff check .
build:
	uv build --project ../../libs/naas-abi-proto
	uv build --project ../../libs/naas-abi-sdk
