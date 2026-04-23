# `chat__primary_adapter__dependencies`

## What it is
FastAPI dependency/helpers module for the Chat primary adapter. It:
- Builds `RequestContext` objects from authenticated users.
- Binds a SQLAlchemy async DB session into a `PostgresSessionRegistry` so `ServiceRegistry` services can run with the correct session.
- Provides DI factories for chat-related services (chat, object storage, vector store, cache, file ingestion).
- Converts request schemas into service-layer inputs and orchestrates a few common chat flows (provider resolution, conversation creation, message building, search, persistence).

## Public API
Functions exposed by this module:

- `request_context(current_user: User) -> RequestContext`  
  Build a request context for the current authenticated user using the current Postgres session id.

- `system_request_context(user_id: str) -> RequestContext`  
  Build a request context for “system” operations as a specific user id.

- `bind_registry(db: AsyncSession)` (context manager)  
  Bind an `AsyncSession` to `PostgresSessionRegistry` under a new session id, set it as current, and yield `ServiceRegistry.instance()`. Always resets/unbinds on exit.

- `get_chat_service(registry: ServiceRegistry = Depends(get_service_registry)) -> ChatService`  
  FastAPI dependency returning `registry.chat`.

- `get_object_storage_service(request: Request) -> ObjectStorageService`  
  FastAPI dependency. Returns `request.app.state.object_storage` if set; otherwise pulls it from `ABIModule.get_instance().engine.services.object_storage` and caches it on `app.state`.

- `get_vector_store_service(request: Request) -> VectorStoreService`  
  Like above, for `vector_store`.

- `get_cache_service(request: Request) -> CacheService`  
  Like above, for `cache`.

- `get_chat_file_ingestion_service(...) -> ChatFileIngestionService`  
  FastAPI dependency constructing `ChatFileIngestionService(object_storage, vector_store, cache_service)`.

- `to_complete_chat_input(request: ChatRequest) -> CompleteChatInput`  
  Convert adapter-layer `ChatRequest` into service-layer `CompleteChatInput`, including mapping messages and (optional) provider config.

- `resolve_provider(context: RequestContext, provider: ProviderConfigRequest | None, has_images: bool, agent_id: str | None = None, workspace_id: str | None = None) -> ProviderConfigRequest | None`  
  Opens a DB session, binds registry, calls `registry.chat.resolve_provider(...)`, and returns the resolved provider as `ProviderConfigRequest` (or `None`).

- `get_or_create_conversation(chat_service: ChatService, request: ChatRequest, current_user: User, now: datetime) -> str`  
  Calls `chat_service.get_or_create_conversation(...)`. Translates:
  - `ValueError` → `HTTPException(400)`
  - `PermissionError` → `HTTPException(404)`

- `build_provider_messages_with_agents(request: ChatRequest, context: RequestContext, current_agent_id: str, db: AsyncSession, conversation_id: str | None = None) -> list[ProviderMessage]`  
  Using an existing DB session, binds registry and calls `registry.chat.build_provider_messages_with_agents(...)`.

- `run_search_if_needed(request: ChatRequest) -> str | None`  
  Opens a DB session, binds registry, calls `registry.chat.run_search_if_needed(message, search_enabled)`.

- `persist_stream_content(user_id: str, conversation_id: str, assistant_msg_id: str, full_response: str, touch_conversation: bool = False) -> None`  
  Opens a DB session, binds registry, and persists streamed assistant content:
  - If `touch_conversation=True`: calls `registry.chat.finalize_streaming_response(..., now=datetime.now(UTC).replace(tzinfo=None))`
  - Else: calls `registry.chat.update_message_content(...)`
  Commits the DB transaction.

## Configuration/Dependencies
- **FastAPI DI**
  - Uses `Depends(get_service_registry)` to obtain `ServiceRegistry`.
  - Uses `Request` to cache long-lived services on `request.app.state`:
    - `object_storage`, `vector_store`, `cache_service`

- **Database**
  - Uses `AsyncSessionLocal()` for internally-managed DB sessions (`resolve_provider`, `run_search_if_needed`, `persist_stream_content`).
  - For some operations (`build_provider_messages_with_agents`) the caller supplies an `AsyncSession`.

- **Session registry**
  - `PostgresSessionRegistry.instance()` is used to bind/unbind DB sessions and track the current session id.

- **ABIModule engine services**
  - Lazily accessed via `ABIModule.get_instance().engine.services.*` for object storage, vector store, and cache.

## Usage
Minimal examples (illustrative; requires the surrounding application context and imports).

### Use as FastAPI dependencies
```python
from fastapi import APIRouter, Depends, Request
from naas_abi.apps.nexus.apps.api.app.services.chat.adapters.primary.chat__primary_adapter__dependencies import (
    get_chat_service,
    get_chat_file_ingestion_service,
)

router = APIRouter()

@router.get("/health/chat")
async def chat_health(chat=Depends(get_chat_service)):
    # chat is a ChatService
    return {"service": "chat", "ok": True}

@router.get("/health/ingestion")
async def ingestion_health(ingestion=Depends(get_chat_file_ingestion_service)):
    # ingestion is a ChatFileIngestionService
    return {"service": "chat_file_ingestion", "ok": True}
```

### Bind a DB session to the registry for a registry-backed call
```python
from naas_abi.apps.nexus.apps.api.app.core.database import AsyncSessionLocal
from naas_abi.apps.nexus.apps.api.app.services.chat.adapters.primary.chat__primary_adapter__dependencies import (
    bind_registry,
)

async def do_something_registry_backed():
    async with AsyncSessionLocal() as db:
        with bind_registry(db) as registry:
            # Example: access chat service from registry
            _chat_service = registry.chat
```

## Caveats
- `bind_registry()` must be used around registry calls that rely on `PostgresSessionRegistry` to ensure the correct session is set and later cleaned up.
- `persist_stream_content()` commits the DB session; callers should not expect to manage that transaction externally for this operation.
- Error mapping in `get_or_create_conversation()` is specific:
  - `PermissionError` is converted to HTTP 404 (not 403).
