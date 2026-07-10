# ABI Desktop — AGENTS.md

> Scope: `libs/naas-abi/naas_abi/apps/desktop/`. A standalone, compilable desktop app: a light Nexus with **Chat** and **Code** sections, backed by a local opencode harness (bring your own model), SQLite, and embedded Oxigraph.

## Purpose

Claude-Desktop-style local app. No Postgres, no Docker, no Nexus web stack.
One process: FastAPI backend + static web UI + native window (pywebview).
AI runs through a locally spawned `opencode serve` — the user brings their own
harness binary and provider keys.

## Hard constraint: no `naas_abi` / `naas_abi_core` imports

This package must stay importable without the ABI engine. All imports use the
top-level ``desktop`` package (``from desktop.core.store import ...``,
``from desktop.api.server import create_app``) and the only runtime deps are
`fastapi`, `uvicorn`, `httpx`, `pyoxigraph`, and optionally `pywebview`.
`run.py` roots the package as `desktop` so `naas_abi/__init__.py` never loads.
Breaking this rule breaks the small-executable build.

## Folder map

```
desktop/
  __init__.py
  main.py              # pywebview launcher + uvicorn (thin entry)
  run.py               # standalone launcher (PyInstaller entry; sys.path trick)
  conftest.py
  AGENTS.md
  build.md
  abi-desktop.spec

  config/              # paths, data dir, workspace bootstrap
    desktop_config.py

  core/                # domain, persistence, graph, integrations
    store.py           # SQLite chats/messages/settings
    graph.py           # embedded Oxigraph + BFO7 routing
    workspace_layout.py
    doctor.py
    templates.py
    integrations.py
    model_capabilities.py
    opencode_client.py # low-level opencode HTTP/SSE (harness adapter uses this)

  api/
    server.py          # FastAPI ``create_app()`` factory + static mount

  harness/             # hexagonal harness port/adapters/factory (sibling to api/)
    port.py            # HarnessPort ABC + event models
    models.py
    factory.py         # create_harness(settings)
    opencode/          # OpencodeHarnessAdapter (wraps core/opencode_client)
    pi/                # PiHarnessAdapter (pi --mode rpc)
    hermes/            # stub for future HermesAdapter

  gui/
    web/               # vanilla JS SPA (index.html, app.js, style.css, vendor/)

  ontology/            # bundled TTL for PyInstaller
  assets/              # app icon (.icns)
  scripts/             # smoke_chat.sh
  *_test.py            # colocated next to each module
```

## Files

| Path | Role |
|---|---|
| `run.py` | Standalone launcher (avoids importing `naas_abi`) |
| `main.py` | uvicorn + pywebview window; `--browser-only` / `ABI_DESKTOP_BROWSER` for browser dev |
| `api/server.py` | FastAPI app factory: chats/SSE, files, models, SPARQL, settings, static |
| `harness/` | Hexagonal harness layer: `HarnessPort`, opencode/pi adapters, `create_harness()` |
| `core/opencode_client.py` | Low-level opencode HTTP/SSE client (used by the opencode harness adapter) |
| `core/store.py` | SQLite (stdlib `sqlite3`): chats, messages, settings |
| `core/graph.py` | Embedded Oxigraph (`pyoxigraph.Store`, on-disk): activity triples, BFO7 system ontology, org/model routing, SPARQL |
| `config/desktop_config.py` | Data dir layout (`~/.abi-desktop`), workspace git-init, `resolve_system_ontology_paths()` |
| `core/workspace_layout.py` | Org/model path schema, scaffolding, AGENTS/MEMORY readers |
| `core/templates.py` | `ensure_templates()`: `templates/slides/` starter decks + optional Downloads copy |
| `ontology/` | Bundled TTL: `desktop-routing.ttl`, `BFO7BucketsProcessOntology.ttl` (PyInstaller-safe) |
| `gui/web/` | Frontend: vanilla JS SPA (`index.html`, `app.js`, `style.css`), no build step |
| `gui/web/vendor/` | Vendored offline assets: Monaco AMD build (`monaco/vs/`), xterm.js + fit addon (`xterm/`), marked (`marked/`), vis-network (`vis/`) — no CDN at runtime |
| `abi-desktop.spec` | PyInstaller spec (onedir + macOS `.app` bundle) |
| `build.md` | Build recipe and runtime requirements |

### Where to add X

| Change | Location |
|---|---|
| New API route | `api/server.py` (or split into `api/routes/` when a section grows large) |
| SQLite schema / settings | `core/store.py` |
| Triple store / routing / SPARQL | `core/graph.py` |
| Org/model scaffolding | `core/workspace_layout.py` |
| Workspace paths / env sourcing | `config/desktop_config.py` |
| New harness backend | `harness/<provider>/adapter.py` + register in `harness/factory.py` |
| Frontend UI | `gui/web/app.js`, `gui/web/style.css` |
| Vendored JS lib | `gui/web/vendor/` + update `build.md` / `abi-desktop.spec` `datas` |
| Unit test | colocated `<module>_test.py` beside the module |

## API surface (localhost only)

- `GET/PUT /api/settings` — workspace root, harness (`opencode` | `pi`), binaries, default model, agents, doctor dismissed, **active_org**, **active_model**, **recent_workspaces**
- `GET /api/workspaces` — active workspace + recent folders `{ active, recent: [{path, name, exists}] }`
- `POST /api/workspaces/open` — `{ path }` opens an existing writable folder, sets active workspace, updates recent list
- `GET /api/workspace/env` — `.env` / `.env.remote` presence and key names in workspace root
- `GET /api/workspace/status` — git branch, workspace name, harness health, agents, default model (status bar)
- `GET /api/workspace/orgs` — org folders under workspace root + active org/model
- `GET /api/workspace/orgs/{org}/models` — model contexts for an org
- `POST /api/workspace/orgs/{org}/models/{model}/scaffold` — create AGENTS.md, MEMORY.md, ontology.ttl, instances.ttl
- `GET /api/integrations` — Ollama probe + installed models (Settings → Servers)
- `GET /api/health` — app status, data dir, workspace root, opencode URL, graph triple count
- `GET /api/models` — providers/models from the active harness
- `GET|POST|DELETE /api/chats`, `GET /api/chats/{id}/messages`
- `POST /api/chats/{id}/messages` — SSE stream: `text` (cumulative), `tool`, `error`, `complete`, `end`
- `POST /api/chats/{id}/abort`
- `GET /api/files`, `GET|PUT /api/files/content`, `DELETE /api/files` — scoped to workspace root
- `POST /api/files/mkdir`, `POST /api/files/rename`, `POST /api/files/upload` (multipart), `POST /api/files/import-local` — explorer upload/import ops, same `_safe_path` scoping
- `WS /api/terminal/ws` — PTY-backed login `bash` (cwd = workspace root); text frames are raw input/output, `{"type":"resize","cols":N,"rows":N}` JSON control messages resize the PTY; the child process group is killed on disconnect
- `POST /api/sparql` — embedded Oxigraph query
- `GET /api/graph/overview` — vis.js graph payload: nodes, edges, SQLite table snapshots
- `GET /api/processes` — paginated process event log with seven BFO bucket columns (`limit`, `offset`, optional `process_type`)
- `GET /api/tables` — SQLite table catalog (`tables[]` with `name`, `row_count`)
- `GET /api/tables/{name}` — paginated rows (`limit`, `offset`); `processes` and `events` return the rich 7-bucket event view
- `POST /api/router/suggest` — intent-aware model suggestions from `instances.ttl` BFO7 realizabilities

## Workspace switcher (IDE folder semantics)

A workspace is a **folder on disk** (VS Code / Cursor semantics), not a Nexus tenant.

- **UI**: icon rail top (Nexus sidebar-top pattern): **logo button only** opens a glass portal dropdown to the right (square corners). Hover on the logo shows the full path; the menu lists recent workspaces with a checkmark on the active entry and **Open Folder…**. The status bar left shows the current workspace basename and git branch as read-only context (no switch action). Top bar and main body stay clean (panel toggle + section title only). Rail bottom is Settings only.
- **Switch / open**: `POST /api/workspaces/open` or `PUT /api/settings` with a new `workspace_root`. Triggers `ensure_workspace`, harness restart, terminal reconnect, file index refresh, org/model context reload, and graph rescaffold.
- **Recent list**: `recent_workspaces` setting (JSON array, max 10 paths). Updated on every open/switch.
- **First run**: `maybe_upgrade_workspace_setting()` auto-detects `~/abi` (git + `.env`) when still on the factory default.
- **Open Folder**:
  - **Browser dev** (`--browser-only`): modal with absolute path input; server validates the folder exists and is writable.
  - **pywebview app**: same modal plus **Browse…** calling `pywebview.api.pick_workspace_folder()` (native `FOLDER_DIALOG` via `main.py` `DesktopApi` bridge).
- **Nexus reference**: `apps/nexus/apps/web/src/components/shell/sidebar/index.tsx` (workspace logo menu, glass dropdown portal).

## Org/model workspace layout

Canonical context path under the workspace root::

    {workspace_root}/{org}/{model}/AGENTS.md
    {workspace_root}/{org}/{model}/MEMORY.md
    {workspace_root}/{org}/{model}/ontology.ttl
    {workspace_root}/{org}/{model}/instances.ttl

- **Settings**: `active_org` and `active_model` (SQLite), defaulting to `default` / `default`.
- **Scaffold**: `workspace_layout.scaffold_org_model()`; called from `ensure_workspace()`, settings save, and the scaffold API. `templates.ensure_templates()` seeds `templates/slides/` (starter deck, README, optional ISO slide from Downloads). `sync_ollama_models_in_instances()` merges Ollama tool-capable models into the active context's `instances.ttl` between `# BEGIN/END abi-desktop:ollama-models` markers (triggered on context reload and `/api/integrations`).
- **Chat**: `build_agent_prompt_prefix()` prepends AGENTS.md + MEMORY.md; `DesktopGraph.build_routing_prompt_hint()` prepends BFO7 routing context; stored user messages stay unmodified.
- **Graph**: `DesktopGraph.load_system_ontology()` loads BFO7 + routing vocab into `#system`; `load_org_model_context()` loads per org/model TTL into `#context/{org}/{model}`; `resolve_route(org, model, intent)` returns agent, model hint, harness, and BFO7 bucket from `instances.ttl`.
- **ADR**: `docs/adr/20260710_desktop-org-model-workspace.md`, `docs/adr/20260710_desktop-bfo7-routing-graph.md`, `docs/adr/20260710_desktop-abi-model-router.md`

### BFO7 routing graph (iteration 2)

System ontology paths resolve via `config/desktop_config.resolve_system_ontology_paths()`:

1. `ABI_DESKTOP_SYSTEM_ONTOLOGY_PATHS` env override (`os.pathsep`-separated)
2. bundled `ontology/desktop-routing.ttl` + `BFO7BucketsProcessOntology.ttl`
3. repo copies under `naas_abi/ontologies/...` and `naas_abi/apps/nexus/ontology/...` when developing from source

Scaffolded `instances.ttl` seeds concrete routing individuals:

- `chat` → `plan` agent, `usesHarness opencode`, BFO7 **role** bucket (`bfo:BFO_0000023` / WHY)
- `code` → `build` agent, `usesHarness opencode`, BFO7 **process** bucket (`bfo:BFO_0000015` / WHAT)
- `ModelContext` with `modelUri` for the org/model canonical IRI
- optional `harnessModel` on routes for per-context model hints

`DesktopGraph.resolve_route(org, model, intent="chat"|"code")` returns `agent`, `model_hint`, `harness`, `bucket_label`. Chat send uses graph routing for agent selection and applies `model_hint` when no explicit model is set. `/api/health` includes `graph.routing` for the Graph UI BFO7 context panel.

**Iteration 3** (current):

- Rule-based intent tagger (`tag_intent_from_text`) and `POST /api/router/suggest` ranked by BFO7 realizability
- Composer router chips (top 3 suggestions; manual apply via chip click)
- `instances.ttl` sync: Ollama tool-capable models merged into active org/model context
- Graph UI: active context panel (org/model, chat/code routes, language models) + auto-run SPARQL union query on section enter
- `/api/health` → `graph.routing` includes `language_models`

**Iteration 4** (current):

- Ollama → `instances.ttl` sync on context reload and `/api/integrations` (tool-capable models, `hostedAt` local, `modelRef`)
- E2E router test: suggest → apply model → chat send
- Auto-apply top router suggestion on send (`router_auto_apply` setting; default off)
- Graph UI: active context panel + auto-run SPARQL on section enter

**Iteration 5** (current):

- Knowledge Graph UI: vis-network overview (SQLite + Oxigraph + routing ontology), entity detail table, SPARQL and Tables tabs
- `GET /api/graph/overview` builds nodes/edges from settings, chats/messages, SectionRoutes, LanguageModels, BFO buckets, and sqlite↔triple sync links

**Iteration 6** (current):

- **Process event schema (Option B)**: SQLite star schema in `core/store.py` — `processes`, `process_aspects` (7 rows per occurrent), `aspect_entities` (dedup by bucket+value_key). Chosen over Option A (wide event table) because material/site/temporal dedup and unknown slots are first-class.
- Graph builder reads `process_aspects` via `sync_chat_process()`; each chat/route process emits 7 bucket spokes (`build_process_bucket_subgraph`) with shared nodes (`SharedBucketRegistry`) and grey dashed unknown placeholders.
- ABOX default view: fixed hub-and-spoke layout (`_layout_instance_graph`). Brain view now uses the same 7-bucket spokes (no collapse). TBOX = ontology classes; Full = anchors + instances.
- `GET /api/graph/overview?view=abox|brain|tbox|full` — Tables tab includes `processes` and `process_aspects`.

**Iteration 7** (current):

- `GET /api/processes` — paginated event log rows (timestamp, label, type, seven bucket columns with known/shared/unknown status, `graph_node_id` for graph focus)

**Iteration 8** (current):

- **Events rail section**: dedicated `#events` main view with full-height process events table (`GET /api/processes`); row click opens detail panel, double-click or **View in Graph** navigates to Graph Overview and focuses the process node
- Workspace logo switcher at rail top (Nexus sidebar-top pattern); rail bottom is Settings only
- Graph Overview tab: vis-network canvas only (process events table removed from split view above graph)
- Tables tab still shows raw SQLite dumps (`processes`, `process_aspects`) for debugging

**Iteration 9** (current):

- **Rail reorganization** (top → bottom): Chat, Code, Graph, **Table**, **Files**, Settings (bottom)
- **Table** section (`#table`): flat SQLite table list in panel nav; main area shows paginated grid per table
- **Files** section (`#files`): full-panel workspace filesystem browser (`GET /api/files`); preview pane; double-click opens file in Code
- **Code** section: Monaco + terminal only; file explorer moved to Files rail
- Graph **Tables** tab redirects to Table section (`processes` table)
- Hash routing: `#table`, `#table/{name}`; legacy `#events`, `#table/events`, `#table/sqlite` → `processes`

**Iteration 10 targets**:
- Per-tool `SectionRoute` instances (terminal, file edit, SPARQL) with disposition-based routing
- Bidirectional sync: settings UI writes back to `instances.ttl` when agents/models change
- Visual BFO7 bucket diagram in Graph UI (seven-bucket layout, not just route summary)
- Model registry validation: warn when `harnessModel` / `modelRef` not in `/api/models`
- Drop SQLite agent fallback once all contexts ship routing instances

## Harness layer (`harness/`)

### Why `harness/` is a sibling of `api/`, not inside it

ABI Desktop follows hexagonal architecture. The **API layer** (`api/server.py`) is a
primary adapter: it translates HTTP/SSE requests into domain operations and depends
inward on the **HarnessPort** interface. The **harness adapters** (`harness/opencode/`,
`harness/pi/`, …) are secondary adapters: they depend outward on external runtimes
(opencode HTTP/SSE, pi JSONL RPC, …) and implement that port.

Nesting `harness/` under `api/` would invert the dependency direction — the HTTP
transport would own the AI-runtime integration boundary. Keeping them as siblings
under `desktop/` makes the contract explicit: `api` → `HarnessPort` ← provider
adapters, with low-level clients (e.g. `core/opencode_client.py`) shared only where
an adapter needs them.

```
desktop/
  api/server.py          # primary adapter (HTTP) — depends on HarnessPort
  harness/
    port.py              # port interface + normalized event models
    factory.py           # create_harness(settings)
    opencode/adapter.py  # secondary adapter — wraps core/opencode_client
    pi/adapter.py        # secondary adapter — spawns pi --mode rpc
    hermes/              # stub (README only until implemented)
  core/opencode_client.py  # low-level opencode HTTP/SSE (not a harness port)
```

Chat, model listing, and SSE streaming go through :class:`~desktop.harness.port.HarnessPort`,
not :class:`~desktop.core.opencode_client.OpencodeClient` directly.

- **Factory**: ``create_harness(settings)`` reads ``harness`` (``"opencode"`` | ``"pi"``,
  default ``"opencode"``), ``workspace_root``, and the harness-specific binary key
  (``opencode_bin`` / ``pi_bin``). Unknown harness names raise a clear ``ValueError``.
- **Adapters**: ``OpencodeHarnessAdapter`` wraps ``OpencodeClient``; ``PiHarnessAdapter``
  drives ``pi --mode rpc``. Both translate into normalized :mod:`~desktop.harness.models`
  events whose ``to_dict()`` shapes match the legacy SSE wire format (``text``, ``tool``,
  ``error``, ``complete``).
- **Adding a provider**: implement ``HarnessPort`` in ``harness/<provider>/adapter.py``,
  add colocated ``adapter_test.py``, export from ``harness/<provider>/__init__.py``,
  register in ``harness/factory.py``. See ``harness/hermes/README.md`` for the stub layout.
- **Server wiring**: ``create_app()`` builds ``create_harness(store.get_settings())`` in
  production. Tests inject ``harness=...`` or the legacy ``opencode=...`` seam (wrapped in
  ``OpencodeHarnessAdapter``). ``app.state.harness`` is the live instance; settings changes
  call ``harness.restart()`` or recreate the adapter when ``harness`` changes.
- **Doctor**: still probes opencode reachability via ``OpencodeHarnessAdapter.client`` when
  the opencode harness is selected; pi skips those checks.

## opencode integration notes

- Spawned via `bash -lc` with :func:`~desktop.config.desktop_config.build_shell_env_source`
  (sources `~/.bashrc` plus workspace `.env.remote` / `.env` with `set -a`), so
  provider keys travel with the workspace. Env detection is centralized in
  :func:`~desktop.config.desktop_config.resolve_env_files` and exposed at
  ``GET /api/workspace/env``.
- The workspace is git-initialized at creation: opencode roots its project at
  the nearest `.git`; without it, file tools fail on a read-only `/`.
  ``ensure_workspace()`` also seeds ``opencode.json``, ``.env.example``, and
  ``desktop.md`` when missing.
- Chat section sends `agent: plan` (read-only), Code section `agent: build`
  (both configurable in settings).
- Models must support **tool calling** (opencode agents always use tools).
  Non-tool models (e.g. `phi`) are filtered from `opencode.json` sync,
  marked `supports_tools: false` in `/api/models`, blocked at send time,
  and excluded from default model selection. See `core/model_capabilities.py`.
- Stream teardown guards against the known `session.idle`-before-prompt-response
  race with a 15 s grace await; never wait on the prompt POST unboundedly.
- opencode >= 1.4 streams assistant text through `message.part.delta` events;
  the client accumulates deltas and still accepts legacy `message.part.updated`
  snapshots.
- When no model is selected, the server falls back to the first configured
  Ollama model before calling opencode (avoids empty OpenAI key errors).
- On first launch, if workspace is still the factory default (`~/.abi-desktop/workspace`)
  and a git project with `.env` is found (e.g. `~/abi`), workspace root is
  upgraded automatically.
- User prompts echo back on the event stream; text parts are filtered by
  assistant `messageID`s collected from `message.updated` events.

## Tests

Canonical command (pytest + coverage KPI):

```bash
# from repo root
./libs/naas-abi/naas_abi/apps/desktop/scripts/test.sh

# or
make test-desktop
```

Expected footer: `244 passed, 0 failed` and `TOTAL coverage 90%` (approximate; run the script for the current number). CI one-liner: `scripts/coverage-kpi.sh` → `desktop_coverage=90.0 pass=244 fail=0`.

See [README.md](README.md) for prerequisites, quick start, and folder map.

```bash
# single file / keyword (extra args pass through to pytest)
./libs/naas-abi/naas_abi/apps/desktop/scripts/test.sh core/store_test.py -v
./libs/naas-abi/naas_abi/apps/desktop/scripts/test.sh -k "traversal" -v
```

### Manual chat smoke (requires live opencode)

```bash
# ABI Desktop must be running (built app or `uv run python .../run.py`)
chmod +x libs/naas-abi/naas_abi/apps/desktop/scripts/smoke_chat.sh
ABI_DESKTOP_URL=http://127.0.0.1:54242 SMOKE_MODEL=ollama/gemma4:latest \
  libs/naas-abi/naas_abi/apps/desktop/scripts/smoke_chat.sh
```

The script hits `/api/health`, `/api/doctor`, creates a chat, and streams one
message. Use an Ollama model when the workspace has no `.env` provider keys.

Conventions and seams:

- **TDD is the rule**: new behavior lands test-first. Every module gets a
  colocated `<module>_test.py` (naas-abi-core style).
- **Imports**: tests import the app as the top-level `desktop` package
  (`from desktop.core.store import DesktopStore`), never as `naas_abi.apps.desktop`
  — `conftest.py` inserts the parent `apps/` dir into `sys.path`, mirroring
  `run.py`, so the heavy `naas_abi` engine is never loaded.
- **DI seams**: `create_app(store=..., graph=..., harness=...)` accepts injectable
  dependencies (defaults self-provision under `~/.abi-desktop`). The legacy
  `opencode=...` kwarg still works for tests: it wraps the stub client in
  `OpencodeHarnessAdapter`. Tests pass tmp_path-backed `DesktopStore` /
  `DesktopGraph` and a duck-typed stub opencode client, so nothing touches the
  real data dir.
- **Fake opencode server**: `OpencodeClient(base_url=..., transport=...)`
  attaches to an existing endpoint instead of spawning a process; with
  `transport=httpx.ASGITransport(app=fake_app)` all HTTP/SSE traffic goes to
  an in-process FastAPI fake (see `FakeOpencode` in `core/opencode_client_test.py`)
  that scripts `/event` SSE frames, prompt responses, and permission calls.
- **No real subprocesses**: `ensure_workspace` tests monkeypatch
  `subprocess.run`; never spawn `opencode` or `git` in unit tests.
- All state goes through `tmp_path`; a test must never read or write
  `~/.abi-desktop`.

## Development workflow

**Daily dev (recommended):** detached supervisor with Python hot reload and crash restart.
Run only one dev instance at a time (the embedded Oxigraph graph uses on-disk RocksDB).

```bash
# from repo root — idempotent; safe for parallel agents; never kills a healthy server
make dev-desktop

# check health + PIDs without restarting
libs/naas-abi/naas_abi/apps/desktop/scripts/dev.sh status

# stop supervisor + server (only when you intend to shut down)
libs/naas-abi/naas_abi/apps/desktop/scripts/dev.sh stop
```

- **URL:** `http://127.0.0.1:54242` by default. Set `ABI_DESKTOP_PORT=8765` to override.
- **Logs:** `~/.abi-desktop/server.log`
- **Meta:** `~/.abi-desktop/server.json` (URL, port, worker PID)
- **Hot reload:** Python under `desktop/` restarts on save. Frontend is vanilla JS/CSS under
  `gui/web/` — refresh the browser after edits; no bundler.
- **Instance lock:** skipped when `--reload` is active. `dev.sh start` is idempotent: if
  `/api/health` returns 200, it prints the URL and exits 0 without stopping anything.
  Only `dev.sh stop` tears down the supervisor. Do not run two dev servers against
  different data dirs on the same port.

Foreground browser dev (no supervisor):

```bash
uv run python libs/naas-abi/naas_abi/apps/desktop/run.py --browser-only --reload
ABI_DESKTOP_RELOAD=1 uv run python libs/naas-abi/naas_abi/apps/desktop/run.py --browser-only
```

Manual flags:

```bash
# print URL only (no auto-open)
uv run python libs/naas-abi/naas_abi/apps/desktop/run.py --browser-only --no-open-browser
```

- If 54242 is busy, the server tries 54243 with a warning; set `ABI_DESKTOP_PORT` explicitly
  when you need a fixed port. On conflict the error is:
  `Port 54242 in use (PID …) — kill PID or set ABI_DESKTOP_PORT`.
- **Native window / ship:** omit `--browser-only` to use pywebview when installed.
  Rebuild the `.app` only when explicitly requested — see `build.md`.
- **Workspace:** defaults to `~/.abi-desktop/workspace`; auto-upgrades to a nearby
  git repo with `.env` (e.g. `~/abi`) on first launch. Override in Settings or via
  `ABI_DESKTOP_HOME` for an isolated data dir.
- **opencode:** must be on `PATH` (or set binary path in Settings). Provider keys
  via workspace `.env` / `.env.remote` or `opencode auth login`.
- **Stale `.app`:** a running `/Applications/ABI Desktop.app` may hold port 54242 if
  it was started from source with the same default. Quit the `.app` or set
  `ABI_DESKTOP_PORT` for dev.

```bash
# isolated data dir for testing
ABI_DESKTOP_HOME=/tmp/abi-desktop-test uv run python libs/naas-abi/naas_abi/apps/desktop/run.py --browser-only
```

## Run (production / native window)

```bash
# from source — native pywebview window when installed, else browser fallback
uv run python libs/naas-abi/naas_abi/apps/desktop/run.py

# build executable (on request only)
see build.md
```

## Code section IDE

The Code section is Monaco editor + PTY terminal (file explorer lives in the **Files** rail). Nexus Code IDE parity for editing: tab bar (dirty dots, close buttons, Cmd/Ctrl+S save), collapsible terminal panel (xterm.js over `WS /api/terminal/ws`, draggable divider, starts collapsed), and a Code/Split/Preview toggle for `.html`/`.md`/`.mdx` files (sandboxed iframe for HTML, `marked` for Markdown). Open files from the **Files** section (double-click or **Open in Code**).

- `vendor/monaco/vs/` — monaco-editor 0.52.2 `min/vs` AMD build (0.53+
  dropped AMD), pruned of non-English nls files; loaded via `loader.js` +
  `require.config({ paths: { vs: ... } })`, custom `abi-dark` theme.
- `vendor/xterm/` — @xterm/xterm 6.0.0 (`xterm.js`, `xterm.css`) +
  @xterm/addon-fit 0.11.0.
- `vendor/marked/` — marked 18.0.6 UMD.
- `vendor/vis/` — vis-network 10.0.2 standalone UMD (`vis-network.min.js`, `vis-network.min.css`).

UMD `<script>` tags must load **before** Monaco's AMD `loader.js`, otherwise
they register as anonymous AMD modules instead of setting window globals.
One Monaco instance swaps `monaco.editor.createModel` models per tab; models
are keyed by `monaco.Uri.file(path)` so language detection follows the
extension. The terminal endpoint needs no extra deps: stdlib `pty`/`termios`/
`fcntl` plus the websockets support already shipped with `uvicorn[standard]`.

### Finder drag-and-drop (Files explorer)

The **Files** section explorer accepts files dragged from macOS Finder:

- **Drop target**: `#files-listing-wrap`. Drag-over shows a square-cornered Nexus
  accent outline (`border-radius: 0`). Hovering a folder row targets that folder.
- **Default folder**: last-clicked folder (`ide.selectedDir`), else workspace root.
- **Browser / fallback**: HTML5 `dataTransfer.files` → `POST /api/files/upload`
  (multipart). Works when the webview exposes file bytes to JS.
- **pywebview (macOS Cocoa)**: standard JS cannot read Finder full paths; `main.py`
  binds a `DOMEventHandler` on `#files-listing-wrap` `drop` (document fallback) that reads
  `event['dataTransfer']['files'][n]['pywebviewFullPath']` and calls
  `POST /api/files/import-local`. Requires pywebview 5+ DOM API. JS uses a drag-depth
  counter (`fileTreeDragDepth`) so drops are not lost when `dragleave` fires early.
- **After import**: toast, explorer refresh, auto-open `.html` in Split preview.
- **Folders from Finder**: not supported via `pywebviewFullPath` (files only).
  `.DS_Store` is skipped. Name conflicts auto-rename with `_1` suffix.

### Knowledge Graph UI

The Graph section combines a **vis-network** canvas with search, group filters, and a right-hand detail panel (inspired by `bob/docs/ontology/bob_ontology.html` and Nexus graph explorer).

- **Layout (Overview tab)**: toolbar with search + group filter chips; center vis-network canvas; right inspector panel (~320px, square corners, slide-in on selection).
- **Search**: filters nodes by label/id/group as you type; matching nodes stay highlighted, others dim; Enter cycles matches and focuses the node; Escape clears search.
- **Group filters**: toggle chips per node group (context, route, language_model, …); hidden groups are removed from the canvas.
- **Right panel**: opens on node click; shows properties from `node.detail`, `can_realize` tags for language models, TTL annotations for BFO buckets, and incoming/outgoing relations (clickable to jump).
- **Data**: `GET /api/graph/overview` returns `{ nodes, edges, tables, meta }`. Built by `DesktopGraph.build_graph_overview()` from SQLite (`store`) plus Oxigraph SPARQL over the active org/model context graph and default-graph activity triples. Language model nodes include `can_realize` process labels; BFO bucket nodes include `rdfs_label` / `rdfs_comment` / `skos_definition` when present in the system ontology.
- **Node groups** (color-coded): `context` (org/model), `route` (chat/code SectionRoutes), `language_model`, `bfo_bucket`, `sqlite_chat` / `sqlite_message`, `graph_chat` / `graph_message`, `settings`.
- **Edges**: ontology links (`hasRoute`, `mapsToBfoProcess`, `LanguageModel`, `message`, `inChat`), plus cross-store `synced` edges linking SQLite chat/message IDs to matching Oxigraph individuals.
- **View in browser dev**: `uv run python libs/naas-abi/naas_abi/apps/desktop/run.py --browser-only` → Knowledge Graph rail icon → Overview tab → search or click a node.
- **Tables tab**: shortcut to Table rail → `processes` table (no inline table dump).
- **References**: `bob/docs/ontology/bob_ontology.html` (inspector + neighbourhood highlight), `apps/nexus/apps/web/src/components/graph/vis-network.tsx` (layout/physics), `knowledge-graph-section.tsx` (sidebar structure).

### Table section (flat SQLite table list)

Dedicated rail section (`#table`) for browsing all SQLite app tables.

- **Panel nav**: flat list of table names + row counts from `GET /api/tables` (`settings`, `chats`, `messages`, `processes`, `process_aspects`, `aspect_entities`)
- **Main area**: paginated data grid via `GET /api/tables/{name}`; generic columns for most tables
- **`processes` table**: shows the rich 7-bucket process events grid (same as iteration 7); row click opens detail panel; double-click or **View in Graph** focuses the process node. API alias: `GET /api/tables/events` returns the same payload
- **Hash**: `#table`, `#table/{name}`; legacy `#events`, `#table/events`, `#table/sqlite` map to `processes`

### Files section (workspace filesystem)

Dedicated rail section (`#files`) for Nexus-style workspace file browsing.

- **Panel (280px)**: workspace root link, recent folders, refresh + hidden toggle
- **Main area**: toolbar (New File, New Folder, Upload, Refresh), search, list/grid toggle, breadcrumbs, file listing with size/modified metadata
- **Preview pane**: right split; single-click previews html/md/text; double-click or **Open in Code** opens Monaco tab
- **Data**: `GET /api/files` (entries include `size`, `mtime`, `is_dir`); drag-drop upload/import unchanged
- **Hash**: `#files`.

## Adding features

- Keep the frontend dependency-free at runtime (vanilla JS + the vendored
  libs above); assets ship as package data and PyInstaller `datas`.
- The UI must stay visually identical to Nexus. `gui/web/style.css` mirrors the
  design tokens in `apps/nexus/apps/web/src/app/globals.css` (dark brand
  default) and the shell layout (icon rail w-14, section panel w-64, h-14
  glass top bar, rounded-2xl composer card, accent chat bubbles with in-bubble
  sender names). Icons are inline lucide SVG paths in `gui/web/app.js`. When Nexus
  branding changes, update the tokens here in lockstep.
- **Settings** is a full main view (not a modal), cloned from Nexus
  `settings-nav.tsx`, `servers-panel.tsx`, and `models-panel.tsx`: panel
  sub-nav (General / Servers / Models), server cards, status pills, models
  table with search/filter. Integrations rail icon removed; Ollama lives under
  Settings → Servers.
- Any new Python dependency must be added to both `build.md` and the
  PyInstaller build env — and justified against bundle size.
- New API routes go in `api/server.py`; persistence in `core/store.py` (SQLite) and/or
  `core/graph.py` (triples). Follow the existing pattern.
