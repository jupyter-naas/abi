# API reference — Lab endpoints

All endpoints are served by the FastAPI backend (`abi-abi-1` container, port 9879).

## Filesystem — `/api/lab/fs/`

Authenticated (JWT bearer). Serves `~/aia` (mounted at `/app/aia-host` in Docker).

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/lab/fs/?path={dir}` | List files/folders in a directory |
| `GET` | `/api/lab/fs/read/{path}` | Read a text file |
| `PUT` | `/api/lab/fs/write/{path}` | Write/create a text file. Body: `{"path":"…","content":"…"}` |
| `GET` | `/api/lab/fs/search?q={query}&limit=40` | Fuzzy-search all files, returns `[LabFileInfo]` |

### Unauthenticated

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/lab/fs/raw/{path}` | Serve raw bytes (image, font, etc.) — used by `<img src>` in iframe previews |

### `LabFileInfo` schema

```json
{
  "name": "slides.html",
  "path": "src/fmz-engagement/apps/web-slides/src/slides.html",
  "type": "file",
  "size": 48231,
  "modified": "2026-03-28T14:22:00",
  "content_type": "text/html"
}
```

---

## Git — `/api/lab/git/`

Authenticated. Runs git commands on the `~/aia` repository.

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/lab/git/branches` | List local branches with `ahead`/`behind` vs origin |
| `GET` | `/api/lab/git/status` | Current branch + staged/changed/untracked counts |
| `POST` | `/api/lab/git/checkout` | Checkout or create a branch. Body: `{"branch":"name","create":false}` |

---

## Terminal — `/api/lab/terminal/`

Unauthenticated WebSocket (local dev only).

| Method | Path | Description |
|---|---|---|
| `WS` | `/api/lab/terminal/ws` | PTY-backed bash shell. Raw bytes I/O + JSON resize events |

---

## Source files

| File | Covers |
|---|---|
| `.abi/.../api/endpoints/lab_fs.py` | Filesystem endpoints |
| `.abi/.../api/endpoints/lab_git.py` | Git endpoints |
| `.abi/.../api/endpoints/lab_terminal.py` | Terminal WebSocket |
| `.abi/.../api/api/router.py` | Router registration |
