# DotenvSecretSecondaryAdaptor

## What it is
- A secondary secret adapter implementing `ISecretAdapter` that reads secrets from a `.env` file and falls back to process environment variables.
- Supports thread-safe `get/set/remove/list` operations using an internal lock.

## Public API
- **Class:** `DotenvSecretSecondaryAdaptor(ISecretAdapter)`
  - **`__init__(path: str = ".env")`**
    - Validates the `.env` file exists at `path`.
    - Loads key/value pairs from the file via `dotenv_values`.
  - **`get(key: str, default: Any = None) -> str | Any | None`**
    - Returns the secret as `str` if found in loaded `.env` values.
    - Otherwise returns `os.environ[key]` if present.
    - Otherwise returns `default`.
  - **`set(key: str, value: str)`**
    - Sets `os.environ[key] = value`.
    - Persists the key to the `.env` file via `set_key(path, key, value)`.
  - **`remove(key: str)`**
    - Removes the key from `os.environ` only (does **not** delete from the `.env` file).
  - **`list() -> Dict[str, str | None]`**
    - Returns a dict of keys from the initially loaded `.env` file with values converted to `str`.

## Configuration/Dependencies
- **Filesystem**
  - Requires the `.env` file to exist at initialization (`path`), otherwise raises `FileNotFoundError`.
- **Python packages**
  - `python-dotenv` (`dotenv_values`, `find_dotenv`, `set_key`)
- **Runtime**
  - Uses `os.environ` as a fallback source and as a write target for `set/remove`.
- **Logging**
  - Uses `naas_abi_core.utils.Logger.logger` for debug logs.

## Usage
```python
from naas_abi_core.services.secret.adaptors.secondary.dotenv_secret_secondaryadaptor import (
    DotenvSecretSecondaryAdaptor,
)

# Ensure .env exists before instantiating
adapter = DotenvSecretSecondaryAdaptor(path=".env")

# Read (checks .env first, then environment variables)
token = adapter.get("API_TOKEN", default="missing")

# Write (updates environment and persists to .env)
adapter.set("API_TOKEN", "secret-value")

# List keys loaded from .env at initialization time
print(adapter.list())

# Remove from environment only
adapter.remove("API_TOKEN")
```

## Caveats
- The `.env` file must exist before constructing the adapter.
- `remove()` only removes the key from `os.environ`; it does not delete the key from the `.env` file.
- `.env` values are loaded once during `__init__`; subsequent updates to the `.env` file are not reloaded into `self.secrets` by this class.
