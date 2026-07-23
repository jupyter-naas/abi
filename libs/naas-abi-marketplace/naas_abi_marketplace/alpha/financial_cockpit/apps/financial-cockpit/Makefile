# financial-cockpit — Next.js finance / pilotage dashboard template.
# All web commands run inside ./web; R2 seeding runs the standalone script.

WEB := web

.PHONY: help kickstart dev build lint typecheck preview push-r2 push-r2-dry

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

push-r2-dry:  ## show what a push to R2 would upload (no writes)
	python scripts/push_to_r2.py --dry-run

push-r2:  ## seed the R2 bucket from ./web/data (needs R2_* env vars)
	python scripts/push_to_r2.py
