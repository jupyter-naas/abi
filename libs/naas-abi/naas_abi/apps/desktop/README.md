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

**Canonical command** (idempotent: safe to run repeatedly; never kills a healthy server):

```bash
# from repo root — detached supervisor, Python hot reload, crash restart
make dev-desktop
# same as:
libs/naas-abi/naas_abi/apps/desktop/scripts/dev.sh start
# or:
libs/naas-abi/naas_abi/apps/desktop/scripts/ensure-dev.sh
```

Check status without restarting:

```bash
libs/naas-abi/naas_abi/apps/desktop/scripts/dev.sh status
```

Stop only when you explicitly want to shut down:

```bash
libs/naas-abi/naas_abi/apps/desktop/scripts/dev.sh stop
```

Open [http://127.0.0.1:54242](http://127.0.0.1:54242). Override the port with `ABI_DESKTOP_PORT` if needed.

Logs: `~/.abi-desktop/server.log`. Server metadata (URL, PID): `~/.abi-desktop/server.json`.

### Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `already running at http://127.0.0.1:54242` | Healthy server on port | No action needed; open the URL |
| `port 54242 in use by a non-ABI process` | Another app holds the port | Quit that app, or `dev.sh stop`, or set `ABI_DESKTOP_PORT` |
| `supervisor running but server unhealthy` | Stuck/crashed worker | `dev.sh stop` then `dev.sh start` |
| Server dies when a Cursor agent exits | Old supervisor not detached | Update to latest `dev.sh` (uses `start_new_session`) |
| `instance.lock` / graph LOCK errors | Two dev servers on same data dir | Run only one `dev.sh start`; use `dev.sh stop` to reset |
| Exit code 143 / SIGTERM in `server.log` | Agent killed the process group | Use `make dev-desktop` (detached supervisor), not foreground `uv run` in agent shells |

**Do not** call `dev.sh stop` unless you intend to shut down. Parallel `dev.sh start` calls are safe: they detect health and exit 0 without restarting.

Use the **workspace switcher** (icon rail top: logo only, Nexus-style) to open or switch IDE workspaces. The **status bar** (left) shows the current workspace basename and git branch as read-only context. Each workspace is a folder on disk (e.g. `~/abi`). In browser dev, **Open Folder…** accepts a typed path; in the pywebview app, **Browse…** opens the native folder picker.

**Reload behavior:**

- **Python** (`api/`, `core/`, `harness/`, `config/`): auto-restarts on save (`--reload` via `make dev-desktop`).
- **JS/CSS** (`gui/web/`): refresh the browser manually; no bundler.

Manual foreground run (no supervisor):

```bash
uv run python libs/naas-abi/naas_abi/apps/desktop/run.py --browser-only --reload
```

Useful flags:

```bash
# print URL only (no auto-open)
uv run python libs/naas-abi/naas_abi/apps/desktop/run.py --browser-only --no-open-browser

# auto-reload Python on save (foreground)
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
  scripts/      dev.sh, test.sh, coverage-kpi.sh, smoke_chat.sh
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
244 passed, 0 failed
TOTAL coverage 90%
```

The script writes coverage and junit artifacts under `desktop/`:

- `.coverage-report.json` for programmatic KPIs
- `.test-results.xml` for pass/fail counts

CI one-liner (after `test.sh`):

```bash
./libs/naas-abi/naas_abi/apps/desktop/scripts/coverage-kpi.sh
# desktop_coverage=90.0 pass=244 fail=0
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
