# Storage

## What it is
Utilities for locating a project-level `storage/` directory and ensuring module/component data directories exist under a standardized path.

## Public API

- **Exception**
  - `NoStorageFolderFound`: Raised when a `storage` folder cannot be found while traversing up to `/`.

- **Functions**
  - `find_storage_folder(base_path: str, needle: str = "storage") -> str`  
    Searches upward from `base_path` for a folder named `needle` (default: `"storage"`). Returns the matched path or raises `NoStorageFolderFound`.
  - `ensure_data_directory(module_name: str, component: str) -> str`  
    Creates (if needed) and returns the absolute path for:
    `storage/datastore/core/modules/<module_name>/<component>`

## Configuration/Dependencies
- Standard library: `os`
- Filesystem access required (for existence checks and directory creation).

## Usage

```python
from naas_abi_core.utils.Storage import find_storage_folder, ensure_data_directory

# Find a storage folder by walking up from current working directory
storage_path = find_storage_folder(os.getcwd())
print(storage_path)

# Ensure a module/component data directory exists
data_dir = ensure_data_directory("__demo__", "orchestration")
print(data_dir)
```

## Caveats
- `find_storage_folder` stops only when `base_path == "/"`; on non-POSIX systems this may not match the filesystem root semantics.
- `ensure_data_directory` creates directories relative to the current working directory (it does not call `find_storage_folder`).
