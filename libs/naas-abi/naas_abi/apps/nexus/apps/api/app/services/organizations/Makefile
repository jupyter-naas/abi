.PHONY: test

ROOT_DIR := $(shell git rev-parse --show-toplevel)
TEST_PATH := libs/naas-abi/naas_abi/apps/nexus/apps/api/app/services/organizations

test:
	cd "$(ROOT_DIR)" && uv run pytest "$(TEST_PATH)" -v
