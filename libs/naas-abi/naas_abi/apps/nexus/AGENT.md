# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

NEXUS is the multi-LLM agent platform vendored inside the **bob** workspace at `bob/.abi/libs/naas-abi/naas_abi/apps/nexus/`. The workspace-level `~/CLAUDE.md` already covers the broader ABI conventions (hexagonal architecture as a principle, `uv` toolchain, BFO ontology, code style). This file documents what is NEXUS-specific.

## Two execution modes (matters for imports)

NEXUS can run standalone **or** as a sub-package of the parent `naas-abi` package — the same code services both. Always use the fully qualified import path:

```python
from naas_abi.apps.nexus.apps.api.app.core.config import settings
```

Not `from app.core.config import settings`. The shorter form only works when running from inside `apps/api/`; the fully qualified form works in both modes. All existing code in `apps/api/app/` uses the long form — match it.

The standalone dev entrypoint is `apps/api/app/main.py` (`uvicorn app.main:app`, port 8000 via Makefile; port 9879 if run as `__main__`). When mounted into the parent naas-abi FastAPI app, `create_app(existing_app)` patches the parent in place rather than creating a new one.

## Commands

NEXUS has its own Makefile separate from the parent ABI Makefile. **Run from `apps/nexus/`, not from the workspace root.**

```bash
make install        # pnpm install + (cd apps/api && uv sync)
make db-up          # docker compose up -d postgres
make db-migrate     # runs init_db() — applies all apps/api/migrations/*.sql idempotently
make up             # kill-ports → ensure postgres → ./dev.sh (turbo runs api + web)
make api / make web # individual servers
make kill-ports     # frees 3000 (web) and 8000 (api)
make check          # lint + typecheck + test
make test-watch     # pytest --lf -x in apps/api/
make db-reset       # DESTRUCTIVE: docker compose down -v, then up + migrate + seed
```

Running a single backend test:
```bash
cd apps/api && uv run pytest tests/test_auth.py::test_login_succeeds -v
```

Type-check / lint a specific area:
```bash
cd apps/api && uv run mypy app/services/chat
cd apps/api && uv run ruff check app/services/chat
cd apps/web && pnpm typecheck
```

## Service layout — hexagonal, mid-migration

`apps/api/app/services/<domain>/` is the canonical home for business logic. Each domain follows:

```
services/<domain>/
  port.py                                      # Abstract IxxxPort interfaces + DTOs (dataclasses)
  service.py                                   # Domain logic, depends only on ports
  handlers/<domain>__http_handler.py           # Wires service + adapters + FastAPI router
  adapters/
    primary/<domain>__primary_adapter__FastAPI.py   # HTTP request/response mapping
    secondary/postgres.py                            # DB adapter implementing the port
```

The double-underscore naming `<domain>__primary_adapter__<Tech>.py` is intentional and used consistently — match it when adding new adapters (`<domain>__primary_adapter__streaming.py`, `<domain>__primary_adapter__export.py`, etc.).

**Migration is in progress** — see `apps/api/app/services/HEXAGONAL_MIGRATION_TASKS.md`. The legacy endpoint files in `apps/api/app/api/endpoints/` (`abi.py`, `admin.py`, `graph.py`, `secrets.py`, `view.py`, etc.) still contain orchestration logic that should move into domain services over time. `api/router.py` shows which domains have migrated to `services/<domain>/handlers/` (chat, agents, auth, files, modules, apps, providers, workspaces) versus the ones still living in `endpoints/`. When touching a legacy endpoint, check the migration doc before deciding whether to extract into a domain.

Per workspace policy: every abstract method on a port must be implemented in adapters — raise `NotImplementedError` for genuinely unsupported features rather than omitting the method.

## Database migrations

Plain SQL files at `apps/api/migrations/NNNN_description.sql`, applied in sequential order by `init_db()` on every API startup. Numbered ≥4 digits (currently up to 0029). Two non-negotiables:

1. **Idempotent** — use `IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`, etc. Migrations re-run on every boot.
2. **Sequential numbering** — never reuse a prefix. There is a known collision (`0016_link_workspaces_to_orgs.sql` + `0016_add_workspace_theming.sql`) — do not introduce more.

No Alembic, no rollback story — write forward-compatible migrations.

## SSE provider adapters

Chat streaming normalizes three protocols to a single `StreamEvent` shape — OpenAI's JSON-per-line, Anthropic's typed W3C SSE, and ABI/Naas's strict multi-line W3C SSE. Event types are `token | thinking | tool_call | link | file | error | done`. The adapter layer in `services/chat/adapters/primary/chat__primary_adapter__streaming.py` is where format-specific quirks live; the domain service operates only on the normalized events. See `docs/ESSENTIALS.md` for protocol examples.

## Multi-tenancy invariant

Everything below `organizations` is scoped to `workspace_id`: agents, conversations, secrets, graph nodes, inference servers. New tables and new endpoints **must** filter by `workspace_id` and check workspace membership via the IAM service (`services/iam/`, see `IAM_SPEC.md` and `authorization.py`). Do not add a second role-check at the endpoint when the IAM service already does it — duplicate checks are explicitly called out as anti-patterns in the migration doc.

## Frontend

Next.js 14 App Router under `apps/web/`. State is Zustand (`src/stores/*.ts`, one store per domain — `auth`, `workspace`, `agents`, etc.). Tenant branding (tab title, OG image, theme) is fetched from `/api/tenant` at SSR time in `layout.tsx` — bypass the API at your peril, it returns defaults on failure.

Cloudflare Pages deploy: `pnpm build:cf` then `wrangler pages deploy` (see `apps/web/package.json`, `wrangler.toml`). Standard `pnpm dev` runs Next.js on 3000.

## Conventional commits

NEXUS uses Conventional Commits enforced via `CONTRIBUTING.md` (`feat:`, `fix:`, `docs:`, `refactor:`, etc.) — match the style of recent commits when authoring messages.
