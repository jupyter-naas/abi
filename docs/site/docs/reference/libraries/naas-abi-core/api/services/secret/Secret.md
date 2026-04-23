# Secret

## What it is
A secret management facade that coordinates multiple secret adapters (e.g., env vars, files, cloud backends) behind a consistent interface. It searches adapters in order for reads and can write/remove across all adapters.

## Public API
- **class `Secret(ServiceBase, ISecretService)`**
  - **`__init__(adapters: List[ISecretAdapter])`**
    - Create the service with an ordered list of adapters.
  - **`get(key: str, default: Any = None) -> str`**
    - Read a secret by key from the first adapter that returns a non-`None` value; otherwise return `default`.
  - **`set(key: str, value: str) -> None`**
    - Write a secret to all configured adapters (no built-in error handling).
  - **`remove(key: str) -> None`**
    - Remove a secret key from all configured adapters.
  - **`list() -> Dict[str, str | None]`**
    - Merge secrets from all adapters into one dict; earlier adapters in the list take precedence on key conflicts.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.services.secret.SecretPorts.ISecretAdapter` (must provide `get`, `set`, `remove`, `list`)
  - `naas_abi_core.services.secret.SecretPorts.ISecretService`
  - `naas_abi_core.services.ServiceBase.ServiceBase`
- Adapter ordering is significant:
  - `get()` checks adapters in the provided order.
  - `list()` processes adapters in reverse so earlier adapters override later ones.

## Usage
```python
from naas_abi_core.services.secret.Secret import Secret
from naas_abi_core.services.secret.adapters import EnvVarSecretAdapter, FileSecretAdapter

secret_service = Secret([
    EnvVarSecretAdapter(),
    FileSecretAdapter("/path/to/secrets"),
])

api_key = secret_service.get("API_KEY", default="missing")
secret_service.set("NEW_KEY", "value")
all_secrets = secret_service.list()
secret_service.remove("OLD_KEY")
```

## Caveats
- `set()` and `remove()` do not handle or suppress exceptions explicitly; any adapter errors will propagate unless adapters implement their own handling.
- `get()` treats `None` as “not found”; adapters must return `None` to indicate missing keys.
