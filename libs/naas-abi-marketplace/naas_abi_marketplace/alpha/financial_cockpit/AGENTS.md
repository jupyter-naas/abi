# AGENTS — financial-cockpit

Conventions for building on this template. Read `README.md` first.

## Layout & naming
- Python package dir is snake_case (`financial_cockpit`) so it imports as
  `naas_abi_marketplace.alpha.financial_cockpit`. The user-facing app dir,
  Cloudflare worker, and manifest use the kebab name `financial-cockpit`.
- The web app is a standalone Next.js 15 project under `apps/financial-cockpit/web`
  — it is **not** a Python subpackage. ABI only carries `__init__.py`'s
  `Configuration` (demo creds + R2 target).

## Config is the source of truth
- Edit `web/config/config.example.yaml`, never the generated `config/config.yaml`
  (gitignored). Pages, sidebar sections, per-page WIP banners, and admin users
  all live there. The `predev`/`prebuild` npm hooks regenerate `config.yaml` via
  `scripts/ensure-config.mjs`, so the app always builds.

## Data
- Bundled demo datastore is `web/data`, keyed exactly like the R2 bucket
  (`globals/…`, `entities/<id>/…`). A page renders when its `pageId` is mapped in
  the entity `manifest.json` `datasets.pages` and the referenced JSON exists;
  empty `records` render an empty state (never crash).
- To add a real dataset: drop the JSON under `web/data/entities/<id>/<page>/…`,
  map it in that entity's `manifest.json`, and (for a new entity) add it to
  `web/data/globals/entities.json`.

## Auth
- Local template = shared demo password (`ADMIN_PASSWORD`), which mints a
  synthetic full-access admin session. There is no e-mail/magic-link path — do
  not re-introduce one for the template.

## Storage / deploy
- Keep all dataset I/O going through `web/lib/data/storage.ts` (the FS↔R2 port).
  Do not read the filesystem or R2 directly elsewhere.
- Seed prod with `scripts/push_to_r2.py`; extend `RUNTIME_OWNED_PREFIXES` there
  whenever the app starts writing a new runtime-owned key.
