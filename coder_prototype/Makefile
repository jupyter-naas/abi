# Coder embedding-prototype harness.
# Run from coder_prototype/. The provision targets shell out to the repo-root
# uv venv (the abi coding_environment service lives there).

ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/..)
CODER_URL ?= http://localhost:7080
TOKEN_FILE := $(ROOT)/coder_prototype/.coder-token

.PHONY: up bootstrap provision provision-inmem template headers edge down logs

up: ## Start postgres + coder (HTTP)
	docker compose up -d postgres coder

bootstrap: ## Create first user + capture a session token
	bash scripts/bootstrap.sh

provision: ## Headless provision via the abi coding_environment service
	cd $(ROOT) && CODER_SESSION_TOKEN=$$(cat $(TOKEN_FILE)) \
	  uv run --no-sync python coder_prototype/scripts/provision.py

provision-inmem: ## Same flow against the in-memory fake adapter (no Docker)
	cd $(ROOT) && uv run --no-sync python coder_prototype/scripts/provision.py --in-memory

template: ## Push the code-server Docker template into Coder
	docker compose cp template coder:/tmp/template
	docker compose exec -T -e CODER_URL=$(CODER_URL) -e CODER_SESSION_TOKEN=$$(cat $(TOKEN_FILE)) coder \
	  coder templates push abi-code-server -d /tmp/template --yes

headers: ## Empirically inspect framing headers (Coder CSP + code-server XFO)
	@echo "== Coder dashboard headers =="
	@curl -sI $(CODER_URL)/ | grep -iE 'content-security-policy|x-frame-options' || echo "(none)"
	@echo "== code-server headers (ephemeral container) =="
	@docker run --rm -d --name cs-probe -p 18080:8080 -e PASSWORD=x codercom/code-server:latest >/dev/null
	@sleep 6
	@curl -sI http://localhost:18080/ | grep -iE 'x-frame-options|content-security-policy' || echo "(no XFO / no frame-ancestors)"
	@docker rm -f cs-probe >/dev/null

edge: ## Add the Caddy HTTPS edge (lvh.me) for the browser embedding test
	CODER_ACCESS_URL=https://coder.lvh.me CODER_WILDCARD_ACCESS_URL='*.coder.lvh.me' \
	CODER_ADDITIONAL_CSP_POLICY='frame-ancestors https://app.lvh.me' \
	  docker compose --profile edge up -d

down: ## Tear everything down (including volumes)
	docker compose --profile edge down -v
	-docker rm -f cs-probe 2>/dev/null

logs: ## Tail Coder logs
	docker compose logs -f coder
