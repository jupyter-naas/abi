# chat.py

## What it is
FastAPI endpoints for a workspace-scoped chat/conversation API backed by async SQLAlchemy models. Supports:
- CRUD for conversations
- Chat completion (non-streaming)
- Server-Sent Events (SSE) streaming completions with incremental persistence
- Optional web-search context injection
- Provider selection via request, agent configuration, workspace ABI server, or Ollama fallback

## Public API

### FastAPI router
- `router: APIRouter`  
  Registers all endpoints in this module.

### Pydantic schemas
- `Message`  
  API representation of a stored message (`role`, `content`, `agent`, `metadata`, timestamps).
- `Conversation`  
  API representation of a conversation (includes optional `messages` list).
- `ConversationCreate`  
  Payload to create a conversation (`workspace_id`, `title`, `agent`).
- `ProviderConfigRequest`  
  Provider config sent by frontend; validates `type` against model registry + `custom` + `abi`.
- `MessageRequest`  
  Message payload for chat history, supports optional `images`.
- `ChatRequest`  
  Main chat input (`conversation_id`/`workspace_id`, `message`, optional history `messages`, `agent`, optional `provider`, optional `system_prompt`, `search_enabled`).
- `ChatResponse`  
  Non-streaming completion response (`conversation_id`, `message`, `provider_used`).

### Endpoints
- `GET /conversations` → `list_conversations(...) -> list[Conversation]`  
  List conversations for a workspace (requires workspace access). Supports `limit` (<=200) and `offset`.
- `POST /conversations` → `create_conversation(...) -> Conversation`  
  Create a new conversation for a workspace (requires workspace access).
- `GET /conversations/{conversation_id}` → `get_conversation(...) -> Conversation`  
  Fetch a conversation by id; can include messages (`include_messages=True`).
- `POST /complete` → `complete_chat(...) -> ChatResponse`  
  Persist user message, run provider completion, persist assistant message, update conversation timestamp.
- `POST /stream` → `stream_chat(...) -> StreamingResponse`  
  SSE stream of assistant output. Pre-persists user + placeholder assistant message, flushes assistant content incrementally, finalizes on completion.
- `PATCH /conversations/{conversation_id}` → `update_conversation(...) -> dict[str, str]`  
  Update allowed fields: `title`, `pinned`, `archived`.
- `DELETE /conversations/{conversation_id}` → `delete_conversation(...) -> dict[str, str]`  
  Delete conversation and all its messages.
- `GET /conversations/{conversation_id}/export` → `export_conversation(...) -> StreamingResponse`  
  Export conversation as `txt`, `json`, or `md` (download via `Content-Disposition`).
- `GET /ollama/status` → `get_ollama_status(...) -> dict`  
  Check Ollama status and list available models.

## Configuration/Dependencies
- **Auth / Access control**
  - `get_current_user_required` (FastAPI dependency)
  - `require_workspace_access(user_id, workspace_id)` enforced on workspace-scoped operations
- **Database**
  - `get_db` provides `AsyncSession`
  - `AsyncSessionLocal` used internally for some streaming operations and provider resolution lookups
  - Models: `ConversationModel`, `MessageModel`, `AgentConfigModel` (and on-demand: `InferenceServerModel`, `SecretModel`)
- **Provider system**
  - Provider registry: `get_all_provider_names()` used to validate `ProviderConfigRequest.type`
  - Provider operations:
    - `complete_chat` (imported as `complete_with_provider`) for non-streaming
    - Streaming functions: `stream_with_ollama`, `stream_with_cloudflare`, `stream_with_abi_inprocess`, `stream_with_openai_compatible` (imported lazily)
  - Provider selection order:
    1. Request `provider` if `enabled`
    2. Agent config (`AgentConfigModel`) including secrets lookup for API keys
    3. Workspace external ABI server (when agent/provider indicates `abi`)
    4. Ollama auto-detect fallback (if online)
- **Search tool (optional)**
  - `execute_tool("search_web", ...)` used when `search_enabled=True` or implicit trigger phrases appear in the message

## Usage

### Call non-streaming completion (`POST /complete`)
```python
import requests

base_url = "http://localhost:8000"
token = "YOUR_BEARER_TOKEN"

payload = {
    "workspace_id": "ws-123",
    "message": "Hello, what can you do?",
    "agent": "aia",
}

r = requests.post(
    f"{base_url}/complete",
    json=payload,
    headers={"Authorization": f"Bearer {token}"},
)
print(r.json()["message"]["content"])
```

### Consume SSE streaming (`POST /stream`)
```python
import requests

base_url = "http://localhost:8000"
token = "YOUR_BEARER_TOKEN"

payload = {
    "workspace_id": "ws-123",
    "message": "Stream a short answer.",
    "agent": "aia",
}

with requests.post(
    f"{base_url}/stream",
    json=payload,
    headers={"Authorization": f"Bearer {token}"},
    stream=True,
) as r:
    for line in r.iter_lines(decode_unicode=True):
        if line:
            print(line)
```

## Caveats
- `workspace_id` is required when creating a new conversation (either no `conversation_id`, or a non-existent `conversation_id`); otherwise the request fails with HTTP 400.
- Streaming is only supported for provider types: `ollama`, `cloudflare`, `abi`, and the listed OpenAI-compatible types (`xai`, `openai`, `anthropic`, `mistral`, `google`, `openrouter`, `perplexity`). Other types return an SSE error event.
- In `/stream`, DB persistence is best-effort:
  - Pre-persist failure does not stop streaming, but prevents incremental updates by `assistant_msg_id`.
  - Incremental flush errors are logged and streaming continues.
- `/complete` returns an instructional message instead of a model response when no provider can be resolved (e.g., Ollama not available and no configured provider).
