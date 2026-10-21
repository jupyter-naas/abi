# errors

## What it is
Portable domain failure types for Naas ABI services. Defines service-level exception classes (derived from `RPCError`) and a helper to convert transport errors into domain-specific errors.

## Public API
- **Exceptions**
  - `ServiceError(RPCError)`: Base error for service/domain failures.
  - `ObjectNotFound(ServiceError)`
  - `ObjectAlreadyExists(ServiceError)`
  - `DocumentNotFound(ServiceError)`
  - `CollectionNotFound(ServiceError)`
  - `VersionConflict(ServiceError)`
  - `UniqueViolation(ServiceError)`
  - `CacheNotFoundError(ServiceError)`
  - `CacheExpiredError(ServiceError)`
  - `KVNotFoundError(ServiceError)`
  - `SecretAuthenticationError(ServiceError)`

- **Constants**
  - `ERRORS: dict[str, type[ServiceError]]`: Maps string error codes (e.g., `"OBJECT_NOT_FOUND"`) to the corresponding exception class.

- **Functions**
  - `domain_error(error: RPCError) -> ServiceError`:
    - Converts an `RPCError` into a domain-specific `ServiceError` subclass based on `error.code`.
    - Falls back to `ServiceError` when the code is not recognized.
    - Preserves `error.response` by passing it through to the new exception.

## Configuration/Dependencies
- Depends on `naas_abi_sdk.transport.RPCError`.
- No runtime configuration.

## Usage
```python
from naas_abi_sdk.services.errors import domain_error, ObjectNotFound
from naas_abi_sdk.transport import RPCError

try:
    # some RPC call that raises RPCError
    raise RPCError("OBJECT_NOT_FOUND", "Missing resource", response={"status": 404})
except RPCError as e:
    raise domain_error(e)

# elsewhere
try:
    ...
except ObjectNotFound:
    print("Handle missing object")
```

## Caveats
- `domain_error` relies on `error.code` matching keys in `ERRORS`; unknown codes are wrapped as `ServiceError`.
