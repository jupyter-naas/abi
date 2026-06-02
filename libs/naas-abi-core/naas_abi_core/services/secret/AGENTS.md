# Secret Service — AGENTS.md

> Scope: `libs/naas-abi-core/naas_abi_core/services/secret/`. Canonical reference for agents.

## Purpose

Unified interface for reading / writing secrets across multiple backends. The service composes a **list** of adapters: `get` consults them in order (first hit wins), `set` / `remove` propagate to all, `list` merges (earlier adapters override later ones).

Emits `SecretSet` / `SecretRemoved` / `SecretError` events.

## Files

```
secret/
├── SecretPorts.py     # ISecretService, ISecretAdapter, SecretAuthenticationError
├── Secret.py          # public service
├── Secret_test.py
├── adaptors/secondary/
│   ├── Base64Secret.py
│   ├── NaasSecret.py
│   └── DotenvSecretSecondaryAdaptor.py
└── ontologies/        # SecretSet, SecretRemoved, SecretError
```

## Port (`SecretPorts.py`)

```python
class ISecretAdapter:
    def get(key: str, default=None) -> str | Any | None
    def set(key: str, value: str) -> None
    def remove(key: str) -> None                    # no-op on missing keys
    def list() -> Dict[str, str | None]

class ISecretService:                              # same surface
    ...

class SecretAuthenticationError(Exception): ...
```

## Service API (`Secret.py`)

```python
Secret(adapters: List[ISecretAdapter])

get(key, default=None) -> str                       # first adapter that returns non-default wins
set(key, value)                                     # writes to all adapters; → SecretSet
remove(key)                                         # removes from all adapters; → SecretRemoved
list() -> Dict[str, str | None]                     # merged view (earlier overrides later)
```

## Available Adapters

| Adapter | Backend / Notes |
|---|---|
| `DotenvSecretSecondaryAdaptor(path=".env")` | Reads / writes `.env` files with thread-safe locking |
| `NaasSecret(naas_api_key, naas_api_url=None)` | Naas API over HTTPS (Bearer token) |
| `Base64Secret(secret_adapter, base64_secret_key)` | **Decorator** — wraps another adapter; encodes / decodes a base64 dotenv blob under a single key |

## Instantiation

No factory file. Wire directly:

```python
from naas_abi_core.services.secret.Secret import Secret
from naas_abi_core.services.secret.adaptors.secondary.DotenvSecretSecondaryAdaptor import (
    DotenvSecretSecondaryAdaptor,
)
from naas_abi_core.services.secret.adaptors.secondary.NaasSecret import NaasSecret

secret = Secret(adapters=[
    DotenvSecretSecondaryAdaptor(".env"),       # local override wins
    NaasSecret(naas_api_key=os.environ["NAAS_API_KEY"]),
])
```

## Tests

```bash
uv run pytest libs/naas-abi-core/naas_abi_core/services/secret/Secret_test.py
uv run pytest libs/naas-abi-core/naas_abi_core/services/secret/adaptors/secondary/Base64Secret_test.py
uv run pytest libs/naas-abi-core/naas_abi_core/services/secret/adaptors/secondary/NaasSecret_test.py
```

## Adding a new adapter

1. Implement `ISecretAdapter` in `adaptors/secondary/<Name>.py`. All four methods.
2. `remove` **must be idempotent** — never raise on missing keys.
3. Raise `SecretAuthenticationError` for auth-related failures so callers can differentiate.
4. Add `<Name>_test.py` and verify `list()` round-trips against `set()` / `remove()`.
