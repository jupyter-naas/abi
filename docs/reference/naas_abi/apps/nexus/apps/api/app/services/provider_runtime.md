# provider_runtime

## What it is
Provider runtime/service utilities for routing chat completion and streaming requests to multiple AI backends:

- Anthropic (Claude) via `anthropic` SDK
- OpenAI via `openai` SDK
- OpenAI-compatible HTTP APIs (e.g., XAI, Mistral, OpenRouter, etc.)
- Ollama (local HTTP API; supports images; optional tool-calls loop)
- Cloudflare Workers AI
- ABI server and ABI in-process agents (`inprocess://...`)

Includes endpoint safety validation and basic URL redaction for logs.

## Public API

### Data models
- `ProviderConfig (pydantic.BaseModel)`
  - Frontend-provided provider configuration.
  - Fields: `id`, `name`, `type`, `enabled`, `endpoint`, `api_key`, `account_id`, `model`.
- `Message (pydantic.BaseModel)`
  - Chat message (supports optional images).
  - Fields: `role` (`"user"|"assistant"|"system"`), `content`, `images` (list of base64 strings).

### Exceptions
- `UnsafeProviderEndpointError(ValueError)`
  - Raised when a provider endpoint URL fails safety checks.

### Endpoint and logging helpers
- `redact_url_for_logs(url: str) -> str`
  - Redacts sensitive query keys (e.g., `token`, `api_key`, `authorization`) in a URL string for safe logging.
- `validated_provider_endpoint(config: ProviderConfig) -> str | None`
  - Validates/normalizes `config.endpoint` based on `config.type` and returns a sanitized endpoint (no trailing `/`).
  - Enforces HTTPS for official/custom endpoints; allows localhost for Ollama and some ABI cases.
- `is_multimodal_model(model_name: str) -> bool`
  - Returns `True` if the model name matches known vision/multimodal patterns.

### Chat completion (non-streaming)
- `complete_chat(messages, config, system_prompt=None, thread_id=None) -> str`
  - Routes to the appropriate provider based on `config.type`.
- Provider-specific completions:
  - `complete_with_anthropic(messages, config, system_prompt=None) -> str`
  - `complete_with_openai(messages, config, system_prompt=None) -> str`
  - `complete_with_ollama(messages, config, system_prompt=None) -> str`
  - `complete_with_cloudflare(messages, config, system_prompt=None) -> str`
  - `complete_with_custom(messages, config, system_prompt=None) -> str` (OpenAI-compatible `/v1/chat/completions`)
  - `complete_with_abi(messages, config, system_prompt=None, thread_id=None) -> str`
    - Supports `inprocess://` endpoints (invokes local agent) or remote ABI HTTP endpoint.

### Streaming APIs
All streaming functions return `AsyncGenerator[...]` yielding text chunks (and in one case, structured events).

- `stream_with_ollama(messages, config, system_prompt=None) -> AsyncGenerator[str, None]`
  - Streams JSON-lines from Ollama `/api/chat`.
- `stream_with_openai_compatible(messages, config, system_prompt=None) -> AsyncGenerator[str, None]`
  - Streams SSE `data:` lines from `{endpoint}/chat/completions`.
- `stream_with_cloudflare(messages, config, system_prompt=None) -> AsyncGenerator[str, None]`
  - Streams SSE from Cloudflare Workers AI.
- `stream_with_abi(messages, config, system_prompt=None) -> AsyncGenerator[str, None]`
  - Streams SSE from ABI server `/agents/{agent}/stream-completion?token=...`.
- `stream_with_abi_inprocess(messages, config, thread_id=None) -> AsyncGenerator[str | dict[str, Any], None]`
  - Streams by invoking an in-process ABI agent.
  - May yield:
    - text deltas (`str`)
    - UI/tool status events (`dict`) extracted from Opencode-style events (e.g., `{"event": "tool", ...}`).
- `stream_with_ollama_tools(messages, config, system_prompt=None, tools=None) -> AsyncGenerator[str, None]`
  - Streams from Ollama and executes tool calls (see `AVAILABLE_TOOLS`) via local API.

### Tools
- `AVAILABLE_TOOLS: list[dict]`
  - Currently includes a `search_web` function tool schema.
- `execute_tool(tool_name: str, arguments: dict) -> str`
  - Executes `search_web` by POSTing to `http://localhost:8000/api/search/web` and returns formatted results.

### Health/status
- `check_ollama_status(endpoint: str = "http://localhost:11434") -> dict`
  - Returns `{status, models, multimodal_models, ...}`; on failure returns `{status:"offline", error:...}`.

## Configuration/Dependencies

### Python dependencies
- `httpx` (required)
- `pydantic` (required)
- Optional SDKs:
  - `anthropic` (required only for `complete_with_anthropic`)
  - `openai` (required only for `complete_with_openai`)

### Settings (imported from `naas_abi.apps.nexus.apps.api.app.core.config.settings`)
Used as fallback when not provided in `ProviderConfig`:
- `settings.anthropic_api_key`
- `settings.openai_api_key`
- `settings.cloudflare_api_token`
- `settings.cloudflare_account_id`

### Endpoint safety rules (enforced by `validated_provider_endpoint`)
- Only `http`/`https` schemes allowed.
- Optional HTTPS requirement depending on provider type.
- Credentials in URL are rejected.
- Query/fragment in provider endpoint are rejected (except ABI remote call constructs its own query later).
- Local/private IP ranges and `.local` are blocked unless explicitly allowed (e.g., Ollama, some ABI).
- For known official providers, host must match the official host (even if a custom endpoint is supplied).

## Usage

### Minimal completion via `complete_chat` (Ollama)
```python
import asyncio
from naas_abi.apps.nexus.apps.api.app.services.provider_runtime import (
    ProviderConfig, Message, complete_chat
)

async def main():
    cfg = ProviderConfig(
        id="ollama1",
        name="Local Ollama",
        type="ollama",
        enabled=True,
        endpoint="http://localhost:11434",
        model="llama3.1",
    )
    messages = [Message(role="user", content="Say hello in one sentence.")]
    text = await complete_chat(messages, cfg)
    print(text)

asyncio.run(main())
```

### Minimal streaming (OpenAI-compatible endpoint)
```python
import asyncio
from naas_abi.apps.nexus.apps.api.app.services.provider_runtime import (
    ProviderConfig, Message, stream_with_openai_compatible
)

async def main():
    cfg = ProviderConfig(
        id="xai1",
        name="XAI",
        type="xai",
        enabled=True,
        endpoint=None,          # uses official endpoint for type when omitted
        api_key="YOUR_KEY",
        model="grok-2-latest",
    )
    messages = [Message(role="user", content="Stream three words.")]
    async for chunk in stream_with_openai_compatible(messages, cfg):
        print(chunk, end="")

asyncio.run(main())
```

## Caveats
- `complete_with_openai_compatible`/`stream_with_openai_compatible` require a valid `config.api_key`; no settings fallback is used there.
- `complete_with_custom` posts to `"{endpoint}/v1/chat/completions"` (note the `/v1`), while `stream_with_openai_compatible` posts to `"{endpoint}/chat/completions"` (no `/v1`).
- ABI remote completion embeds the token as a query parameter (`...?token=...`); use `redact_url_for_logs()` when logging such URLs.
- `stream_with_abi_inprocess` may yield dictionaries (UI/tool events) in addition to text; consumers must handle both.
