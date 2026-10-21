# secrets__schema

## What it is
- A small schema module defining immutable dataclasses and error types for a "secrets" service API.
- Includes input/output payload structures and typed exceptions.

## Public API
### Types
- `SecretCategory`: `Literal["api_keys", "credentials", "tokens", "other"]`
  - Allowed categories for a secret at creation time.

### Dataclasses (schemas)
- `SecretCreateInput`
  - Fields: `workspace_id`, `key`, `value`, `description=""`, `category="other"`
  - Purpose: payload for creating a secret.

- `SecretUpdateInput`
  - Fields: `value: str | None = None`, `description: str | None = None`
  - Purpose: partial update payload for an existing secret.

- `SecretBulkImportInput`
  - Fields: `workspace_id`, `env_content`
  - Purpose: payload for importing secrets from environment-style content.

- `SecretOutput`
  - Fields: `id`, `workspace_id`, `key`, `masked_value`, `description`, `category`, `created_at: datetime | None`, `updated_at: datetime | None`
  - Purpose: output model representing a secret as returned by the service.

- `SecretBulkImportResult`
  - Fields: `imported`, `updated`
  - Purpose: output model for bulk import summary.

### Exceptions
- `SecretAlreadyExistsError(ValueError)`
  - Field: `key`
  - Purpose: signals an attempted create with a duplicate secret key.

- `SecretNotFoundError(ValueError)`
  - Field: `secret_id`
  - Purpose: signals a lookup/update/delete on a missing secret.

## Configuration/Dependencies
- Python 3.10+ (uses `str | None` union syntax).
- Standard library dependencies:
  - `dataclasses.dataclass`
  - `datetime.datetime`
  - `typing.Literal`

## Usage
```python
from datetime import datetime
from naas_abi.apps.nexus.apps.api.app.services.secrets.secrets__schema import (
    SecretCreateInput,
    SecretUpdateInput,
    SecretOutput,
    SecretAlreadyExistsError,
)

create_in = SecretCreateInput(
    workspace_id="ws_123",
    key="OPENAI_API_KEY",
    value="super-secret",
    description="Key used by the LLM integration",
    category="api_keys",
)

update_in = SecretUpdateInput(description="Rotated on 2026-04-23")

secret_out = SecretOutput(
    id="sec_1",
    workspace_id=create_in.workspace_id,
    key=create_in.key,
    masked_value="****",
    description=create_in.description,
    category=create_in.category,
    created_at=datetime.utcnow(),
    updated_at=None,
)

# Example exception usage
raise SecretAlreadyExistsError(key=create_in.key)
```

## Caveats
- `SecretCreateInput`, `SecretUpdateInput`, `SecretBulkImportInput`, `SecretOutput`, and `SecretBulkImportResult` are dataclasses only; no validation or parsing is implemented in this module.
- `SecretOutput.category` is typed as `str` (not `SecretCategory`).
