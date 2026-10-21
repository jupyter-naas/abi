# ABI Marketplace (`marketplace.py`)

## What it is
- A Streamlit app that renders an “ABI Marketplace” UI to:
  - List predefined local Streamlit apps (by port).
  - Discover module directories from specific filesystem locations.
  - Search and filter items (All / Apps / Modules / Running).
  - Launch running apps in a browser, or start stopped apps via `streamlit run`.

## Public API
This file is primarily a Streamlit script (executed top-to-bottom). The reusable public functions are:

- `get_app_status(port: int) -> str`
  - Checks `http://localhost:{port}` with a 2s timeout.
  - Returns `"running"` if HTTP 200, otherwise `"stopped"`.

- `load_modules_from_path(path: Path, module_type: str = "module") -> List[Dict[str, Any]]`
  - Scans immediate subdirectories of `path` (excluding names starting with `__`).
  - Attempts to read `agents/*Agent.py` files to extract:
    - `AVATAR_URL = "..."` (used as icon URL)
    - `DESCRIPTION = "..."` (used as description)
  - Falls back to:
    - An emoji icon based on directory name, or `"🧠"` if unknown.
    - A default description: `AI module with {module_dir.name} capabilities`
  - For `module_type` containing `"domain"`: formats name by replacing `-` with spaces and title-casing.

- `get_modules() -> List[Dict[str, Any]]`
  - Aggregates module entries from:
    - `src/core/modules` (`"core-module"`)
    - `src/custom/modules` (`"custom-module"`)
    - `src/marketplace/modules/domains/modules` (`"domain-expert"`)
    - `src/marketplace/modules/applications` (`"marketplace-app"`)

Other notable top-level data:
- `apps_data`: hardcoded list of apps with `name`, `port`, `icon`, `description`; augmented at runtime with:
  - `status` from `get_app_status(port)`
  - `type = "app"`

## Configuration/Dependencies
- **Runtime**:
  - `streamlit`
  - `requests`
- **Environment assumptions**:
  - Localhost ports are used to detect app status (`http://localhost:{port}`).
  - Starting apps requires the `streamlit` CLI available on `PATH`.
- **Filesystem conventions for modules**:
  - Module folders under the paths listed in `get_modules()`.
  - Optional metadata extraction from: `<module_dir>/agents/*Agent.py` lines beginning with:
    - `AVATAR_URL = `
    - `DESCRIPTION = `

## Usage
Run as a Streamlit app:

```bash
streamlit run libs/naas-abi-marketplace/marketplace.py
```

Optional: reuse the helper functions in Python (e.g., in another script):

```python
from pathlib import Path
from libs.naas_abi_marketplace.marketplace import get_app_status, load_modules_from_path

print(get_app_status(8500))
modules = load_modules_from_path(Path("src/core/modules"), module_type="core-module")
print(modules[:1])
```

## Caveats
- Importing this module will execute Streamlit page setup and UI rendering immediately (it is not structured as a library module).
- “Install” for modules is UI-only: it only displays a success message and does not perform installation logic.
- Launching stopped apps relies on a hardcoded `port -> app file` mapping and `os.path.exists(app_file)`; if paths differ, launching will fail.
- Status detection treats any non-200 response (or request error) as `"stopped"`.
