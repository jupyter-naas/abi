# Terminal

An integrated bash terminal in the Lab section, backed by a real PTY (pseudo-terminal) — the same mechanism VS Code uses.

## Open

Click **Terminal** in the tab bar of the Lab page (top-right of the tab row).

## Resize

Drag the thin handle at the top edge of the terminal panel up or down. Min height 100px, max 600px.

## New session

Click **↺ New** in the terminal title bar to kill the current shell and start a fresh one.

## Shell environment

The terminal spawns `/bin/bash --login` inside the Docker container (`abi-abi-1`) with:

- **Working directory**: `/app/aia-host` (bind-mounted `~/aia`)
- **`TERM`**: `xterm-256color` (full colour support)
- **`COLORTERM`**: `truecolor`

This means you can run Python scripts, `make` targets, `git` commands, `curl`, etc. directly against your `~/aia` files.

## Limitations

- Runs inside the Docker container, not on the host macOS shell
- Interactive full-screen apps (vim, htop) work via the full PTY
- Programs not installed in the container image are unavailable (use `pip install` or add to requirements)

## WebSocket protocol

The terminal uses a raw WebSocket at `/api/lab/terminal/ws`:

- **Browser → server**: raw bytes (keyboard input) OR JSON resize event `{"type":"resize","cols":N,"rows":N}`
- **Server → browser**: raw bytes (PTY output, consumed by xterm.js)

## Source files

| File | Purpose |
|---|---|
| `.abi/.../api/endpoints/lab_terminal.py` | PTY WebSocket backend |
| `.abi/.../web/src/components/shell/terminal-pane.tsx` | xterm.js React component |
| `.abi/.../web/src/app/workspace/[workspaceId]/lab/page.tsx` | Toggle button + draggable panel |
