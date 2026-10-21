# `stream_chat_response`

## What it is
- An async FastAPI-compatible Server-Sent Events (SSE) streaming handler for chat responses.
- Responsibilities:
  - Resolve the effective chat agent (optionally rewriting based on workspace + open Office context).
  - Resolve a provider capable of streaming and build provider-ready messages (including agent/tool context and vector context).
  - Stream model output and tool/agent events as SSE frames (`text/event-stream`).
  - Best-effort persistence of:
    - Message pair pre-creation (user + assistant placeholders).
    - Incremental assistant content during streaming.
    - Final metadata (execution time, steps, sources, llm_model).
    - Regeneration bookkeeping (marking old message superseded).

## Public API
- `async stream_chat_response(request: ChatRequest, current_user: User) -> StreamingResponse`
  - Entry point returning `fastapi.responses.StreamingResponse` producing SSE frames.
  - First frame includes identifiers and the effective LLM model used:
    - `conversation_id`
    - `assistant_message_id`
    - `llm_model` (may differ from request due to routing/model overrides)

### SSE frames emitted (payloads are JSON unless `[DONE]`)
- First frame:
  - `{"conversation_id": "...", "assistant_message_id": "...", "llm_model": "..."}`
- Optional sources frames:
  - `{"sources": ["https://...", ...]}` (may be sent early and again at end; merges vector context sources + URLs extracted from tool responses)
- Content frames:
  - `{"content": "<text chunk>"}` (for each streamed text chunk)
- Tool/agent event frames (dict chunks passthrough from provider streams)
  - Events are also ingested server-side into a `steps` accumulator for metadata persistence (mirrors frontend behavior).
- Error frame (on failure):
  - `{"error": "<escaped message>"}`
- Terminal frame (always):
  - `[DONE]`

## Configuration/Dependencies
- Database/session:
  - `AsyncSessionLocal`
  - Registry binding: `bind_registry(db)`
  - Persistence helpers:
    - `get_or_create_conversation(...)`
    - `persist_stream_content(...)`
    - `persist_stream_metadata(...)`
    - `mark_message_superseded(...)`
- Provider resolution and message preparation:
  - `resolve_provider(context, request.provider, has_images, agent_id, workspace_id)`
  - `build_provider_messages_with_agents(...)`
  - Vector context injection: `registry.chat._inject_chat_vector_context(...)`
  - System prompt/preamble:
    - `registry.chat.build_system_prompt(...)`
    - `registry.chat.build_remote_agent_preamble(...)` (for `provider.type == "remote"`)
    - `registry.chat.build_abi_injection_preamble(...)` (otherwise)
- Supported streaming backends:
  - `"ollama"` → `stream_with_ollama(...)`
  - `"cloudflare"` → `stream_with_cloudflare(...)`
  - `"abi"` → `stream_with_abi_inprocess(...)` (requires `endpoint` starting with `inprocess://` for model routing; must emit at least one chunk)
  - `"remote"` → `stream_with_remote_agent(...)`
  - OpenAI-compatible types:
    - `["xai", "openai", "anthropic", "mistral", "google", "openrouter", "perplexity"]`
    - → `stream_with_openai_compatible(...)`
- Provider type allowlist:
  - `SUPPORTED_STREAMING = ["ollama", "cloudflare", "abi", "remote", *OPENAI_COMPATIBLE]`
- Office/coding context integration (optional; driven by `request.context`):
  - Auto-title for open documents/slides: `_apply_office_auto_title(...)` (best-effort, runs in threadpool)
  - Binds agent execution context variables (user/workspace/chat ids, open document/deck/sheet slugs, sidecar credentials, coding repo bindings, feature context, research policies).

## Usage
Minimal FastAPI endpoint returning the SSE stream:

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
- If no provider can be resolved, the stream emits an SSE error hinting to install/pull an Ollama model (`DEFAULT_CHAT_MODEL_TAG`), then `[DONE]`.
- If `provider.type` is not in `SUPPORTED_STREAMING`, the stream emits an SSE error and `[DONE]`.
- Persistence is best-effort:
  - Pre-creation of message IDs can fail; streaming still proceeds (but incremental flush/metadata persistence are skipped without `assistant_msg_id`).
  - Incremental flush occurs only when both conditions are met:
    - buffered ≥ 512 chars **or** ≥ 0.75s since last flush.
- For `provider.type == "abi"` using in-process streaming: if the stream yields no chunks, a `RuntimeError` is raised and returned as an SSE error payload.
- On errors during streaming, partial content/metadata persistence is attempted, then an error frame and `[DONE]` are emitted.
