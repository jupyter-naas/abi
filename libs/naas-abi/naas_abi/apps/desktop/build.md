# Building the ABI Desktop executable

The app deliberately avoids importing `naas_abi` / `naas_abi_core`, so the
bundle only needs six runtime dependencies. Build it from a clean throwaway
virtualenv to keep the executable small.

Frontend libraries (Monaco, xterm.js, marked) are vendored under
`web/vendor/` (~12 MB) and ship automatically through the spec's `datas`
entry — no CDN access needed at runtime. Expect an onedir bundle of
~66 MB total.

## macOS / Linux

```bash
cd libs/naas-abi/naas_abi/apps/desktop

# 1. Isolated build env (not the repo venv — keeps the bundle minimal)
uv venv /tmp/abi-desktop-build
source /tmp/abi-desktop-build/bin/activate
uv pip install fastapi "uvicorn[standard]" httpx pyoxigraph pywebview pyinstaller

# 2. Build
pyinstaller abi-desktop.spec --noconfirm

# 3. Result
#    dist/abi-desktop/abi-desktop     — CLI-launchable binary
#    dist/ABI Desktop.app             — macOS app bundle
open "dist/ABI Desktop.app"
```

## Run from source (no build)

```bash
uv run python libs/naas-abi/naas_abi/apps/desktop/run.py
# opens a native window if pywebview is installed, else the browser
```

## Runtime requirements on the target machine

- `opencode` on the `PATH` (or configure the binary path in Settings) —
  the harness is bring-your-own by design and is not bundled.
- Provider API keys: either `opencode auth login`, or a `.env` /
  `.env.remote` file in the workspace root (sourced automatically when
  the app spawns `opencode serve`).

## Data location

Everything lives under `~/.abi-desktop` (override with `ABI_DESKTOP_HOME`):

| Path | Contents |
|---|---|
| `desktop.db` | SQLite: chats, messages, settings |
| `graph/` | Embedded Oxigraph store (RocksDB) |
| `workspace/` | Default code workspace (git-initialized) |
