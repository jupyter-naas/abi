# SecretsService

## What it is
A service layer for managing workspace secrets:
- Enforces IAM scope and workspace access checks.
- Persists secrets via a `SecretsPersistencePort` adapter.
- Encrypts secret values at rest and returns masked values in outputs.
- Supports CRUD, bulk `.env` import, and resolving decrypted secret values.

## Public API

### Helper functions
- `mask_secret_value(value: str) -> str`
  - Returns a masked representation (`"****"` for short values; otherwise `prefix****suffix`).
- `infer_secret_category(key: str) -> str`
  - Infers a category from a key name: `api_keys`, `tokens`, `credentials`, or `other`.

### Class: `SecretsService`
Constructor:
- `SecretsService(adapter: SecretsPersistencePort, iam_service: IAMService | None = None, workspace_access_checker: Callable[[str, str], Awaitable[str]] | None = None)`
  - `adapter`: persistence implementation.
  - `iam_service`: optional IAM service used by authorization helpers.
  - `workspace_access_checker`: optional async override for workspace access control.

Static methods (crypto):
- `encrypt(value: str) -> str`
- `decrypt(encrypted_value: str) -> str`
- `try_decrypt(encrypted_value: str) -> str | None`

Instance methods:
- `to_output(record: SecretRecord) -> SecretOutput`
  - Converts a persistence record to an API output with masked value.
- `list_secrets(context: RequestContext, workspace_id: str) -> list[SecretOutput]`
  - Lists secrets for a workspace (masked).
- `create_secret(context: RequestContext, secret: SecretCreateInput, now: datetime) -> SecretOutput`
  - Creates a secret (fails if key already exists in workspace).
- `update_secret(context: RequestContext, secret_id: str, update: SecretUpdateInput, now: datetime) -> SecretOutput`
  - Updates encrypted value and/or description.
- `delete_secret(context: RequestContext, secret_id: str) -> None`
  - Deletes a secret by id.
- `bulk_import(context: RequestContext, data: SecretBulkImportInput, now: datetime) -> SecretBulkImportResult`
  - Imports key/value pairs from `env_content`; updates existing keys, creates missing ones.
- `resolve_secret_value(context: RequestContext, workspace_id: str, key: str) -> str | None`
  - Returns the decrypted value for a given key, or `None` if not found (no masking).

## Configuration/Dependencies
- Persistence:
  - Requires an implementation of `SecretsPersistencePort` with methods used here:
    - `list_by_workspace`, `get_by_workspace_key`, `get_by_id`, `create`, `save`, `delete`, `commit`.
  - Uses `SecretRecord` for storage objects.
- Authorization:
  - Scope checks via `ensure_scope(...)` with required scopes:
    - `secret.read`, `secret.create`, `secret.update`, `secret.delete`
  - Workspace access checks:
    - Either via injected `workspace_access_checker(actor_user_id, workspace_id)`
    - Or fallback to `ensure_workspace_access(...)` (requires `workspace.read` scope).
- Crypto:
  - Uses `encrypt_secret_value`, `decrypt_secret_value`, `try_decrypt_secret_value`.

## Usage

```python
import asyncio
from datetime import datetime, timezone

# Imports depend on your project layout
from naas_abi.apps.nexus.apps.api.app.services.secrets.service import SecretsService
from naas_abi.apps.nexus.apps.api.app.services.secrets.secrets__schema import SecretCreateInput
from naas_abi.apps.nexus.apps.api.app.services.iam.port import RequestContext

async def main(adapter):
    service = SecretsService(adapter=adapter)

    ctx = RequestContext(actor_user_id="user_123")  # other fields may exist in your implementation
    now = datetime.now(timezone.utc)

    out = await service.create_secret(
        context=ctx,
        secret=SecretCreateInput(
            workspace_id="ws_1",
            key="MY_API_KEY",
            value="abcd1234efgh5678",
            description="Example key",
            category=None,
        ),
        now=now,
    )
    print(out.key, out.masked_value)

    value = await service.resolve_secret_value(ctx, "ws_1", "MY_API_KEY")
    print(value)  # decrypted value (or None if not found)

# asyncio.run(main(adapter))
```

## Caveats
- `list_secrets()` and `to_output()` attempt decryption; if decryption fails, the masked value becomes `"****"`.
- `bulk_import()` parsing is minimal:
  - Skips empty lines, comments (`#`), and lines without `=`.
  - Strips optional surrounding single/double quotes from values.
  - Does not support advanced dotenv syntax (exports, escapes, multiline).
- `create_secret()` checks uniqueness by `(workspace_id, key)`; duplicates raise `SecretAlreadyExistsError`.
- `delete_secret()` may raise `SecretNotFoundError` both when the record is missing and when deletion reports failure.
