# Secret

## What it is
- A secret management service that provides a unified interface to retrieve, store, remove, and list secrets across multiple backends via pluggable adapters.
- Acts as a facade over a list of `ISecretAdapter` implementations.

## Public API
- `class Secret(ServiceBase, ISecretService)`
  - `__init__(adapters: List[ISecretAdapter])`
    - Create the service with an ordered list of secret adapters.
  - `get(key: str, default: Any = None) -> str`
    - Return the first non-`None` value for `key` found when querying adapters in order; otherwise return `default`.
  - `set(key: str, value: str) -> None`
    - Set `key/value` on **all** configured adapters.
  - `remove(key: str) -> None`
    - Remove `key` from **all** configured adapters.
  - `list() -> Dict[str, str | None]`
    - Merge secrets from all adapters into one dictionary.
    - If a key exists in multiple adapters, the **earlier** adapter in the configured list has precedence.

## Configuration/Dependencies
- Requires:
  - A list of adapter instances implementing `naas_abi_core.services.secret.SecretPorts.ISecretAdapter`.
- Inherits from:
  - `naas_abi_core.services.ServiceBase.ServiceBase`
- Implements:
  - `naas_abi_core.services.secret.SecretPorts.ISecretService`

## Usage
```python
from naas_abi_core.services.secret.Secret import Secret
from naas_abi_core.services.secret.adapters import EnvVarSecretAdapter, FileSecretAdapter

adapters = [
    EnvVarSecretAdapter(),                # higher priority
    FileSecretAdapter("/path/to/secrets")  # lower priority
]
secrets = Secret(adapters)

# Read with fallback
api_key = secrets.get("API_KEY", default="default_key")

# Write to all backends
secrets.set("API_KEY", "your-secret-api-key")

# List merged view (earlier adapters override later ones)
all_secrets = secrets.list()

# Remove from all backends
secrets.remove("API_KEY")
```

## Caveats
- Adapter order matters:
  - `get()` returns the first non-`None` value found in adapter order.
  - `list()` merges adapters such that earlier adapters override later ones.
- `set()` and `remove()` do not perform error handling in this module; any exceptions are not caught here.
