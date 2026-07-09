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
| `main.py` | uvicorn thread + pywebview window (browser fallback) |
| `server.py` | FastAPI app factory: chats/SSE, files, models, SPARQL, settings, static |
| `harness/` | Hexagonal harness layer: `HarnessPort`, opencode/pi adapters, `create_harness()` |
| `opencode_client.py` | Low-level opencode HTTP/SSE client (used by the opencode harness adapter) |
| `store.py` | SQLite (stdlib `sqlite3`): chats, messages, settings |
| `graph.py` | Embedded Oxigraph (`pyoxigraph.Store`, on-disk): activity triples + SPARQL |
| `desktop_config.py` | Data dir layout (`~/.abi-desktop`), workspace git-init |
| `web/` | Frontend: vanilla JS SPA (`index.html`, `app.js`, `style.css`), no build step |
| `web/vendor/` | Vendored offline assets: Monaco AMD build (`monaco/vs/`), xterm.js + fit addon (`xterm/`), marked (`marked/`) — no CDN at runtime |
| `abi-desktop.spec` | PyInstaller spec (onedir + macOS `.app` bundle) |
| `build.md` | Build recipe and runtime requirements |

## API surface (localhost only)

- `GET/PUT /api/settings` — workspace root, harness (`opencode` | `pi`), binaries, default model, agents, doctor dismissed
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
- Chat section sends `agent: plan` (read-only), Code section `agent: build`
  (both configurable in settings).
- Stream teardown guards against the known `session.idle`-before-prompt-response
  race with a 15 s grace await; never wait on the prompt POST unboundedly.
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

## Run

```bash
# from source
uv run python libs/naas-abi/naas_abi/apps/desktop/run.py

# isolated data dir for testing
ABI_DESKTOP_HOME=/tmp/abi-desktop-test uv run python libs/naas-abi/naas_abi/apps/desktop/run.py

# build executable
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
  registers a `DOMEventHandler` on `drop` that reads
  `event['dataTransfer']['files'][n]['pywebviewFullPath']` and calls
  `POST /api/files/import-local`. Requires pywebview 5+ DOM API.
- **Folders from Finder**: not supported via `pywebviewFullPath` (files only).
  `.DS_Store` is skipped. Name conflicts auto-rename with `_1` suffix.

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
