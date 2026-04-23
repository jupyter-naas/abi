# `secrets` (backward-compatible secrets endpoint export)

## What it is
- A compatibility shim module that re-exports the FastAPI secrets router and related schema types.
- Provides thin wrapper functions around secrets crypto/utilities and an async helper to resolve a secret value via the secrets service backed by Postgres.

## Public API
### Re-exports
- `router`: FastAPI router for secrets endpoints (imported from the primary FastAPI adapter).
- `SecretCreate`: request model/schema for creating a secret.
- `SecretUpdate`: request model/schema for updating a secret.
- `SecretResponse`: response model/schema for secret operations.
- `SecretBulkImport`: request model/schema for bulk import.

### Functions
- `deprecated_encrypt(value: str) -> str`
  - Encrypts a plaintext secret value using `encrypt_secret_value`.
- `_encrypt(value: str) -> str`
  - Backward-compatible alias for `deprecated_encrypt`.
- `_decrypt(encrypted_value: str) -> str`
  - Decrypts an encrypted secret value using `decrypt_secret_value`.
- `_try_decrypt(encrypted_value: str) -> str | None`
  - Attempts to decrypt using `try_decrypt_secret_value`; returns `None` on failure.
- `_mask_value(value: str) -> str`
  - Masks a secret value using `mask_secret_value`.
- `_infer_category(key: str) -> str`
  - Infers a secret category from a key using `infer_secret_category`.
- `resolve_secret_async(db: AsyncSession, workspace_id: str, key: str) -> str | None`
  - Resolves (fetches and decrypts as needed) a secret value for a workspace/key using:
    - `SecretsService`
    - `SecretsSecondaryAdapterPostgres(db=db)`
    - A system `RequestContext` with `TokenData(user_id="system", scopes={"*"}, is_authenticated=True)`

## Configuration/Dependencies
- Requires an SQLAlchemy async database session:
  - `sqlalchemy.ext.asyncio.AsyncSession`
- Depends on internal services/adapters:
  - `SecretsService`
  - `SecretsSecondaryAdapterPostgres`
  - IAM context models: `RequestContext`, `TokenData`
- Crypto/utilities:
  - `encrypt_secret_value`, `decrypt_secret_value`, `try_decrypt_secret_value`
  - `mask_secret_value`, `infer_secret_category`

## Usage
### Include the router in a FastAPI app
```python
from fastapi import FastAPI
from naas_abi.apps.nexus.apps.api.app.api.endpoints import secrets

app = FastAPI()
app.include_router(secrets.router)
```

### Resolve a secret value (async)
```python
from sqlalchemy.ext.asyncio import AsyncSession
from naas_abi.apps.nexus.apps.api.app.api.endpoints.secrets import resolve_secret_async

async def get_api_key(db: AsyncSession, workspace_id: str) -> str | None:
    return await resolve_secret_async(db, workspace_id=workspace_id, key="API_KEY")
```

## Caveats
- `resolve_secret_async` uses a hardcoded system context (`user_id="system"`, scopes `{"*"}`); authorization behavior is delegated to the underlying service.
- This module is explicitly “backward-compatible”; functions like `_encrypt`/`deprecated_encrypt` are aliases rather than new implementations.
