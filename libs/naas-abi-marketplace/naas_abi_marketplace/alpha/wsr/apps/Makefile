# WSR — development launcher + Cloudflare deployment
# Run from the apps/ directory:
#   make dev            start both services (FastAPI :8001 + Next.js :3043)
#   make stop           kill both services
#   make logs           tail logs for both
#   make api            start FastAPI only
#   make ui             start Next.js only
#   make generate       re-generate api/ports/domain.py from ../ontology/wsr.ttl
#
# Cloudflare deployment (requires wrangler + Docker running):
#   make deploy-api     build + push FastAPI container → Cloudflare Containers
#   make deploy-web     build + deploy Next.js → Cloudflare Workers (OpenNext)
#   make deploy         deploy both (api first, then web)
#   make preview-web    local preview of web in the workerd runtime

PYTHON      ?= python
API_DIR     := api
UI_DIR      := web
API_LOG     := /tmp/wsr-api.log
UI_LOG      := /tmp/wsr-ui.log
API_PID     := /tmp/wsr-api.pid
UI_PID      := /tmp/wsr-ui.pid

ONTO2PY     := $(shell cd ../../../../.. && pwd)/.abi/abi/libs/naas-abi-core/naas_abi_core/utils/onto2py/onto2py.py
TTL         := ../ontology/wsr.ttl
DOMAIN_OUT  := api/ports/domain.py

.PHONY: dev stop logs api ui generate deploy-api deploy-web deploy preview-web

dev: stop
	@echo "▶  Starting FastAPI  (http://localhost:8001)"
	@cd $(API_DIR) && $(PYTHON) -m uvicorn main:app --reload --port 8001 > $(API_LOG) 2>&1 & echo $$! > $(API_PID)
	@echo "▶  Starting Next.js  (http://localhost:3043)"
	@cd $(UI_DIR) && npm run dev -- --port 3043 > $(UI_LOG) 2>&1 & echo $$! > $(UI_PID)
	@echo ""
	@echo "Both services running. Logs:"
	@echo "  API → $(API_LOG)"
	@echo "  UI  → $(UI_LOG)"
	@echo ""
	@echo "Run 'make logs' to follow both, 'make stop' to shut down."

api:
	@echo "▶  Starting FastAPI  (http://localhost:8001)"
	cd $(API_DIR) && $(PYTHON) -m uvicorn main:app --reload --port 8001

ui:
	@echo "▶  Starting Next.js  (http://localhost:3043)"
	cd $(UI_DIR) && npm run dev -- --port 3043

stop:
	@if [ -f $(API_PID) ]; then \
		kill $$(cat $(API_PID)) 2>/dev/null && echo "■  FastAPI stopped" || true; \
		rm -f $(API_PID); \
	fi
	@if [ -f $(UI_PID) ]; then \
		kill $$(cat $(UI_PID)) 2>/dev/null && echo "■  Next.js stopped" || true; \
		rm -f $(UI_PID); \
	fi
	@pkill -f "uvicorn main:app" 2>/dev/null || true
	@pkill -f "next dev" 2>/dev/null || true

logs:
	@tail -f $(API_LOG) $(UI_LOG)

generate:
	@echo "▶  Generating domain types from $(TTL)"
	@$(PYTHON) $(ONTO2PY) $(TTL)
	@cp ontology/wsr.py $(DOMAIN_OUT)
	@echo "✅  Written → $(DOMAIN_OUT)"

# ---------------------------------------------------------------------------
# Cloudflare deployment
# ---------------------------------------------------------------------------

# Deploy the FastAPI backend as a Cloudflare Container.
# Docker must be running. On first deploy, wait ~3 min for provisioning.
deploy-api:
	@echo "▶  Deploying wsr-api container → Cloudflare"
	cd api-worker && npm install && npx wrangler deploy
	@echo ""
	@echo "✅  wsr-api deployed."
	@echo "    Get the URL with:  cd api-worker && npx wrangler containers list"
	@echo "    Set NEXT_PUBLIC_API_BASE_URL in web/wrangler.jsonc then run 'make deploy-web'."

# Deploy the Next.js frontend as a Cloudflare Worker via OpenNext.
# Ensure NEXT_PUBLIC_API_BASE_URL is set in web/wrangler.jsonc before running.
deploy-web:
	@echo "▶  Deploying wsr-web → Cloudflare Workers (OpenNext)"
	cd web && npm install && npm run deploy
	@echo "✅  wsr-web deployed."

# Deploy both. API must go first so its URL is known before building web.
deploy: deploy-api deploy-web

# Local workerd preview (closest to production, uses wrangler dev).
preview-web:
	cd web && npm install && npm run preview
