# ChatIngestionJobService

## What it is
Async service layer for creating, retrieving, and updating chat ingestion job rows in the database, returning a lightweight `ChatIngestionJobRecord` dataclass representation.

## Public API
- `ChatIngestionJobRecord` (dataclass)
  - Immutable-style record of a chat ingestion job (IDs, source info, embedding info, status/progress, error fields, timestamps, attempt counters).
- `ChatIngestionJobService(db: AsyncSession)`
  - Service bound to a SQLAlchemy `AsyncSession`.
  - Methods:
    - `create_job(job_id, conversation_id, workspace_id, user_id, source_type, source_path, embedding_model, embedding_dimension, status="queued") -> ChatIngestionJobRecord`
      - Inserts a new job row and flushes it.
    - `get_job_for_user(job_id, user_id) -> ChatIngestionJobRecord | None`
      - Fetches a job by `id` scoped to a given `user_id`.
    - `get_job(job_id) -> ChatIngestionJobRecord | None`
      - Fetches a job by `id` without user scoping.
    - `update_status(job_id, status, *, progress=None, cache_hit=None, file_sha256=None, collection_name=None, chunks_count=None, error_code=None, error_message=None, started=False, finished=False, increment_attempt=False) -> ChatIngestionJobRecord | None`
      - Updates status and optional fields, sets timestamps, optionally increments attempt, flushes, and returns the updated record.

## Configuration/Dependencies
- Requires an initialized SQLAlchemy `AsyncSession`.
- Depends on:
  - `ChatIngestionJobModel` (ORM model) from `naas_abi.apps.nexus.apps.api.app.models`
  - SQLAlchemy async execution (`select`, `AsyncSession`)
  - `UTC` timezone object from `naas_abi.apps.nexus.apps.api.app.core.datetime_compat`
- Timestamp behavior:
  - Uses current UTC time but stores it as a **naive** `datetime` (timezone removed) for `updated_at`, and optionally `started_at`/`finished_at`.

## Usage
```python
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from naas_abi.apps.nexus.apps.api.app.services.chat.chat_ingestion_jobs import (
    ChatIngestionJobService,
)

async def run(db: AsyncSession):
    svc = ChatIngestionJobService(db)

    job = await svc.create_job(
        job_id="job_1",
        conversation_id="conv_1",
        workspace_id="ws_1",
        user_id="user_1",
        source_type="file",
        source_path="/tmp/doc.pdf",
        embedding_model="text-embedding-3-large",
        embedding_dimension=3072,
    )

    job = await svc.update_status(
        job_id=job.id,
        status="running",
        progress=10,
        started=True,
        increment_attempt=True,
    )

    same_job = await svc.get_job_for_user(job.id, user_id="user_1")
    return same_job

# asyncio.run(run(db))  # db must be an active AsyncSession
```

## Caveats
- `update_status(..., started=True)` only sets `started_at` if it is currently `None` (first start wins).
- `finished=True` always sets `finished_at` to “now”.
- `update_status` updates `updated_at` on every call, using a **naive** UTC timestamp.
- Methods call `flush()` but do not `commit()`; transaction boundaries are managed by the caller/session scope.
