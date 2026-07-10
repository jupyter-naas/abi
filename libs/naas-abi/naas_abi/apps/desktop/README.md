# ABI Desktop

ABI Desktop is a standalone local app: a lightweight Nexus with Chat, Code, and Knowledge Graph sections. One process runs a FastAPI backend, a vanilla JS web UI, and an optional native window (pywebview). AI runs through a locally spawned harness (`opencode` or `pi`); you bring your own binary and provider keys. Persistence uses SQLite and an embedded Oxigraph triple store. No Postgres, Docker, or full Nexus stack required.

For architecture, API surface, harness layer, and development conventions, see [AGENTS.md](AGENTS.md).

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (repo Python toolchain)
- `opencode` on `PATH` for live chat (optional for unit tests)
- [Ollama](https://ollama.com/) for local models (optional)

Install repo dependencies from the repository root:

```bash
uv sync --all-extras
```

## Quick start (browser dev)

Recommended daily workflow: run from source in your browser. No PyInstaller rebuild required.

```bash
# from repo root
uv run python libs/naas-abi/naas_abi/apps/desktop/run.py --browser-only
```

Open [http://127.0.0.1:54242](http://127.0.0.1:54242). Override the port with `ABI_DESKTOP_PORT` if needed.

Useful flags:

```bash
# print URL only (no auto-open)
uv run python libs/naas-abi/naas_abi/apps/desktop/run.py --browser-only --no-open-browser

# auto-reload Python on save
uv run python libs/naas-abi/naas_abi/apps/desktop/run.py --browser-only --reload
```

## Folder map

```
desktop/
  config/       Paths, data dir (~/.abi-desktop), workspace bootstrap
  core/         Domain: SQLite store, Oxigraph graph, integrations, doctor
  api/          FastAPI app factory (create_app) + static mount
  harness/      Hexagonal harness port/adapters (opencode, pi, hermes stub)
  gui/web/      Vanilla JS SPA (index.html, app.js, style.css, vendor/)
  ontology/     Bundled TTL for PyInstaller and BFO7 routing
  scripts/      test.sh, coverage-kpi.sh, smoke_chat.sh
```

## Testing

Run the full desktop suite with coverage from the repository root:

```bash
./libs/naas-abi/naas_abi/apps/desktop/scripts/test.sh
```

Or via Make:

```bash
make test-desktop
```

Expected output ends with:

```
237 passed, 0 failed
TOTAL coverage 90%
```

The script writes coverage and junit artifacts under `desktop/`:

- `.coverage-report.json` for programmatic KPIs
- `.test-results.xml` for pass/fail counts

CI one-liner (after `test.sh`):

```bash
./libs/naas-abi/naas_abi/apps/desktop/scripts/coverage-kpi.sh
# desktop_coverage=90.0 pass=237 fail=0
```

Single file or keyword runs pass through to pytest:

```bash
./libs/naas-abi/naas_abi/apps/desktop/scripts/test.sh core/store_test.py -k traversal
```

Tests import the top-level `desktop` package (see `conftest.py`). They are fast and hermetic: no live opencode, network, or GUI.

Manual chat smoke (requires a running instance and live opencode):

```bash
ABI_DESKTOP_URL=http://127.0.0.1:54242 ./libs/naas-abi/naas_abi/apps/desktop/scripts/smoke_chat.sh
```

## Native app build

See [build.md](build.md) when you need a compiled `.app` or executable. Not required for day-to-day development.
