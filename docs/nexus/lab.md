# Lab — IDE environment

The **Lab** section in Nexus is a full-featured code editor built on Monaco (the same engine as VS Code), connected to the `~/aia` filesystem via a backend API.

## Access

Sidebar → **Lab**, or navigate to `/workspace/{id}/lab`.

## File explorer

The left sidebar under Lab shows the `~/aia` directory tree. Only code/config/doc files are shown; large data and binary folders are hidden.

**Hidden directories** (server-side):
`.git`, `.next`, `node_modules`, `__pycache__`, `.venv`, `venv`, `dist`, `build`, `aia-model`, `archive`, `obsidian`, `openai`, `iphone-jrv`, `qonto`, `assets`

**Shown extensions**:
`.py .ts .tsx .js .jsx .json .yaml .yml .md .txt .toml .cfg .ini .env .sh .html .css .scss .sql .graphql .proto .tf .hcl` and no-extension files (Makefile, Dockerfile).

### Context menu (right-click a file)

| Action | What it does |
|---|---|
| Copy Absolute Path | Copies `/Users/jrvmac/aia/src/file.py` |
| Copy Relative Path | Copies `src/file.py` |

## Monaco editor

- Syntax highlighting for all major languages (auto-detected from extension)
- Dark/light theme follows Nexus theme (`vs-dark` / `light`)
- Tab size: 2 spaces
- Word wrap enabled
- Bracket pair colorisation
- Minimap disabled for Markdown files

## Keyboard shortcuts

| Shortcut | Action |
|---|---|
| `Cmd+S` | Save current file to host filesystem |
| `Cmd+P` | Open file palette (search all files) |

## Creating a new file

Click **+ New file** in the tab bar. Enter a path relative to `~/aia`, e.g. `src/mymodule/app.py`. The file is created immediately on disk.

## Saving

Unsaved changes show a `•` dot on the tab and an **Italic** filename. Press `Cmd+S` or click the **Save** button in the toolbar. Files are written directly to `~/aia` via `PUT /api/lab/fs/write/{path}`.

## Backend API

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/lab/fs/?path={dir}` | List files in a directory |
| `GET` | `/api/lab/fs/read/{path}` | Read file content |
| `PUT` | `/api/lab/fs/write/{path}` | Write file content |
| `GET` | `/api/lab/fs/search?q={query}` | Fuzzy-search all files |
| `GET` | `/api/lab/fs/raw/{path}` | Serve raw file bytes (no auth — for images in iframes) |

### Source files

- **Backend**: `.abi/libs/naas-abi/naas_abi/apps/nexus/apps/api/app/api/endpoints/lab_fs.py`
- **Frontend store**: `.abi/libs/naas-abi/naas_abi/apps/nexus/apps/web/src/stores/files.ts`
- **Sidebar**: `.abi/libs/naas-abi/naas_abi/apps/nexus/apps/web/src/components/shell/sidebar/lab-section.tsx`
- **Page**: `.abi/libs/naas-abi/naas_abi/apps/nexus/apps/web/src/app/workspace/[workspaceId]/lab/page.tsx`
