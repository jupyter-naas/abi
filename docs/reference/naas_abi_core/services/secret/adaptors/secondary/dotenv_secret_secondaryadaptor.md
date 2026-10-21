# DotenvSecretSecondaryAdaptor

## What it is
- A secondary secret adapter implementing `ISecretAdapter` that reads secrets from a `.env` file and falls back to process environment variables.
- Supports thread-safe `get/set/remove/list` operations using an internal lock.
- Preserves the `.env` file’s original owner/group after writes (to avoid permission issues when `python-dotenv` rewrites the file).

## Public API
- **Class:** `DotenvSecretSecondaryAdaptor(ISecretAdapter)`
  - **`__init__(path: str = ".env")`**
    - Requires the file at `path` to exist; otherwise raises `FileNotFoundError`.
    - Loads secrets from the `.env` file into `self.secrets` via `dotenv_values`.
  - **`get(key: str, default: Any = None) -> str | Any | None`**
    - Returns the value from loaded `.env` secrets first (as `str`).
    - Falls back to `os.environ`.
    - Returns `default` if not found.
  - **`set(key: str, value: str) -> None`**
    - Writes to `os.environ`.
    - Persists the key/value into the `.env` file via `set_key`.
    - Updates the in-memory `self.secrets`.
  - **`remove(key: str) -> None`**
    - Removes the key from the `.env` file via `unset_key`.
    - Removes the key from in-memory `self.secrets` and `os.environ`.
  - **`list() -> dict[str, str | None]`**
    - Returns a dict of currently in-memory secrets (`self.secrets`) with keys cast to `str` and values cast via `str(...)`.

## Configuration/Dependencies
- **Filesystem**
  - `.env` file must exist at `path` when the adapter is constructed.
- **Python packages**
  - `python-dotenv` (`dotenv_values`, `find_dotenv`, `set_key`, `unset_key`)
- **Runtime**
  - Uses `os.environ` for fallback reads and as a write target.
- **Logging**
  - Uses `naas_abi_core.utils.Logger.logger` for debug and warning logs.
- **Ownership handling**
  - After modifying `.env`, attempts to restore the original file owner/group (uses `os.stat` and `os.chown`).

## Usage
```python
from naas_abi_core.services.secret.adaptors.secondary.dotenv_secret_secondaryadaptor import (
    DotenvSecretSecondaryAdaptor,
)

# Ensure the .env file exists before instantiation
adapter = DotenvSecretSecondaryAdaptor(path=".env")

# Read: .env first, then os.environ, else default
token = adapter.get("API_TOKEN", default=None)

# Write: updates os.environ and persists to .env
adapter.set("API_TOKEN", "secret-value")

# List current in-memory secrets
print(adapter.list())

# Remove: unsets from .env, in-memory, and os.environ
adapter.remove("API_TOKEN")
```

## Caveats
- Initialization fails with `FileNotFoundError` if the `.env` file does not exist.
- In-memory secrets are loaded once at `__init__`, but `set()`/`remove()` also update the in-memory `self.secrets`; external edits to `.env` are not automatically reloaded.
- Owner/group restoration after writes may fail (logs a warning) if the process lacks permissions to `chown`.
