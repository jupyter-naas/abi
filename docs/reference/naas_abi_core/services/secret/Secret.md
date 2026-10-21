# Secret

## What it is
- A secret management service that provides a single interface to **get**, **set**, **remove**, and **list** secrets across multiple storage backends via pluggable adapters.
- Acts as a facade over an ordered list of `ISecretAdapter` implementations.

## Public API
- `class Secret(ServiceBase, ISecretService)`
  - `__init__(adapters: list[ISecretAdapter])`
    - Construct the service with an ordered list of secret adapters.
  - `adapters -> list[ISecretAdapter]` (property)
    - Exposes the wrapped adapters (e.g., for introspection by other components).
  - `get(key: str, default: Any = None) -> str`
    - Query adapters in order and return the **first non-None** value; otherwise return `default`.
  - `set(key: str, value: str) -> None`
    - Call `set` on **all** adapters.
    - Publishes `SecretSet` on success; publishes `SecretError` and re-raises on exception.
  - `remove(key: str) -> None`
    - Call `remove` on **all** adapters.
    - Publishes `SecretRemoved` on success; publishes `SecretError` and re-raises on exception.
  - `list() -> dict[str, str | None]`
    - Merge `adapter.list()` from all adapters into one dict.
    - **Earlier adapters take precedence** on key conflicts (implemented by updating from adapters in reverse order).

## Configuration/Dependencies
- Requires:
  - `adapters: list[ISecretAdapter]` implementing `naas_abi_core.services.secret.SecretPorts.ISecretAdapter`.
- Inherits from:
  - `naas_abi_core.services.ServiceBase.ServiceBase`
- Implements:
  - `naas_abi_core.services.secret.SecretPorts.ISecretService`
- Optional event publishing:
  - If `ServiceBase` is wired and events are available, emits:
    - `SecretSet`, `SecretRemoved`, `SecretError` (from `naas_abi_core.services.secret.ontologies.modules.SecretEventOntology`).
  - Event publishing failures are caught and logged; secret operations remain the source of truth.

## Usage
```python
from naas_abi_core.services.secret.Secret import Secret
from naas_abi_core.services.secret.adapters import EnvVarSecretAdapter, FileSecretAdapter

secret_service = Secret([
    EnvVarSecretAdapter(),                # higher priority
    FileSecretAdapter("/path/to/secrets")  # lower priority
])

# Read with fallback
api_key = secret_service.get("API_KEY", default="default_key")

# Write to all backends
secret_service.set("API_KEY", "your-secret-api-key")

# List merged view (earlier adapters override later ones)
all_secrets = secret_service.list()

# Remove from all backends
secret_service.remove("API_KEY")
```

## Caveats
- Adapter order matters:
  - `get()` returns the first non-`None` value found in adapter order.
  - `list()` merges such that earlier adapters override later ones.
- `set()`/`remove()`:
  - If any adapter raises, the method publishes `SecretError` (when possible) and **re-raises** the exception.
