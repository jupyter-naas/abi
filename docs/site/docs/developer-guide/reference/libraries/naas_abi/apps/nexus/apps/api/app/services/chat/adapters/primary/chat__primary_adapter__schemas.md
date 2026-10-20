# chat__primary_adapter__schemas

## What it is
Pydantic schemas and small mapping helpers used by the Chat API primary adapter. It defines request/response models for chat, conversation/message representations, provider configuration, export payloads, and file ingestion/job status.

## Public API

### Constants
- `VALID_PROVIDER_TYPES: list[str]`
  - Allowed values for `ProviderConfigRequest.type`.
  - Computed at import time from `list_catalog_providers()` provider ids, plus `"custom"`, `"abi"`, and `"remote"`.

### Functions
- `_valid_provider_types() -> list[str]`
  - Builds the list of accepted provider types (catalog provider ids + internal aliases).
- `to_conversation(row: Any, messages: list[Message] | None = None) -> Conversation`
  - Maps a DB-like `row` into a `Conversation`.
  - Reads: `id`, `workspace_id`, `user_id`, `title`, `agent`, `created_at`, `updated_at`, and optional `pinned`/`archived`.
- `to_message(row: Any) -> Message`
  - Maps a DB-like `row` into a `Message`.
  - Reads: `id`, `conversation_id`, `role`, `content`, `agent`, `metadata_`, `created_at`.
  - Parses `row.metadata_` as JSON when present.

### Models (Pydantic `BaseModel`)
- `MessageStep`
  - Fields: `tool_name`, `prefix`, `status`, `input`, `output`.
- `MessageMetadataUpdate`
  - Fields: `execution_time`, `steps`, `sources`, `llm_model`.
- `ExportMessageMetadata`
  - Fields: `message_id`, `execution_time`, `steps`, `sources`.
- `ExportRequest`
  - Fields:
    - `format`: `"txt" | "json" | "md"` (validated by regex pattern)
    - `messages_metadata`: list of `ExportMessageMetadata`
- `Message`
  - Fields: `id`, `conversation_id`, `role` (`"user"|"assistant"|"system"`), `content`, `agent`, `metadata`, `created_at`.
- `Conversation`
  - Fields: `id`, `workspace_id`, `user_id`, `title`, `agent`, `pinned`, `archived`, `messages`, `created_at`, `updated_at`.
- `ConversationCreate`
  - Input payload to create a conversation.
  - Fields: `workspace_id` (1..100), `title` (1..200), `agent` (1..50).
- `ProviderConfigRequest`
  - Provider configuration for chat requests.
  - Fields: `id`, `name`, `type`, `enabled`, `endpoint`, `api_key`, `account_id`, `model`, `llm_model`.
  - Validation: `model_post_init()` raises `ValueError` if `type` not in `VALID_PROVIDER_TYPES`.
- `MessageRequest`
  - Structured message input.
  - Fields: `role`, `content` (max 100_000), `images` (max 10), `agent`.
- `ChatRequest`
  - Main chat request payload.
  - Fields: `conversation_id`, `workspace_id`, `message` (1..100_000), `images` (max 10), `messages` (max 200), `agent`, `provider`, `llm_model`, `context`, `system_prompt` (max 50_000), `search_enabled`, `regenerate_of`.
- `ChatResponse`
  - Chat response payload.
  - Fields: `conversation_id`, `message` (`Message`), `context_used`, `provider_used`.
- `ChatIngestMyDriveFileRequest`
  - File ingestion request payload.
  - Fields: `source_path` (1..1000), `workspace_id`, `embedding_model`, `embedding_dimension` (8..4096).
- `ChatFileIngestionResponse`
  - Ingestion response details.
  - Fields: `job_id`, `status`, `conversation_id`, `source_path`, `collection_name`, `file_sha256`, `cache_hit`, `chunks_count`, `statuses`, `embedding_model`, `embedding_dimension`.
- `ChatIngestionJobStatusResponse`
  - Ingestion job status details.
  - Fields: `job_id`, `conversation_id`, `workspace_id`, `source_path`, `status`, `progress`, `cache_hit`, `file_sha256`, `collection_name`, `chunks_count`, `error_code`, `error_message`, `attempt`, `max_attempts`, `created_at`, `updated_at`, `started_at`, `finished_at`.

## Configuration/Dependencies
- Depends on:
  - `pydantic.BaseModel`, `pydantic.Field`
  - `naas_abi.apps.nexus.apps.api.app.services.providers.model_catalog.list_catalog_providers`
  - Standard library: `json`, `datetime`, typing (`Any`, `Literal`)
- `VALID_PROVIDER_TYPES` is computed at import time and reflects the current provider catalog at import.

## Usage

```python
from datetime import datetime

from naas_abi.apps.nexus.apps.api.app.services.chat.adapters.primary.chat__primary_adapter__schemas import (
    ChatRequest,
    ProviderConfigRequest,
    to_message,
)

# Build a chat request payload
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

# Map a DB-like row to an API Message
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
- `ProviderConfigRequest.type` is validated in `model_post_init()`; invalid values raise `ValueError`.
- `to_message()` assumes `row.metadata_` is valid JSON when present; invalid JSON raises `json.JSONDecodeError`.
- Field constraints are enforced by Pydantic (e.g., `ChatRequest.messages` max 200, `images` max 10, `system_prompt` max 50_000).
