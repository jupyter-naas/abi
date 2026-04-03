# DotenvSecretSecondaryAdaptor

## What it is
- A secondary secret adapter implementing `ISecretAdapter` that reads secrets from a `.env` file (via `python-dotenv`) with a fallback to environment variables.
- Supports retrieving, setting, removing, and listing secrets.

## Public API
- `class DotenvSecretSecondaryAdaptor(ISecretAdapter)`
  - `__init__(path: str = ".env")`
    - Loads secrets from the given `.env` file.
    - Raises `FileNotFoundError` if the file does not exist.
  - `get(key: str, default: Any = None) -> str | Any | None`
    - Returns the secret value for `key`:
      - First from loaded `.env` values (as `str`)
      - Then from `os.environ`
      - Otherwise returns `default`
  - `set(key: str, value: str) -> None`
    - Sets `key` in `os.environ` and writes/updates it in the `.env` file.
  - `remove(key: str) -> None`
    - Removes `key` from `os.environ` only.
  - `list() -> Dict[str, str | None]`
    - Returns a dict of all keys loaded from the `.env` file with their values stringified.

## Configuration/Dependencies
- Requires an existing `.env` file at `path` (default: `.env`).
- Depends on:
  - `python-dotenv` (`dotenv_values`, `find_dotenv`, `set_key`)
  - `naas_abi_core.services.secret.SecretPorts.ISecretAdapter`
  - `naas_abi_core.utils.Logger.logger`
- Uses:
  - File system (`os.path.exists`)
  - Environment variables (`os.environ`)

## Usage
```python
from naas_abi_core.services.secret.adaptors.secondary.dotenv_secret_secondaryadaptor import (
    DotenvSecretSecondaryAdaptor,
)

# Ensure .env exists before instantiating
adapter = DotenvSecretSecondaryAdaptor(path=".env")

# Read with fallback to env and then default
api_key = adapter.get("API_KEY", default="missing")

# Write to env and persist to .env
adapter.set("API_KEY", "supersecret")

# List values loaded from .env
print(adapter.list())

# Remove only from current process environment
adapter.remove("API_KEY")
```

## Caveats
- The `.env` file must already exist; initialization fails otherwise.
- `.env` contents are loaded once during initialization; subsequent external changes to the file are not reloaded automatically.
- `remove()` does not remove the key from the `.env` file; it only unsets it from `os.environ`.
