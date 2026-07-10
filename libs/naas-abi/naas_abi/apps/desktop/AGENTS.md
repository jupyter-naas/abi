# ABI Desktop — AGENTS.md

> Scope: `libs/naas-abi/naas_abi/apps/desktop/`. A standalone, compilable desktop app: a light Nexus with **Chat** and **Code** sections, backed by a local opencode harness (bring your own model), SQLite, and embedded Oxigraph.

## Purpose

Claude-Desktop-style local app. No Postgres, no Docker, no Nexus web stack.
One process: FastAPI backend + static web UI + native window (pywebview).
AI runs through a locally spawned `opencode serve` — the user brings their own
harness binary and provider keys.

## Hard constraint: no `naas_abi` / `naas_abi_core` imports

This package must stay importable without the ABI engine. All imports are
package-relative (`from .store import ...`) and the only runtime deps are
`fastapi`, `uvicorn`, `httpx`, `pyoxigraph`, and optionally `pywebview`.
`run.py` roots the package as `desktop` so `naas_abi/__init__.py` never loads.
Breaking this rule breaks the small-executable build.

## Files

| File | Role |
|---|---|
| `run.py` | Standalone launcher (avoids importing `naas_abi`) |
| `main.py` | uvicorn + pywebview window; `--browser-only` / `ABI_DESKTOP_BROWSER` for browser dev |
| `server.py` | FastAPI app factory: chats/SSE, files, models, SPARQL, settings, static |
| `harness/` | Hexagonal harness layer: `HarnessPort`, opencode/pi adapters, `create_harness()` |
| `opencode_client.py` | Low-level opencode HTTP/SSE client (used by the opencode harness adapter) |
| `store.py` | SQLite (stdlib `sqlite3`): chats, messages, settings |
| `graph.py` | Embedded Oxigraph (`pyoxigraph.Store`, on-disk): activity triples, BFO7 system ontology, org/model routing, SPARQL |
| `desktop_config.py` | Data dir layout (`~/.abi-desktop`), workspace git-init, `resolve_system_ontology_paths()` |
| `workspace_layout.py` | Org/model path schema, scaffolding, AGENTS/MEMORY readers |
| `templates.py` | `ensure_templates()`: `templates/slides/` starter decks + optional Downloads copy |
| `ontologies/` | Bundled TTL: `desktop-routing.ttl`, `BFO7BucketsProcessOntology.ttl` (PyInstaller-safe) |
| `web/` | Frontend: vanilla JS SPA (`index.html`, `app.js`, `style.css`), no build step |
| `web/vendor/` | Vendored offline assets: Monaco AMD build (`monaco/vs/`), xterm.js + fit addon (`xterm/`), marked (`marked/`), vis-network (`vis/`) — no CDN at runtime |
| `abi-desktop.spec` | PyInstaller spec (onedir + macOS `.app` bundle) |
| `build.md` | Build recipe and runtime requirements |

## API surface (localhost only)

- `GET/PUT /api/settings` — workspace root, harness (`opencode` | `pi`), binaries, default model, agents, doctor dismissed, **active_org**, **active_model**
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
- `POST /api/router/suggest` — intent-aware model suggestions from `instances.ttl` BFO7 realizabilities

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

System ontology paths resolve via `desktop_config.resolve_system_ontology_paths()`:

1. `ABI_DESKTOP_SYSTEM_ONTOLOGY_PATHS` env override (`os.pathsep`-separated)
2. bundled `ontologies/desktop-routing.ttl` + `BFO7BucketsProcessOntology.ttl`
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

**Iteration 6 targets**:
- Per-tool `SectionRoute` instances (terminal, file edit, SPARQL) with disposition-based routing
- Bidirectional sync: settings UI writes back to `instances.ttl` when agents/models change
- Visual BFO7 bucket diagram in Graph UI (seven-bucket layout, not just route summary)
- Model registry validation: warn when `harnessModel` / `modelRef` not in `/api/models`
- Drop SQLite agent fallback once all contexts ship routing instances

## Harness layer (`harness/`)

Chat, model listing, and SSE streaming go through :class:`~desktop.harness.port.HarnessPort`,
not :class:`~desktop.opencode_client.OpencodeClient` directly.

- **Factory**: ``create_harness(settings)`` reads ``harness`` (``"opencode"`` | ``"pi"``,
  default ``"opencode"``), ``workspace_root``, and the harness-specific binary key
  (``opencode_bin`` / ``pi_bin``).
- **Adapters**: ``OpencodeHarnessAdapter`` wraps ``OpencodeClient``; ``PiHarnessAdapter``
  drives ``pi --mode rpc``. Both translate into normalized :mod:`~desktop.harness.models`
  events whose ``to_dict()`` shapes match the legacy SSE wire format (``text``, ``tool``,
  ``error``, ``complete``).
- **Server wiring**: ``create_app()`` builds ``create_harness(store.get_settings())`` in
  production. Tests inject ``harness=...`` or the legacy ``opencode=...`` seam (wrapped in
  ``OpencodeHarnessAdapter``). ``app.state.harness`` is the live instance; settings changes
  call ``harness.restart()`` or recreate the adapter when ``harness`` changes.
- **Doctor**: still probes opencode reachability via ``OpencodeHarnessAdapter.client`` when
  the opencode harness is selected; pi skips those checks.

## opencode integration notes

- Spawned via `bash -lc` with :func:`~desktop.desktop_config.build_shell_env_source`
  (sources `~/.bashrc` plus workspace `.env.remote` / `.env` with `set -a`), so
  provider keys travel with the workspace. Env detection is centralized in
  :func:`~desktop.desktop_config.resolve_env_files` and exposed at
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
  and excluded from default model selection. See `model_capabilities.py`.
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

```bash
# full desktop suite (fast: no opencode binary, no network, no GUI)
uv run pytest libs/naas-abi/naas_abi/apps/desktop -v

# single file / test
uv run pytest libs/naas-abi/naas_abi/apps/desktop/store_test.py -v
uv run pytest libs/naas-abi/naas_abi/apps/desktop -k "traversal" -v
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
  (`from desktop.store import DesktopStore`), never as `naas_abi.apps.desktop`
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
  an in-process FastAPI fake (see `FakeOpencode` in `opencode_client_test.py`)
  that scripts `/event` SSE frames, prompt responses, and permission calls.
- **No real subprocesses**: `ensure_workspace` tests monkeypatch
  `subprocess.run`; never spawn `opencode` or `git` in unit tests.
- All state goes through `tmp_path`; a test must never read or write
  `~/.abi-desktop`.

## Development workflow

**Daily dev (recommended):** run from source in the browser. No PyInstaller rebuild,
no `/Applications` install. Stable URL on port **54242** (override with `ABI_DESKTOP_PORT`).

```bash
# from repo root — opens your default browser tab
uv run python libs/naas-abi/naas_abi/apps/desktop/run.py --browser-only

# same, via env (useful in shell profiles or IDE run configs)
ABI_DESKTOP_BROWSER=1 uv run python libs/naas-abi/naas_abi/apps/desktop/run.py

# print URL only (no auto-open)
uv run python libs/naas-abi/naas_abi/apps/desktop/run.py --browser-only --no-open-browser

# auto-reload Python on save (browser-only; JS/CSS still need a manual refresh)
uv run python libs/naas-abi/naas_abi/apps/desktop/run.py --browser-only --reload
ABI_DESKTOP_RELOAD=1 uv run python libs/naas-abi/naas_abi/apps/desktop/run.py --browser-only
```

- **URL:** `http://127.0.0.1:54242` by default. Set `ABI_DESKTOP_PORT=8765` to override.
  If 54242 is busy, the server tries 54243 with a warning; set `ABI_DESKTOP_PORT` explicitly
  when you need a fixed port. On conflict the error is:
  `Port 54242 in use (PID …) — kill PID or set ABI_DESKTOP_PORT`.
- **Hot reload:** `--reload` or `ABI_DESKTOP_RELOAD=1` (with `--browser-only`) restarts
  uvicorn when Python files change. Frontend is vanilla JS/CSS under `web/` — refresh the
  browser after edits; no bundler.
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

The Code section is a full IDE shell (Nexus Code IDE parity): Monaco editor
with a tab bar (dirty dots, close buttons, Cmd/Ctrl+S save), file explorer
with inline new-file/new-folder/rename/delete, a collapsible PTY terminal
panel (xterm.js over `WS /api/terminal/ws`, draggable divider, starts
collapsed), and a Code/Split/Preview toggle for `.html`/`.md`/`.mdx` files
(sandboxed iframe for HTML, `marked` for Markdown). All JS libraries are
vendored under `web/vendor/` so the app works offline and inside the
PyInstaller bundle:

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

### Finder drag-and-drop (file explorer)

The Code section explorer accepts files dragged from macOS Finder:

- **Drop target**: `#file-tree` panel. Drag-over shows a square-cornered Nexus
  accent outline (`border-radius: 0`). Hovering a folder row targets that folder.
- **Default folder**: last-clicked folder (`ide.selectedDir`), else workspace root.
- **Browser / fallback**: HTML5 `dataTransfer.files` → `POST /api/files/upload`
  (multipart). Works when the webview exposes file bytes to JS.
- **pywebview (macOS Cocoa)**: standard JS cannot read Finder full paths; `main.py`
  binds a `DOMEventHandler` on `#file-tree` `drop` (document fallback) that reads
  `event['dataTransfer']['files'][n]['pywebviewFullPath']` and calls
  `POST /api/files/import-local`. Requires pywebview 5+ DOM API. JS uses a drag-depth
  counter (`fileTreeDragDepth`) so drops are not lost when `dragleave` fires early.
- **After import**: toast, explorer refresh, auto-open `.html` in Split preview.
- **Folders from Finder**: not supported via `pywebviewFullPath` (files only).
  `.DS_Store` is skipped. Name conflicts auto-rename with `_1` suffix.

### Knowledge Graph UI

The Graph section combines a **vis-network** canvas with search, group filters, and a right-hand detail panel (inspired by `bob/docs/ontology/bob_ontology.html` and Nexus graph explorer).

- **Layout (Overview tab)**: toolbar with search + group filter chips; optional left node list when search matches; center vis-network canvas; right inspector panel (~320px, square corners, slide-in on selection).
- **Search**: filters nodes by label/id/group as you type; matching nodes stay highlighted, others dim; Enter cycles matches and focuses the node; Escape clears search.
- **Group filters**: toggle chips per node group (context, route, language_model, …); hidden groups are removed from the canvas.
- **Right panel**: opens on node click; shows properties from `node.detail`, `can_realize` tags for language models, TTL annotations for BFO buckets, and incoming/outgoing relations (clickable to jump).
- **Data**: `GET /api/graph/overview` returns `{ nodes, edges, tables, meta }`. Built by `DesktopGraph.build_graph_overview()` from SQLite (`store`) plus Oxigraph SPARQL over the active org/model context graph and default-graph activity triples. Language model nodes include `can_realize` process labels; BFO bucket nodes include `rdfs_label` / `rdfs_comment` / `skos_definition` when present in the system ontology.
- **Node groups** (color-coded): `context` (org/model), `route` (chat/code SectionRoutes), `language_model`, `bfo_bucket`, `sqlite_chat` / `sqlite_message`, `graph_chat` / `graph_message`, `settings`.
- **Edges**: ontology links (`hasRoute`, `mapsToBfoProcess`, `LanguageModel`, `message`, `inChat`), plus cross-store `synced` edges linking SQLite chat/message IDs to matching Oxigraph individuals.
- **View in browser dev**: `uv run python libs/naas-abi/naas_abi/apps/desktop/run.py --browser-only` → Knowledge Graph rail icon → Overview tab → search or click a node.
- **References**: `bob/docs/ontology/bob_ontology.html` (inspector + neighbourhood highlight), `apps/nexus/apps/web/src/components/graph/vis-network.tsx` (layout/physics), `knowledge-graph-section.tsx` (sidebar structure).

## Adding features

- Keep the frontend dependency-free at runtime (vanilla JS + the vendored
  libs above); assets ship as package data and PyInstaller `datas`.
- The UI must stay visually identical to Nexus. `web/style.css` mirrors the
  design tokens in `apps/nexus/apps/web/src/app/globals.css` (dark brand
  default) and the shell layout (icon rail w-14, section panel w-64, h-14
  glass top bar, rounded-2xl composer card, accent chat bubbles with in-bubble
  sender names). Icons are inline lucide SVG paths in `web/app.js`. When Nexus
  branding changes, update the tokens here in lockstep.
- **Settings** is a full main view (not a modal), cloned from Nexus
  `settings-nav.tsx`, `servers-panel.tsx`, and `models-panel.tsx`: panel
  sub-nav (General / Servers / Models), server cards, status pills, models
  table with search/filter. Integrations rail icon removed; Ollama lives under
  Settings → Servers.
- Any new Python dependency must be added to both `build.md` and the
  PyInstaller build env — and justified against bundle size.
- New API routes go in `server.py`; persistence in `store.py` (SQLite) and/or
  `graph.py` (triples). Follow the existing pattern.
