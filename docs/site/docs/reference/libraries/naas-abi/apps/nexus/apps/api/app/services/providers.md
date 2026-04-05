# providers

## What it is
Provider-facing service functions and data models used by the Nexus API to run chat completions (sync or streaming) against multiple AI backends:

- Anthropic (Claude)
- OpenAI
- Ollama (local)
- Cloudflare Workers AI
- Custom OpenAI-compatible HTTP endpoints
- ABI server streaming and in-process ABI agent streaming
- Optional Ollama tool-calling loop via a local `search_web` API

## Public API

### Data models
- `class ProviderConfig(BaseModel)`
  - Provider configuration (typically supplied by the frontend).
  - Fields: `id`, `name`, `type`, `enabled`, `endpoint`, `api_key`, `account_id`, `model`.

- `class Message(BaseModel)`
  - Chat message representation.
  - Fields: `role` (`"user"|"assistant"|"system"`), `content`, optional `images` (list of base64 strings).

### Chat completion (non-streaming)
- `async def complete_chat(messages, config, system_prompt=None) -> str`
  - Routes to the correct provider based on `config.type`.
  - Supported `type`: `anthropic`, `openai`, `ollama`, `cloudflare`, `custom`.

- `async def complete_with_anthropic(messages, config, system_prompt=None) -> str`
  - Uses `anthropic` SDK; merges `system_prompt` with any `"system"` messages.

- `async def complete_with_openai(messages, config, system_prompt=None) -> str`
  - Uses `openai` SDK; prepends `system_prompt` as a `"system"` message if provided.

- `async def complete_with_ollama(messages, config, system_prompt=None) -> str`
  - Calls Ollama `POST {endpoint}/api/chat` with `stream=False`.
  - Supports `Message.images` for multimodal models.

- `async def complete_with_cloudflare(messages, config, system_prompt=None) -> str`
  - Calls Cloudflare Workers AI run endpoint; returns `data["result"]["response"]` when present.

- `async def complete_with_custom(messages, config, system_prompt=None) -> str`
  - Calls a custom OpenAI-compatible endpoint: `POST {endpoint}/v1/chat/completions`.

### Chat completion (streaming)
- `async def stream_with_ollama(messages, config, system_prompt=None) -> AsyncGenerator[str, None]`
  - Streams Ollama JSON lines from `POST {endpoint}/api/chat` with `stream=True`.
  - Yields `message.content` tokens as they arrive.

- `async def stream_with_openai_compatible(messages, config, system_prompt=None) -> AsyncGenerator[str, None]`
  - Streams Server-Sent Events-like lines from `POST {endpoint}/chat/completions` (expects `data: ...` lines).
  - Extracts and yields `choices[0].delta.content`.

- `async def stream_with_cloudflare(messages, config, system_prompt=None) -> AsyncGenerator[str, None]`
  - Streams Cloudflare Workers AI with `stream=True` and yields `data["response"]` from `data: ...` SSE lines.

- `async def stream_with_ollama_tools(messages, config, system_prompt=None, tools=None) -> AsyncGenerator[str, None]`
  - Streams Ollama, detects tool calls in `message.tool_calls`, executes them via `execute_tool`, then continues streaming without tools.
  - Yields a `*Searching...*` marker when tool execution begins.

- `async def stream_with_abi(messages, config, system_prompt=None) -> AsyncGenerator[str, None]`
  - Streams from an ABI server using SSE:
    - `POST {endpoint}/agents/{agent_name}/stream-completion?token={token}`
  - Uses the latest `"user"` message as `prompt`, and a hash-based `thread_id`.
  - Prefers SSE event `ai_message`; falls back to `message` if `ai_message` never appears; suppresses consecutive duplicates.

- `async def stream_with_abi_inprocess(messages, config, thread_id=None) -> AsyncGenerator[str, None]`
  - Invokes an ABI agent directly in-process via `agent.stream_invoke(...)`.
  - Resolves agent from the ABI module registry (and a local fallback set) using `_resolve_inprocess_abi_agent`.
  - If `thread_id` is provided and agent supports it, sets agent thread id.

### Utilities
- `def is_multimodal_model(model_name: str) -> bool`
  - Returns `True` if `model_name` contains any substring in `MULTIMODAL_MODEL_PATTERNS`.

- `async def check_ollama_status(endpoint: str = "http://localhost:11434") -> dict`
  - Calls `GET {endpoint}/api/tags`, returns:
    - `status`: `"online"`/`"offline"`
    - `models`: list of model names
    - `multimodal_models`: filtered list using `is_multimodal_model`

### Tools
- `AVAILABLE_TOOLS: list[dict]`
  - Currently defines one function tool: `search_web` with parameters `{query, engine}`.

- `async def execute_tool(tool_name: str, arguments: dict) -> str`
  - Implements `search_web` by calling local API:
    - `POST http://localhost:8000/api/search/web` with `{query, engine, limit: 5}`
  - Returns formatted bullet results, or an error/empty message.

## Configuration/Dependencies
- `settings` (from `naas_abi.apps.nexus.apps.api.app.core.config`) provides fallback credentials:
  - `settings.anthropic_api_key`
  - `settings.openai_api_key`
  - `settings.cloudflare_api_token`
  - `settings.cloudflare_account_id`

- Optional SDK dependencies:
  - `anthropic` (required for `complete_with_anthropic`)
  - `openai` (required for `complete_with_openai`)

- HTTP client:
  - `httpx.AsyncClient` used for Ollama, Cloudflare, custom endpoints, tool execution, and ABI streaming.

- Provider-specific expectations:
  - Ollama default endpoint: `http://localhost:11434` if `config.endpoint` is unset.
  - OpenAI-compatible streaming expects `data: ...` lines and `[DONE]` termination.
  - Cloudflare model path is derived from `config.model.lstrip("@cf/")`.

## Usage

### Route a non-streaming completion (Ollama)
```python
import asyncio
from naas_abi.apps.nexus.apps.api.app.services.providers import (
    Message, ProviderConfig, complete_chat
)

async def main():
    cfg = ProviderConfig(
        id="ollama1",
        name="Local Ollama",
        type="ollama",
        enabled=True,
        endpoint="http://localhost:11434",
        model="llama3",
    )
    msgs = [Message(role="user", content="Say hello.")]
    text = await complete_chat(msgs, cfg)
    print(text)

asyncio.run(main())
```

### Stream tokens (OpenAI-compatible endpoint)
```python
import asyncio
from naas_abi.apps.nexus.apps.api.app.services.providers import (
    Message, ProviderConfig, stream_with_openai_compatible
)

async def main():
    cfg = ProviderConfig(
        id="compat1",
        name="Compat",
        type="custom",
        enabled=True,
        endpoint="https://example.com/v1",  # base URL that serves /chat/completions
        api_key="YOUR_KEY",
        model="gpt-4o-mini",
    )
    msgs = [Message(role="user", content="Stream a short poem.")]
    async for chunk in stream_with_openai_compatible(msgs, cfg):
        print(chunk, end="")

asyncio.run(main())
```

## Caveats
- `complete_chat()` does **not** route to streaming functions or ABI streaming; streaming must be called explicitly.
- `stream_with_openai_compatible()` uses `config.endpoint.rstrip("/")` and posts to `"{endpoint}/chat/completions"` (note: not `.../v1/...` unless your `endpoint` already includes it).
- `stream_with_openai_compatible()` assumes SSE-like `data: ...` lines; non-SSE streaming formats will be ignored.
- `complete_with_custom()` posts to `"{config.endpoint}/v1/chat/completions"`; include the correct base URL accordingly.
- Tool execution (`execute_tool`) depends on a local service at `http://localhost:8000/api/search/web`; failures are returned as text to the model stream.
- `stream_with_abi()` and `stream_with_abi_inprocess()` only send the **latest** user message as the prompt (they do not serialize the full message history into the request body).
