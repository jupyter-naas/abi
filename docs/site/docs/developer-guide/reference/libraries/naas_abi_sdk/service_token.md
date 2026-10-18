# service_token

## What it is
Utilities for creating and caching service JWTs used by ABI modules when calling engine services or other modules over NATS. Tokens are signed locally using HMAC-SHA256 (HS256) and a module key (`ABI_MODULE_KEY`), with optional audience binding.

## Public API

- `TTL_SECONDS: int`
  - Default token TTL for unbound tokens (3600 seconds).

- `BOUND_TTL_SECONDS: int`
  - Max TTL for audience-bound tokens (300 seconds).

- `BOUND_REUSE_SECONDS: int`
  - Reuse window for cached bound tokens (30 seconds).

- `MAX_AUDIENCES: int`
  - Maximum cached audiences before clearing the cache (1024).

- `MODULE_KEY_ID: str`
  - JWT header `kid` value used for module tokens (`"module"`).

### `class TokenCache`
Caches tokens by audience (`None` for unbound), reissuing only within a configured reuse window.

- `TokenCache(sign, *, ttl_seconds=TTL_SECONDS, clock=time.time)`
  - `sign(audience, issued_at, ttl_seconds) -> str` is a callback used to create tokens.

- `unbound() -> str`
  - Returns an unbound token, cached/reused for half of its TTL.

- `bound(audience: str) -> str`
  - Returns a token bound to `audience` (must be non-empty), cached/reused for `min(BOUND_REUSE_SECONDS, ttl/2)`.

### `class ModuleToken`
Callable token source for a given module identity, signing fresh JWTs with a module key.

- `ModuleToken(identity: str, key: str, *, ttl_seconds=TTL_SECONDS, clock=time.time)`
  - Validates `identity` and `key` are non-empty.
  - Uses an internal `TokenCache`.

- `__call__() -> str`
  - Returns an unbound token (for engine services).

- `for_audience(audience: str) -> str`
  - Returns a token bound to a specific module instance (sets JWT `aud` claim).

### `token_from_env(env: Mapping[str, str], identity: str) -> str | ModuleToken`
Creates a token source from environment-like mappings:

- If `env["ABI_MODULE_KEY"]` is set (non-empty): returns `ModuleToken(identity, key)`.
- Else if `env["ABI_SERVICE_TOKEN"]` is set (non-empty): returns that issued token string as-is.
- Else: raises `RuntimeError` with instructions.

## Configuration/Dependencies
- Environment variables (via `token_from_env`):
  - `ABI_MODULE_KEY`: module key used to sign fresh tokens (preferred when present).
  - `ABI_SERVICE_TOKEN`: pre-issued token string (used only if no module key is available).
- Standard library only: `base64`, `hashlib`, `hmac`, `json`, `time`.

## Usage

```python
import os
from naas_abi_sdk.service_token import token_from_env

identity = "my-module-id"
token_source = token_from_env(os.environ, identity)

# Unbound token (engine services)
token = token_source() if callable(token_source) else token_source

# Bound token (calls to another module instance)
if callable(token_source):
    bound = token_source.for_audience("target-instance-id")
```

## Caveats
- `ModuleToken.for_audience(audience)` requires a non-empty string; otherwise `ValueError` is raised.
- `token_from_env` may return either a `ModuleToken` (callable) or a raw token `str`; callers must handle both.
- Cache is capped at `MAX_AUDIENCES`; when exceeded, the cache is cleared (tokens may rotate abruptly).
