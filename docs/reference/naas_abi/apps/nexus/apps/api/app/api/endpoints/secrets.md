# `secrets` (Secrets API endpoints)

## What it is
Server-side secret storage endpoints for a FastAPI app.

- Secrets are stored per workspace.
- Only workspace **admins/owners** can create/update/delete/import secrets.
- Secret values are **encrypted at rest** using Fernet (key derived from `settings.secret_key`).
- Secret values are **never returned in full**; responses contain a masked value only.
- Uses **async SQLAlchemy ORM** (`AsyncSession`).

## Public API

### FastAPI router
- `router: APIRouter`
  - Configured with `dependencies=[Depends(get_current_user_required)]` (authentication required for all routes on this router).

### Pydantic schemas
- `SecretCreate`
  - Input for creating a secret: `workspace_id`, `key`, `value`, optional `description`, `category`.
- `SecretUpdate`
  - Input for updating: optional `value`, optional `description`.
- `SecretResponse`
  - Output shape returned by list/create/update: includes `masked_value` (not the plaintext).
- `SecretBulkImport`
  - Input for `.env`-style bulk import: `workspace_id`, `env_content`.

### Endpoints
- `GET /{workspace_id}` → `list_secrets(...) -> list[SecretResponse]`
  - Lists secrets for a workspace (masked values).
  - Requires workspace access via `require_workspace_access`.

- `POST /` → `create_secret(secret: SecretCreate) -> SecretResponse`
  - Creates a new secret.
  - Enforces uniqueness on `(workspace_id, key)`.
  - Requires role `admin` or `owner`.

- `PUT /{secret_id}` → `update_secret(secret_id: str, update: SecretUpdate) -> SecretResponse`
  - Updates secret value and/or description.
  - Requires role `admin` or `owner`.

- `DELETE /{secret_id}` → `delete_secret(secret_id: str) -> dict`
  - Deletes a secret.
  - Requires role `admin` or `owner`.
  - Returns `{"status": "deleted"}`.

- `POST /import` → `bulk_import_secrets(data: SecretBulkImport) -> dict`
  - Imports secrets from `.env`-formatted content.
  - Existing keys are updated; new keys are inserted.
  - Returns `{"imported": int, "updated": int}`.
  - Requires role `admin` or `owner`.

- `GET /test-public` → `test_public_endpoint() -> dict`
  - Returns `{"message": "Public secrets endpoint working!"}`.
  - Note: despite the docstring, this router still has an auth dependency at the router level.

### Internal helper (non-endpoint)
- `resolve_secret_async(db: AsyncSession, workspace_id: str, key: str) -> str | None`
  - Fetches a secret by `(workspace_id, key)` and returns the **decrypted** value (or `None`).
  - Intended for internal use.

## Configuration/Dependencies
- `settings.secret_key`
  - Used to derive the Fernet key: `sha256(secret_key)` then `urlsafe_b64encode`.
- Authentication/authorization:
  - `get_current_user_required` (FastAPI dependency)
  - `require_workspace_access(user_id, workspace_id)` which returns a role string (checked against `"admin"`/`"owner"` for management operations)
- Database:
  - `get_db` provides a `sqlalchemy.ext.asyncio.AsyncSession`
  - `SecretModel` ORM model with fields used here: `id`, `workspace_id`, `key`, `encrypted_value`, `description`, `category`, `created_at`, `updated_at`
- Crypto:
  - `cryptography.fernet.Fernet` for encryption/decryption
- Time:
  - `datetime.now(UTC).replace(tzinfo=None)` used for `created_at`/`updated_at` timestamps

## Usage

### Call the endpoints (example with `requests`)
```python
import requests

BASE = "http://localhost:8000"  # adjust
TOKEN = "your-bearer-token"

headers = {"Authorization": f"Bearer {TOKEN}"}

# Create a secret
resp = requests.post(
    f"{BASE}/secrets",
    headers=headers,
    json={
        "workspace_id": "ws_123",
        "key": "MY_API_KEY",
        "value": "abcd-1234-efgh-5678",
        "description": "Used for vendor X",
        "category": "api_keys",
    },
)
resp.raise_for_status()
print(resp.json())  # contains masked_value, not the real value

# List secrets (masked)
resp = requests.get(f"{BASE}/secrets/ws_123", headers=headers)
resp.raise_for_status()
print(resp.json())
```

### Resolve a secret internally (async)
```python
from sqlalchemy.ext.asyncio import AsyncSession
from naas_abi.apps.nexus.apps.api.app.api.endpoints.secrets import resolve_secret_async

async def use_secret(db: AsyncSession):
    value = await resolve_secret_async(db, workspace_id="ws_123", key="MY_API_KEY")
    if value is None:
        raise RuntimeError("Secret not found or decrypt failed")
    return value
```

## Caveats
- Secret values are only returned masked; there is no endpoint that returns the full plaintext.
- Encryption key is derived from `settings.secret_key`; changing it will prevent decrypting previously stored secrets (decrypt will fail and masking falls back to `"****"`).
- `DELETE` endpoint does not call `db.commit()` after `db.delete(row)` in this code; persistence may depend on session/transaction handling elsewhere.
- The router enforces `get_current_user_required` globally; `/test-public` is not actually public unless mounted without that dependency.
