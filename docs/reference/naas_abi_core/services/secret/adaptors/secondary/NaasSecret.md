# NaasSecret

## What it is
- A secondary `ISecretAdapter` implementation that manages secrets via the Naas API (`https://api.naas.ai` by default).
- Uses `requests` to `GET/POST/DELETE` secrets and logs errors via `naas_abi_core.logger`.

## Public API
- `class NaasSecret(ISecretAdapter)`
  - `__init__(naas_api_key: str, naas_api_url: str | None = None)`
    - Creates an adapter using the provided API key and optional base URL.
  - `get(key: str, default: Any = None) -> str | Any | None`
    - Fetches a secret value by name.
    - Returns the secret value as `str` on success; returns `default` on non-auth errors/404.
    - Raises `SecretAuthenticationError` on HTTP 401.
  - `set(key: str, value: str) -> None`
    - Creates/updates a secret.
    - Logs an error and returns on HTTP error.
  - `remove(key: str) -> None`
    - Deletes a secret by name.
    - Logs an error and returns on HTTP error.
  - `list() -> Dict[str, str | None]`
    - Lists secrets (name → value) from the API.
    - Returns `{}` on HTTP error (with specific debug log on 404).

## Configuration/Dependencies
- Requires:
  - `requests`
  - `naas_abi_core.logger`
  - `naas_abi_core.services.secret.SecretPorts`:
    - `ISecretAdapter`
    - `SecretAuthenticationError`
- Configuration:
  - `naas_api_key` (required): used as `Authorization: Bearer <key>`.
  - `naas_api_url` (optional): defaults to `https://api.naas.ai`.

## Usage
```python
from naas_abi_core.services.secret.adaptors.secondary.NaasSecret import NaasSecret

adapter = NaasSecret(naas_api_key="YOUR_NAAS_API_KEY")

adapter.set("MY_SECRET", "hello")
value = adapter.get("MY_SECRET", default=None)
print(value)

print(adapter.list())

adapter.remove("MY_SECRET")
```

## Caveats
- `get()` returns `default` for missing secrets (404) and most other HTTP errors, but **raises** `SecretAuthenticationError` for 401 responses.
- `list()` sends pagination parameters in the JSON body of a `GET` request (as implemented), and returns `{}` on errors.
- All returned secret values are coerced to `str`.
