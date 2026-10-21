# publish_assets

## What it is
Utilities to locate a Next.js static export (`web/out/`) and upload its files to object storage under an application prefix. Includes an optional helper to build the export via `pnpm`/`npm` when missing.

## Public API
- `export_candidates() -> list[pathlib.Path]`
  - Returns possible export directories (most specific first):
    - `X_APP_WEB_EXPORT_DIR` (if set)
    - `<this module>/out`
    - `/opt/x-app-web/out`
- `resolve_export_dir() -> Path | None`
  - Returns the first candidate directory that looks like a Next export (contains `index.html`), else `None`.
- `web_export_dir() -> Path`
  - Returns `resolve_export_dir()` or falls back to `<this module>/out`.
- `web_export_exists() -> bool`
  - True if a usable export directory is found.
- `ensure_web_built() -> Path`
  - Returns the resolved export directory or raises `FileNotFoundError` with a rebuild hint.
- `upload_web_export(object_storage: ObjectStorageService, app_prefix: str, *, required: bool = True) -> dict`
  - Uploads all files from the resolved export to object storage under `app_prefix/`.
  - Skips:
    - `.DS_Store`
    - `404.html` and anything under `404/`
  - When `required=False` and no export exists: logs a warning and returns a skip dict.
  - Returns a summary dict (or skip dict).
- `maybe_build_web(*, force: bool = False) -> Path | None`
  - Attempts to install dependencies and build the web export in `WEB_DIR` if missing (or if `force=True`).
  - Returns the export path, or `None` if `package.json` is not present.

## Configuration/Dependencies
- Environment:
  - `X_APP_WEB_EXPORT_DIR`: overrides where the Next export is searched for.
- Filesystem conventions:
  - `EXPORT_DIR`: `out/` adjacent to this file.
  - `BAKED_EXPORT_DIR`: `/opt/x-app-web/out` (image-baked export).
- External services:
  - `ObjectStorageService` (must provide `put_object(prefix: str, name: str, content: bytes)`).
- Build tooling (for `maybe_build_web`):
  - `pnpm` and/or `npm` available on `PATH`.
  - `package.json` present in `WEB_DIR`.

## Usage
```python
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService
from naas_abi_marketplace.applications.x.apps.x.web.publish_assets import upload_web_export

object_storage = ObjectStorageService(...)  # must be configured for your backend
summary = upload_web_export(object_storage, app_prefix="apps/x", required=False)
print(summary)
```

Optionally build locally (if `package.json` exists and tooling is installed):
```python
from naas_abi_marketplace.applications.x.apps.x.web.publish_assets import maybe_build_web, upload_web_export
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService

maybe_build_web(force=False)
upload_web_export(ObjectStorageService(...), app_prefix="apps/x")
```

## Caveats
- A valid export directory is defined as a directory containing `index.html`.
- `upload_web_export(..., required=True)` raises if no export is found; set `required=False` to skip uploading web assets when missing.
- `maybe_build_web` runs `pnpm`/`npm` subprocess commands and will raise if it cannot install dependencies or build.
