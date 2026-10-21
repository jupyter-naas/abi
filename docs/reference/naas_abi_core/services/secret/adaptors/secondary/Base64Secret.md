# Base64Secret

## What it is
- `Base64Secret` is an `ISecretAdapter` implementation that stores multiple key/value secrets inside a single underlying secret value.
- The underlying secret is a Base64-encoded `.env`-style text (parsed via `python-dotenv`), fetched and persisted through another `ISecretAdapter`.

## Public API
- `class Base64Secret(ISecretAdapter)`
  - `__init__(secret_adapter: ISecretAdapter, base64_secret_key: str)`
    - Wraps an existing secret adapter and uses `base64_secret_key` as the storage location for the Base64-encoded bundle.
  - `get(key: str, default: Any = None) -> str | Any | None`
    - Returns the decoded value for `key`, or `default` if not present.
  - `set(key: str, value: str) -> None`
    - Updates/creates `key` in the decoded bundle and writes the re-encoded bundle back to `base64_secret_key`.
  - `remove(key: str) -> None`
    - Removes `key` from the decoded bundle (no-op if missing) and writes the updated bundle back.
  - `list() -> Dict[str, str | None]`
    - Returns all decoded secrets as a dict.

## Configuration/Dependencies
- Depends on:
  - An underlying `ISecretAdapter` instance (`secret_adapter`) that implements `get` and `set`.
  - `python-dotenv` (`dotenv_values`) for parsing `.env` content.
  - Standard library `base64` for encoding/decoding.

## Usage
```python
from naas_abi_core.services.secret.adaptors.secondary.Base64Secret import Base64Secret
from naas_abi_core.services.secret.SecretPorts import ISecretAdapter

class MemorySecretAdapter(ISecretAdapter):
    def __init__(self):
        self.store = {}
    def get(self, key, default=None):
        return self.store.get(key, default)
    def set(self, key, value):
        self.store[key] = value
    def remove(self, key):
        self.store.pop(key, None)
    def list(self):
        return dict(self.store)

underlying = MemorySecretAdapter()
secrets = Base64Secret(underlying, base64_secret_key="B64_SECRETS")

secrets.set("API_KEY", "abc123")
print(secrets.get("API_KEY"))          # "abc123"
print(secrets.list())                  # {"API_KEY": "abc123"}
secrets.remove("API_KEY")
print(secrets.get("API_KEY", None))    # None
```

## Caveats
- If the underlying value at `base64_secret_key` is not valid Base64 or not valid UTF-8 after decoding, decoding will raise an exception.
- Values are written as `.env` lines in the form `KEY="value"`. Values are coerced to strings when decoding and when setting.
