# Storage

## What it is
Utility helpers for locating a project-level `storage/` directory and ensuring module/component data directories exist under a standard layout.

## Public API
- **Exception**
  - `NoStorageFolderFound`: Raised by `find_storage_folder()` when no `storage` folder is found up to filesystem root (`/`).

- **Functions**
  - `find_storage_folder(base_path: str, needle: str = "storage") -> str`  
    Recursively searches upward from `base_path` for a directory named `needle` (default: `storage`) and returns its path.
  - `ensure_data_directory(module_name: str, component: str) -> str`  
    Creates (if needed) and returns the absolute path to:
    `storage/datastore/core/modules/<module_name>/<component>`

## Configuration/Dependencies
- Uses the standard library `os` module.
- `ensure_data_directory()` creates directories relative to the current working directory.

## Usage
```python
from naas_abi_core.utils.Storage import find_storage_folder, ensure_data_directory, NoStorageFolderFound

# Ensure a module/component data directory exists (created relative to CWD)
data_dir = ensure_data_directory("__demo__", "orchestration")
print(data_dir)  # absolute path

# Find the nearest "storage" folder by walking up from a starting path
try:
    storage_path = find_storage_folder(data_dir)  # or any base path within the project
    print(storage_path)
except NoStorageFolderFound:
    print("No storage folder found")
```

## Caveats
- `find_storage_folder()`:
  - Assumes a Unix-style root (`/`) as the stop condition.
  - Only checks existence of the `needle` path; it does not validate that it is a directory.
- `ensure_data_directory()`:
  - Creates directories under `./storage/...` based on the current working directory, not based on `find_storage_folder()`.
