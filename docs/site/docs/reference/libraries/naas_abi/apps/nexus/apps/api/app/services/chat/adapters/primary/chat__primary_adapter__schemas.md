# chat__primary_adapter__schemas

## What it is
Pydantic schemas and small mapping helpers used by the Chat API primary adapter. It defines request/response models for conversations, messages, provider configuration, and file ingestion, plus utilities to convert DB rows into API models.

## Public API

### Constants
- `VALID_PROVIDER_TYPES: list[str]`
  - Allowed provider `type` values for `ProviderConfigRequest`.
  - Built from `get_all_provider_names()` plus `"custom"` and `"abi"`.

### Models (Pydantic `BaseModel`)
- `Message`
  - Chat message representation.
  - Fields: `id`, `conversation_id`, `role` (`"user"|"assistant"|"system"`), `content`, `agent`, `metadata`, `created_at`.

- `Conversation`
  - Conversation container with messages.
  - Fields: `id`, `workspace_id`, `user_id`, `title`, `agent`, `messages`, `created_at`, `updated_at`.

- `ConversationCreate`
  - Input payload to create a conversation.
  - Fields (validated): `workspace_id`, `title`, `agent`.

- `ProviderConfigRequest`
  - Provider configuration included in chat requests.
  - Fields: `id`, `name`, `type`, `enabled`, `endpoint`, `api_key`, `account_id`, `model`.
  - Validation: `model_post_init()` raises `ValueError` if `type` not in `VALID_PROVIDER_TYPES`.

- `MessageRequest`
  - Structured message input for chat.
  - Fields: `role`, `content` (max 100_000), `images` (max 10), `agent`.

- `ChatRequest`
  - Main chat request payload.
  - Fields: `conversation_id`, `workspace_id`, `message`, `images` (max 10), `messages` (max 200), `agent`, `provider`, `context`, `system_prompt` (max 50_000), `search_enabled`.

- `ChatResponse`
  - Chat response payload.
  - Fields: `conversation_id`, `message` (`Message`), `context_used`, `provider_used`.

- `ChatIngestMyDriveFileRequest`
  - Request to ingest a file into chat context.
  - Fields: `source_path`, `workspace_id`, `embedding_model`, `embedding_dimension` (8..4096).

- `ChatFileIngestionResponse`
  - Response describing ingestion result.
  - Fields: `job_id`, `status`, `conversation_id`, `source_path`, `collection_name`, `file_sha256`, `cache_hit`, `chunks_count`, `statuses`, `embedding_model`, `embedding_dimension`.

- `ChatIngestionJobStatusResponse`
  - Job status details for ingestion.
  - Fields: `job_id`, `conversation_id`, `workspace_id`, `source_path`, `status`, `progress`, `cache_hit`, `file_sha256`, `collection_name`, `chunks_count`, `error_code`, `error_message`, `attempt`, `max_attempts`, `created_at`, `updated_at`, `started_at`, `finished_at`.

### Functions
- `to_conversation(row: Any, messages: list[Message] | None = None) -> Conversation`
  - Maps a DB-like `row` (attributes: `id`, `workspace_id`, `user_id`, `title`, `agent`, `created_at`, `updated_at`) into a `Conversation`.
  - Uses provided `messages` or an empty list.

- `to_message(row: Any) -> Message`
  - Maps a DB-like `row` (attributes: `id`, `conversation_id`, `role`, `content`, `agent`, `metadata_`, `created_at`) into a `Message`.
  - If `row.metadata_` is set, it is parsed with `json.loads`.

## Configuration/Dependencies
- Depends on:
  - `pydantic.BaseModel`, `pydantic.Field`
  - `naas_abi.apps.nexus.apps.api.app.services.model_registry.get_all_provider_names`
  - Standard library: `json`, `datetime`, typing (`Any`, `Literal`)
- Provider type validation uses `VALID_PROVIDER_TYPES` computed at import time.

## Usage

```python
from datetime import datetime
from naas_abi.apps.nexus.apps.api.app.services.chat.adapters.primary.chat__primary_adapter__schemas import (
    ChatRequest, ProviderConfigRequest, to_message
)

# Build a request
req = ChatRequest(
    workspace_id="ws_123",
    message="Hello",
    provider=ProviderConfigRequest(
        id="prov_1",
        name="MyProvider",
        type="custom",   # must be in VALID_PROVIDER_TYPES
        enabled=True,
        model="gpt-4o-mini",
    ),
)

# Map a DB-like row to a Message
class Row:
    id = "msg_1"
    conversation_id = "conv_1"
    role = "user"
    content = "Hi"
    agent = None
    metadata_ = '{"foo":"bar"}'
    created_at = datetime.utcnow()

msg = to_message(Row)
```

## Caveats
- `ProviderConfigRequest.type` is validated in `model_post_init`; invalid types raise `ValueError`.
- `to_message()` assumes `row.metadata_` is valid JSON when present; invalid JSON will raise a `json.JSONDecodeError`.
- `images` fields are `list[str]` with a maximum length of 10; `ChatRequest.messages` max length is 200; content/system prompt sizes are capped by `Field` constraints.
