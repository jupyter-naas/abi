# Financial Cockpit

A finance & **pilotage** dashboard app you can clone and build from. It ships a
self-contained Next.js app with bundled demo data, password-only local login
(no e-mail service), and a hexagonal **FS↔R2** storage boundary so the same UI
runs locally and on Cloudflare.

```
alpha/financial_cockpit/
├── __init__.py                     # ABIModule (module: naas_abi_marketplace.alpha.financial_cockpit)
└── apps/financial-cockpit/
    ├── Makefile                    # make kickstart / dev / build / push-r2
    ├── manifest.json               # marketplace catalog descriptor
    ├── scripts/push_to_r2.py       # seed a prod R2 bucket from local demo data
    └── web/                        # the Next.js app
        ├── config/config.example.yaml   # canonical app config (pages, sections, banners, users)
        ├── data/                        # bundled demo datastore (globals/ + entities/_demo/)
        ├── scripts/{kickstart,ensure-config}.mjs
        └── app/ components/ lib/ …
```

## Quickstart (local, no cloud, no e-mail)

```bash
cd apps/financial-cockpit
make kickstart          # creates web/config/config.yaml + web/.env (random SESSION_SECRET)
make dev                # npm install + next dev  →  http://localhost:3000
```

Open <http://localhost:3000/login> and sign in with the demo password (`demo`
by default — see `web/.env`). You land on the **Société Démo** perimeter with
demo P&L, treasury, and unpaid-invoice data.

The **kickstart CLI** (`web/scripts/kickstart.mjs`) is what makes the template
runnable: it generates `config/config.yaml` from the committed
`config.example.yaml`, and `.env` from `.env.example` with a fresh random
`SESSION_SECRET`. Both generated files are gitignored; `config.example.yaml` is
the source of truth you edit and commit.

## Configuration

Everything the app shows is driven by **`web/config/config.example.yaml`**:
`app.pages` (enabled pages + labels + optional WIP `banner`), `app.sections`
(the sidebar groups), and `users` (admin identities). Edit the example, then
re-run `make kickstart` (or delete `config/config.yaml` and let `predev`
regenerate it).

## Storage boundary (local → prod)

`web/lib/data/storage.ts` is the storage **port**, with two adapters chosen by
`ENV`:

| `ENV`    | Adapter | Source                                        |
|----------|---------|-----------------------------------------------|
| unset    | FS      | `web/data` (or `DATA_LOCAL_ROOT`)             |
| `prod`   | R2      | Cloudflare R2 bucket bound as `DATASETS`      |

To take demo data to production:

```bash
# 1. create the bucket once
wrangler r2 bucket create app-financial-cockpit
# 2. seed it from local demo data (dry-run first)
export R2_ACCOUNT_ID=… R2_ACCESS_KEY_ID=… R2_SECRET_ACCESS_KEY=… R2_BUCKET=app-financial-cockpit
make push-r2-dry
make push-r2
# 3. deploy the Worker (reads R2 when ENV=prod)
cd web && npm run preview     # or `opennextjs-cloudflare deploy`
```

`scripts/push_to_r2.py` skips unchanged objects (ETag) and never touches
runtime-owned keys (`globals/users.json`, `globals/pnl/…`, `user_annotations/…`).

## What was templated out of the source app

- Microsoft-Graph magic-link e-mail → **password-only** demo login.
- Real company datastore → **bundled `web/data`** demo datastore.
- Asgard-specific secrets/bindings → env-driven, documented in `.env.example`.
