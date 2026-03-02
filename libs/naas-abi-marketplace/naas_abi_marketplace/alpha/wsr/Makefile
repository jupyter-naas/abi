# WSR — development launcher
# Usage:
#   make dev      start both services (FastAPI :8000 + Next.js :3000)
#   make stop     kill both services
#   make logs     tail logs for both services
#   make api      start FastAPI only
#   make ui       start Next.js only
#   make generate re-generate backend/ports/domain.py from ontology/wsr.ttl

PYTHON      ?= python
API_DIR     := backend
UI_DIR      := frontend
API_LOG     := /tmp/wsr-api.log
UI_LOG      := /tmp/wsr-ui.log
API_PID     := /tmp/wsr-api.pid
UI_PID      := /tmp/wsr-ui.pid

ONTO2PY     := $(shell cd ../../../.. && pwd)/.abi/abi/libs/naas-abi-core/naas_abi_core/utils/onto2py/onto2py.py
TTL         := ontology/wsr.ttl
DOMAIN_OUT  := backend/ports/domain.py

.PHONY: dev stop logs api ui generate

dev: stop
	@echo "▶  Starting FastAPI  (http://localhost:8000)"
	@cd $(API_DIR) && $(PYTHON) -m uvicorn main:app --reload --port 8000 > $(API_LOG) 2>&1 & echo $$! > $(API_PID)
	@echo "▶  Starting Next.js  (http://localhost:3000)"
	@cd $(UI_DIR) && npm run dev > $(UI_LOG) 2>&1 & echo $$! > $(UI_PID)
	@echo ""
	@echo "Both services running. Logs:"
	@echo "  API → $(API_LOG)"
	@echo "  UI  → $(UI_LOG)"
	@echo ""
	@echo "Run 'make logs' to follow both, 'make stop' to shut down."

api:
	@echo "▶  Starting FastAPI  (http://localhost:8000)"
	cd $(API_DIR) && $(PYTHON) -m uvicorn main:app --reload --port 8000

ui:
	@echo "▶  Starting Next.js  (http://localhost:3000)"
	cd $(UI_DIR) && npm run dev

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
