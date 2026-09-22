.PHONY: deps test lint build
deps:
	uv sync --group dev
test:
	uv run pytest tests -q
lint:
	uv run ruff check .
build:
	uv build

generate:
	uvx --from 'grpcio-tools==1.78.0' python -m grpc_tools.protoc -I . --python_out=. --pyi_out=. naas_abi_proto/*/v1/*.proto
	python tools/generate_clients.py
	uvx ruff check ../naas-abi-sdk/naas_abi_sdk --fix
	uvx ruff format ../naas-abi-sdk/naas_abi_sdk
