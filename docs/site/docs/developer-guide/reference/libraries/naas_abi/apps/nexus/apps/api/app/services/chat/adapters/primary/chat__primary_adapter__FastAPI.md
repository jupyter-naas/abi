# ChatFastAPIPrimaryAdapter

## What it is
- A FastAPI **primary adapter** exposing HTTP endpoints for the chat domain:
  - conversation CRUD
  - chat completion (sync + streaming)
  - file ingestion job creation + status polling
  - conversation export
  - Ollama runtime status check
- Built around a module-level `APIRouter` (`router`) that is attached to `ChatFastAPIPrimaryAdapter.router`.

## Public API

### Class
- `ChatFastAPIPrimaryAdapter`
  - `__init__()`: sets `self.router` to the module-level `router`.

### FastAPI routes (mounted on `router`)
- `GET /conversations`
  - List conversations in a workspace (`workspace_id`, `limit`, `offset`).
- `POST /conversations`
  - Create a conversation from `ConversationCreate`.
- `GET /conversations/{conversation_id}`
  - Fetch a conversation; optionally include messages (`include_messages`).
- `PATCH /conversations/{conversation_id}`
  - Update conversation fields from an untyped `dict` (`title`, `pinned`, `archived` supported).
- `DELETE /conversations/{conversation_id}`
  - Delete a conversation and its messages.

- `POST /complete`
  - Execute a non-streaming chat completion from `ChatRequest`, returning `ChatResponse`.
  - Maps `ValueError -> 400`, `PermissionError -> 404`.

- `POST /stream`
  - Execute a streaming chat completion from `ChatRequest` (delegates to `stream_chat_response`).

- `POST /conversations/{conversation_id}/files/upload`
  - Upload a file (`multipart/form-data`) and create an ingestion job.
  - Form fields: `workspace_id` (optional), `embedding_model` (default `"text-embedding-3-small"`), `embedding_dimension` (default `1536`).
  - If the conversation does not exist and `workspace_id` is provided, it creates a new conversation with:
    - title: `"New Conversation"`, agent: `"aia"`, and the given `conversation_id`.
  - Stores the file under `my-drive/{user_id}/uploads/{filename}` via object storage.
  - Publishes an ingestion job via `publish_chat_ingestion_job`.

- `POST /conversations/{conversation_id}/files/ingest`
  - Create an ingestion job for an existing “my drive” file path (`ChatIngestMyDriveFileRequest`).
  - Same conversation auto-create behavior as upload (uses `payload.workspace_id`).
  - Publishes an ingestion job via `publish_chat_ingestion_job`.

- `GET /ingestion-jobs/{job_id}`
  - Get ingestion job status (`ChatIngestionJobStatusResponse`).

- `GET /conversations/{conversation_id}/export`
  - Export a conversation in `txt|json|md` (`format` query param; default `txt`).
  - Returns a response built by `export_conversation_as_response`.

- `GET /ollama/status`
  - Check Ollama endpoint status (`endpoint` query param; default `http://localhost:11434`).

### Helper (module-private)
- `_to_ingestion_response(result) -> ChatFileIngestionResponse`
  - Converts a result object into `ChatFileIngestionResponse`.
  - Note: not used by the routes in this module.

## Configuration/Dependencies
- **Authentication/authorization**
  - All endpoints depend on `get_current_user_required`.
  - Workspace access is enforced with `require_workspace_access(user_id, workspace_id)` when a workspace is known.

- **Service dependencies**
  - `ChatService` via `Depends(get_chat_service)`.
  - `AsyncSession` via `Depends(get_db)`.
  - `ObjectStorageService` via `Depends(get_object_storage_service)` (upload endpoint).
  - Registry binding via `bind_registry(db)` for `/complete` and `/conversations/{id}/export`.

- **Background job publication**
  - Ingestion jobs are published via `publish_chat_ingestion_job` executed in a thread: `asyncio.to_thread(...)`.

- **Time handling**
  - Uses `datetime.now(UTC).replace(tzinfo=None)` in several places (naive timestamps derived from UTC).

## Usage

### Mount the router in a FastAPI app
```python
from fastapi import FastAPI
from naas_abi.apps.nexus.apps.api.app.services.chat.adapters.primary.chat__primary_adapter__FastAPI import (
    ChatFastAPIPrimaryAdapter,
)

app = FastAPI()
adapter = ChatFastAPIPrimaryAdapter()
app.include_router(adapter.router, prefix="/chat", tags=["chat"])
```

## Caveats
- **Ingestion job race condition guard**: ingestion endpoints explicitly `await db.commit()` *before* publishing to the worker queue to ensure the job row is visible to the worker.
- **Conversation auto-create**: file upload/ingest endpoints will create a new conversation if it doesn’t exist *only* when `workspace_id` is provided (otherwise returns 404).
- **Uploads path and name**:
  - Stored under `my-drive/{user_id}/uploads`.
  - Filename is sanitized only by stripping path separators (`/` and `\`); collisions are not handled here.
- **`PATCH` payload is untyped**: `update_conversation` accepts a raw `dict`; only `title`, `pinned`, `archived` keys are read.
