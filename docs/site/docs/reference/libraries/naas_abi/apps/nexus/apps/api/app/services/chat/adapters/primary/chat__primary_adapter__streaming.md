# `stream_chat_response`

## What it is
- An async FastAPI-compatible server-sent events (SSE) streaming handler that:
  - Resolves a chat provider based on the request/user context.
  - Builds provider-ready messages (including multi-agent and optional search context).
  - Streams model output chunks to the client as `text/event-stream`.
  - Persists streaming content incrementally and on completion (best-effort).

## Public API
- `async stream_chat_response(request: ChatRequest, current_user: User) -> StreamingResponse`
  - Main entrypoint returning a `fastapi.responses.StreamingResponse` producing SSE events.
  - Emits SSE frames with JSON payloads, plus a terminal `data: [DONE]`.

### SSE events emitted
- `{"conversation_id": "<id>"}` (first event)
- `{"sources": ...}` (only if vector context sources are available)
- `{"search": true}` (only if search context was added)
- `{"content": "<text chunk>"}` (for each streamed text chunk)
- `{"error": "<message>"}` (on errors or unsupported/no provider cases)
- `[DONE]` (always emitted at end of stream)

## Configuration/Dependencies
- Provider resolution and message preparation:
  - `resolve_provider(...)`
  - `build_provider_messages_with_agents(...)`
  - `get_or_create_conversation(...)`
  - `run_search_if_needed(request)`
  - `AGENT_SYSTEM_PROMPTS` (system prompt lookup)
  - Adds `MULTI_AGENT_NOTICE` to system prompt if any prior assistant messages exist in the request.
- Database/session:
  - `AsyncSessionLocal`
  - `bind_registry(db)` and registry methods:
    - `registry.chat.create_streaming_message_pair(...)` (best-effort pre-persist)
    - `registry.chat._inject_chat_vector_context(...)`
  - Persistence during/after streaming:
    - `persist_stream_content(...)` (incremental flush and final write)
- Streaming backends (selected by `provider.type`):
  - `"ollama"` → `stream_with_ollama(...)`
  - `"cloudflare"` → `stream_with_cloudflare(...)`
  - `"abi"` → `stream_with_abi_inprocess(...)` (requires emitting at least one chunk)
  - OpenAI-compatible types (`xai`, `openai`, `anthropic`, `mistral`, `google`, `openrouter`, `perplexity`)
    → `stream_with_openai_compatible(...)`
- Supported streaming provider types are controlled by:
  - `SUPPORTED_STREAMING = ["ollama", "cloudflare", "abi", *OPENAI_COMPATIBLE]`

## Usage
Minimal FastAPI endpoint that returns the SSE stream:

```python
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import User
from naas_abi.apps.nexus.apps.api.app.services.chat.adapters.primary.chat__primary_adapter__schemas import ChatRequest
from naas_abi.apps.nexus.apps.api.app.services.chat.adapters.primary.chat__primary_adapter__streaming import (
    stream_chat_response,
)

router = APIRouter()

def get_current_user() -> User:
    ...  # your auth dependency

@router.post("/chat/stream", response_class=StreamingResponse)
async def chat_stream(request: ChatRequest, current_user: User = Depends(get_current_user)):
    return await stream_chat_response(request, current_user)
```

## Caveats
- If no provider is resolved, the stream returns an SSE error message suggesting installing/pulling an Ollama model and then `[DONE]`.
- If `provider.type` is not in `SUPPORTED_STREAMING`, the stream returns an SSE error and `[DONE]`.
- Streaming persistence is **best-effort**:
  - Incremental flush occurs only when an assistant message ID was created and thresholds are met (≥512 chars or ≥0.75s since last flush).
  - Failures to pre-persist or flush content are logged and do not necessarily stop streaming.
- For `"abi"` provider type, the in-process stream must emit at least one chunk; otherwise a `RuntimeError` is raised and sent as an SSE error payload.
