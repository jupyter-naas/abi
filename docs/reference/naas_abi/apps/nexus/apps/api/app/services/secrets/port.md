# SecretsPersistencePort

## What it is
- Defines the persistence interface (“port”) for storing and retrieving secrets.
- Provides a `SecretRecord` data model used by the persistence layer.
- All operations are `async` and intended to be implemented by an infrastructure adapter (e.g., DB repository).

## Public API

### `SecretRecord` (dataclass)
Represents a persisted secret.

Fields:
- `id: str`
- `workspace_id: str`
- `key: str`
- `encrypted_value: str`
- `description: str`
- `category: str`
- `created_at: datetime | None = None`
- `updated_at: datetime | None = None`

### `SecretsPersistencePort` (abstract base class)
Async interface that persistence implementations must provide:

- `async list_by_workspace(workspace_id: str) -> list[SecretRecord]`
  - List all secrets for a workspace.
- `async get_by_workspace_key(workspace_id: str, key: str) -> SecretRecord | None`
  - Fetch a secret by `(workspace_id, key)`.
- `async get_by_id(secret_id: str) -> SecretRecord | None`
  - Fetch a secret by its ID.
- `async create(record: SecretRecord) -> SecretRecord`
  - Create a new secret record and return the created record.
- `async save(record: SecretRecord) -> None`
  - Persist updates to an existing record.
- `async delete(secret_id: str) -> bool`
  - Delete a secret by ID; returns whether deletion occurred.
- `async commit() -> None`
  - Commit pending persistence operations (transaction boundary).

## Configuration/Dependencies
- Standard library only:
  - `dataclasses.dataclass`
  - `abc.ABC`, `abc.abstractmethod`
  - `datetime.datetime`
- Requires an async-capable runtime (e.g., `asyncio`) in callers/implementations.

## Usage

Minimal example implementing an in-memory adapter:

```python
import asyncio
from datetime import datetime

from naas_abi.apps.nexus.apps.api.app.services.secrets.port import (
    SecretRecord,
    SecretsPersistencePort,
)

class InMemorySecrets(SecretsPersistencePort):
    def __init__(self):
        self._by_id = {}

    async def list_by_workspace(self, workspace_id: str):
        return [r for r in self._by_id.values() if r.workspace_id == workspace_id]

    async def get_by_workspace_key(self, workspace_id: str, key: str):
        for r in self._by_id.values():
            if r.workspace_id == workspace_id and r.key == key:
                return r
        return None

    async def get_by_id(self, secret_id: str):
        return self._by_id.get(secret_id)

    async def create(self, record: SecretRecord):
        self._by_id[record.id] = record
        return record

    async def save(self, record: SecretRecord):
        self._by_id[record.id] = record

    async def delete(self, secret_id: str):
        return self._by_id.pop(secret_id, None) is not None

    async def commit(self):
        return None

async def main():
    store = InMemorySecrets()
    rec = SecretRecord(
        id="s1",
        workspace_id="w1",
        key="API_KEY",
        encrypted_value="...",
        description="Service key",
        category="integration",
        created_at=datetime.utcnow(),
    )
    await store.create(rec)
    await store.commit()
    print(await store.get_by_workspace_key("w1", "API_KEY"))

asyncio.run(main())
```

## Caveats
- This module defines an interface only; it does not implement encryption, storage, validation, or transaction semantics.
- All methods are abstract and must be implemented; calling them directly raises `NotImplementedError`.
