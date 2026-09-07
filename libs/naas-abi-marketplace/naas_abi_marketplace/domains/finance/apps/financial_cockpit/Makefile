# financial-cockpit — Next.js finance / pilotage dashboard template.
# All web commands run inside ./web; R2 seeding runs the standalone script.
# Demo-data scripts mirror the frontend sidebar sections (see config.yaml).

WEB := web
# Override if your interpreter is named differently: `make demo-data PYTHON=python`
PYTHON ?= python3

.PHONY: help kickstart dev build lint typecheck preview push-r2 push-r2-dry demo-data

help:  ## list targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

kickstart:  ## generate config.yaml + .env, then print next steps
	cd $(WEB) && npm run kickstart

dev:  ## install deps (first run) + start the local dev server on :3000
	cd $(WEB) && npm install && npm run dev

build:  ## production build
	cd $(WEB) && npm install && npm run build

lint:  ## eslint
	cd $(WEB) && npm run lint

typecheck:  ## tsc --noEmit
	cd $(WEB) && npm run typecheck

preview:  ## Cloudflare Workers preview (OpenNext)
	cd $(WEB) && npm run preview

demo-data:  ## regenerate the fabricated demo datasets in ./web/data (order matters)
	$(PYTHON) scripts/performance/balance_sheet.py
	$(PYTHON) scripts/performance/cash_flow.py
	$(PYTHON) scripts/performance/financial_ratios.py
	$(PYTHON) scripts/pilotage/forecast.py
	$(PYTHON) scripts/pilotage/scenario_analysis.py
	$(PYTHON) scripts/pilotage/cost_centers.py
	$(PYTHON) scripts/treasury/cash_position.py
	$(PYTHON) scripts/treasury/cash_forecast.py
	$(PYTHON) scripts/treasury/financing.py
	$(PYTHON) scripts/operations/customer_invoices.py
	$(PYTHON) scripts/operations/supplier_invoices.py
	$(PYTHON) scripts/operations/expenses.py
	$(PYTHON) scripts/operations/procurement.py
	$(PYTHON) scripts/comptabilite/fixed_assets.py
	$(PYTHON) scripts/comptabilite/general_ledger.py
	$(PYTHON) scripts/comptabilite/journal_entries.py
	$(PYTHON) scripts/comptabilite/financial_close.py
	$(PYTHON) scripts/administration/settings.py

push-r2-dry:  ## show what a push to R2 would upload (no writes)
	$(PYTHON) scripts/push_to_r2.py --dry-run

push-r2:  ## seed the R2 bucket from ./web/data (needs R2_* env vars)
	$(PYTHON) scripts/push_to_r2.py
