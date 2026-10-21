# chat_ingestion_worker

## What it is
A small worker/consumer module that:
- Publishes chat file ingestion jobs to a message bus topic.
- Consumes those jobs and processes them asynchronously.
- Updates ingestion job status in the database.
- Broadcasts ingestion progress/status events to workspace WebSocket clients.
- Runs the heavy ingestion work in a thread executor to avoid blocking the FastAPI/uvicorn event loop.

## Public API

### Constants
- `CHAT_INGESTION_TOPIC = "chat_ingestion"`  
  Message bus topic name used for ingestion jobs.
- `CHAT_INGESTION_ROUTING_KEY = "chat.file.ingest"`  
  Routing key used for ingestion jobs.

### Functions
- `publish_chat_ingestion_job(payload: dict[str, Any]) -> None`  
  Publishes a JSON-encoded job payload to the message bus (`topic_publish`).

- `process_chat_ingestion_job(payload: dict[str, Any]) -> None` *(async)*  
  Processes an ingestion job:
  - Validates `job_id`.
  - Retries up to 5 times to find/update the job row (handles replication lag).
  - Updates job status through phases: `hashing` → `cache_lookup` → progress callbacks → `ready` (or `failed`).
  - Emits WebSocket events (`chat.ingestion.status`) to the job’s workspace.
  - Runs `ChatFileIngestionService.ingest_from_path(...)` in an executor thread and reports progress.

- `start_chat_ingestion_consumer(app: fastapi.FastAPI) -> None`  
  Starts a message bus consumer once per FastAPI app instance. Must be called while an event loop is running (e.g., during FastAPI startup). The consumer:
  - Decodes messages as JSON payloads.
  - Schedules `process_chat_ingestion_job(...)` onto the existing uvicorn loop.
  - Blocks the bus/consumer thread until the job completes (`future.result()`).

## Configuration/Dependencies
This module relies on application infrastructure provided elsewhere:

- `naas_abi.ABIModule.get_instance()` with:
  - `module.engine.services.bus.topic_publish(...)`
  - `module.engine.services.bus.topic_consume(...)`
  - `module.engine.services.object_storage`
  - `module.engine.services.vector_store`
  - `module.engine.services.cache`

- Database:
  - `AsyncSessionLocal` (async SQLAlchemy session factory)
  - `ChatIngestionJobService` for status updates and job lookup

- Ingestion:
  - `ChatFileIngestionService.ingest_from_path(...)`
  - `ChatFileIngestionError` for expected ingestion failures

- WebSocket:
  - `WebSocketService.broadcast_to_workspace(...)` emitting event `chat.ingestion.status`

Payload fields used by `process_chat_ingestion_job`:
- Required (effectively):
  - `job_id`
  - `user_id`
  - `conversation_id`
  - `source_path`
- Optional:
  - `embedding_model` (defaults to `"text-embedding-3-small"`)
  - `embedding_dimension` (defaults to `1536`)

## Usage

### Start the consumer on FastAPI startup
```python
from fastapi import FastAPI
from naas_abi.apps.nexus.apps.api.app.services.chat.chat_ingestion_worker import (
    start_chat_ingestion_consumer,
)

app = FastAPI()

@app.on_event("startup")
async def startup():
    start_chat_ingestion_consumer(app)
```

### Publish an ingestion job
```python
from naas_abi.apps.nexus.apps.api.app.services.chat.chat_ingestion_worker import (
    publish_chat_ingestion_job,
)

publish_chat_ingestion_job({
    "job_id": "123",
    "user_id": "u1",
    "conversation_id": "c1",
    "source_path": "object-storage://bucket/path/to/file.pdf",
    # optional:
    "embedding_model": "text-embedding-3-small",
    "embedding_dimension": 1536,
})
```

## Caveats
- `start_chat_ingestion_consumer()` must be invoked from within a running event loop (e.g., FastAPI startup). It uses `asyncio.get_running_loop()` and schedules work onto that loop to avoid conflicts with async DB connections.
- The bus consumer callback blocks its consumer thread until each job completes (`future.result()`), so throughput depends on how the bus service provisions consumer threads.
- If `job_id` is missing, the job is not processed and an error is logged.
- WebSocket event emission failures are caught and logged; ingestion continues even if WebSocket broadcasting fails.
