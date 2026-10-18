# apps (remote module web apps over NATS)

## What it is
Utilities for discovering and describing web apps shipped alongside a Python module. An app is a folder under `apps/<name>/` containing a `manifest.json`, plus static assets. The module can advertise these apps via protobuf descriptors.

## Public API

### Constants
- `MAX_APPS = 16`: Maximum number of apps a module may serve.
- `DEFAULT_ENTRY = "index.html"`: Default entry page when not specified.
- `DEFAULT_MAX_UPLOAD_BYTES = 1024 * 1024 * 1024`: Default upload limit (1 GiB) when the manifest sets none.

### `AppDescriptor` (dataclass)
Represents a single app and its metadata.

Fields:
- `name: str`: App folder/name (must match `[A-Za-z0-9_-]{1,64}`).
- `title: str = ""`
- `description: str = ""`
- `category: str = "module"`
- `icon_emoji: str = ""`
- `entry: str = DEFAULT_ENTRY`: Relative path; must not start with `/` and must not contain `..` path segments.
- `contract_major: int = 1`
- `max_upload_bytes: int = 0`: `0` means use default 1 GiB; must be non-negative.
- `root: Path | None = None`: Folder where files are served from.

Methods / properties:
- `upload_limit -> int`: Returns `max_upload_bytes` if non-zero, otherwise `DEFAULT_MAX_UPLOAD_BYTES`.
- `to_pb() -> naas_abi_proto.discovery.v1.discovery_pb2.AppDescriptor`: Converts to protobuf descriptor.

### `read_app(folder: Path) -> AppDescriptor`
- Reads `folder/manifest.json` and returns an `AppDescriptor`.
- `name` is taken from `folder.name`.
- Manifest keys used:
  - `name` (string) → `title` (defaults to folder name if missing/invalid type)
  - `description` (string)
  - `category` (string, default `"module"`)
  - `icon_emoji` (string)
  - `url` (string): if it is `html:<file>`, sets `entry` to `<file>`, else uses `index.html`
  - `max_upload_bytes` (int ≥ 0): invalid types (including `bool`) raise `ValueError`

### `module_apps_dir(module_type: type) -> Path | None`
- Returns the `apps/` directory next to the module’s package file (`__init__.py` / module `__file__`), if it exists.
- Returns `None` if the module has no `__file__` or if `apps/` is not a directory.

### `discover_apps(module_type: type) -> tuple[AppDescriptor, ...]`
- Discovers all `apps/<name>/manifest.json` folders under the module’s `apps/` directory.
- Returns a tuple of `AppDescriptor` sorted by folder name.
- Raises `ValueError` if more than `MAX_APPS` apps are found.

## Configuration/Dependencies
- Reads app manifests from the filesystem:
  - Layout: `<module_package_dir>/apps/<app_name>/manifest.json`
- Requires `naas_abi_proto.discovery.v1.discovery_pb2` for `AppDescriptor.to_pb()`.

## Usage

```python
from pathlib import Path
from naas_abi_sdk.apps import discover_apps, read_app

# Example: discover apps shipped next to a module package
apps = discover_apps(module_type=SomeModuleClass)
for app in apps:
    print(app.name, app.entry, app.upload_limit)

# Example: read a single app folder directly
desc = read_app(Path("apps/my_app"))
print(desc.to_pb())  # protobuf descriptor
```

## Caveats
- App names must match `[A-Za-z0-9_-]{1,64}` (used as a URL segment).
- `entry` must be a relative path and must not contain `..` segments.
- `max_upload_bytes` must be a non-negative integer; `bool` values are rejected.
- A module may expose at most `MAX_APPS` apps; exceeding this raises `ValueError`.
