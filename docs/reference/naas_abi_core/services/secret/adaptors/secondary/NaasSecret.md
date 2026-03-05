# NaasSecret

## What it is
- `NaasSecret` is a secondary adapter implementing `ISecretAdapter` to manage secrets stored in the Naas API.
- It uses HTTP requests (`requests`) with Bearer token authentication.

## Public API
- **Class `NaasSecret(ISecretAdapter)`**
  - `__init__(naas_api_key: str, naas_api_url: str | None = None)`
    - Stores the API key and sets the base URL (defaults to `https://api.naas.ai`).
  - `get(key: str, default: Any = None) -> str | Any | None`
    - Fetches a secret value by name.
    - Returns the secret value as a `str` on success; returns `default` on most HTTP errors.
    - Raises `SecretAuthenticationError` on HTTP 401.
  - `set(key: str, value: str) -> None`
    - Creates/updates a secret with the given name and value.
    - Logs an error on HTTP failure; does not raise.
  - `remove(key: str) -> None`
    - Deletes a secret by name.
    - Logs an error on HTTP failure; does not raise.
  - `list() -> Dict[str, str | None]`
    - Lists secrets and returns a dict mapping secret names to values (both coerced to `str`).
    - Returns `{}` on HTTP failure.

## Configuration/Dependencies
- **Dependencies**
  - `requests` for HTTP calls.
  - `naas_abi_core.logger` for logging.
  - `naas_abi_core.services.secret.SecretPorts`:
    - `ISecretAdapter`
    - `SecretAuthenticationError`
- **Configuration**
  - `naas_api_key` (required): used as `Authorization: Bearer <token>`.
  - `naas_api_url` (optional): overrides default `https://api.naas.ai`.

## Usage
```python
from naas_abi_core.services.secret.adaptors.secondary.NaasSecret import NaasSecret

secrets = NaasSecret(naas_api_key="YOUR_NAAS_API_KEY")

# Set a secret
secrets.set("MY_KEY", "my-value")

# Get a secret (returns default if not found or on most errors)
value = secrets.get("MY_KEY", default=None)
print(value)

# List secrets
print(secrets.list())

# Remove a secret
secrets.remove("MY_KEY")
```

## Caveats
- `get()`:
  - Returns `default` on non-401 HTTP errors (including 404).
  - Raises `SecretAuthenticationError` on HTTP 401.
- All returned secret values are coerced to `str` (`str(...)`), including when listing.
- `list()` uses `requests.get(..., json={...})` to send pagination parameters in a JSON body (not query params).
