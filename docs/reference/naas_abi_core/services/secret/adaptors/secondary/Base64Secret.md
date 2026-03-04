# Base64Secret

## What it is
- An `ISecretAdapter` implementation that stores multiple secrets inside a single underlying secret value.
- The underlying secret is a Base64-encoded `.env`-style text (key/value pairs) stored under one key (`base64_secret_key`) in another `ISecretAdapter`.

## Public API
- `class Base64Secret(ISecretAdapter)`
  - `__init__(secret_adapter: ISecretAdapter, base64_secret_key: str)`
    - Wraps another adapter and names the single underlying secret key where the Base64 payload is stored.
  - `get(key: str, default: Any = None) -> str | Any | None`
    - Returns the decoded value for `key` from the Base64 `.env` payload; falls back to `default` if missing.
  - `set(key: str, value: str) -> None`
    - Updates/creates `key` in the decoded map, re-encodes the full `.env` content to Base64, and writes it back to `secret_adapter` under `base64_secret_key`.
  - `remove(key: str) -> None`
    - Removes `key` (if present), re-encodes, and writes back to `secret_adapter` under `base64_secret_key`.
  - `list() -> Dict[str, str | None]`
    - Returns all decoded secrets as a dict.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.services.secret.SecretPorts.ISecretAdapter` (the wrapped adapter providing actual persistence)
  - `python-dotenv` (`dotenv_values`) for parsing `.env` formatted content
  - Python stdlib: `base64`, `io.StringIO`

## Usage
```python
from naas_abi_core.services.secret.adaptors.secondary.Base64Secret import Base64Secret
from naas_abi_core.services.secret.SecretPorts import ISecretAdapter

# Minimal in-memory adapter for demonstration
class MemorySecretAdapter(ISecretAdapter):
    def __init__(self):
        self._store = {}

    def get(self, key, default=None):
        return self._store.get(key, default)

    def set(self, key, value):
        self._store[key] = value

    def remove(self, key):
        self._store.pop(key, None)

    def list(self):
        return dict(self._store)

backend = MemorySecretAdapter()

# All secrets are stored inside backend under a single key "ENV_B64"
secrets = Base64Secret(backend, base64_secret_key="ENV_B64")

secrets.set("API_KEY", "abc123")
print(secrets.get("API_KEY"))       # "abc123"
print(secrets.list())              # {"API_KEY": "abc123"}

secrets.remove("API_KEY")
print(secrets.get("API_KEY", None))  # None
```

## Caveats
- If the underlying stored value for `base64_secret_key` is not valid Base64 or does not decode as UTF-8, decoding will raise an exception (not handled in this class).
- Values are always written as strings in `.env` format: `KEY="value"`.
- When the underlying Base64 secret is empty (`""`), `list()` returns `{}` and `get()` returns the provided default.
