# provider_runtime

## What it is
Provider runtime/service utilities for routing chat completion and streaming requests to multiple AI backends:

- Anthropic (Claude) via `anthropic` SDK
- OpenAI via `openai` SDK
- OpenAI-compatible HTTP APIs (XAI, Mistral, OpenRouter, etc.)
- Ollama (local HTTP API; supports images; optional tool-calls loop)
- Cloudflare Workers AI
- ABI server (HTTP) and ABI in-process agents (`inprocess://...`)
- Remote, module-published agents (`type="remote"`)

Includes provider endpoint safety validation and URL query redaction for logs.

## Public API

### Data models
- `ProviderConfig(BaseModel)`
  - Provider configuration from frontend.
  - Fields:
    - `id: str`, `name: str`, `type: str`, `enabled: bool`
    - `endpoint: str | None`
    - `api_key: str | None`
    - `account_id: str | None` (Cloudflare)
    - `model: str`
    - `llm_model: str | None` (in-process ABI override)
- `Message(BaseModel)`
  - Chat message; supports optional images (base64 strings).
  - Fields: `role: Literal["user","assistant","system"]`, `content: str`, `images: list[str] | None`

### Exceptions
- `UnsafeProviderEndpointError(ValueError)`
  - Raised when a provider endpoint URL fails safety checks.

### Endpoint/logging helpers
- `redact_url_for_logs(url: str) -> str`
  - Redacts sensitive query keys (e.g., `token`, `api_key`, `authorization`) for safe logging.
- `validated_provider_endpoint(config: ProviderConfig) -> str | None`
  - Validates/normalizes `config.endpoint` based on `config.type`.
  - Returns a sanitized endpoint (no trailing `/`) or `None`.
- `is_multimodal_model(model_name: str) -> bool`
  - Returns `True` if `model_name` matches known multimodal/vision patterns.

### Chat completion (non-streaming)
- `complete_chat(messages, config, system_prompt, *, thread_id=None, injection_preamble) -> str`
  - Routes completion to the provider defined by `config.type`.
  - Provider types handled: `anthropic`, `openai`, `ollama`, `cloudflare`, `custom`, `abi`, `remote`.
- Provider-specific completions:
  - `complete_with_anthropic(messages, config, system_prompt) -> str`
  - `complete_with_openai(messages, config, system_prompt) -> str`
  - `complete_with_ollama(messages, config, system_prompt) -> str` (supports `Message.images`)
  - `complete_with_cloudflare(messages, config, system_prompt) -> str`
  - `complete_with_custom(messages, config, system_prompt) -> str` (POSTs to `.../v1/chat/completions`)
  - `complete_with_abi(messages, config, system_prompt, *, thread_id=None, injection_preamble) -> str`
    - Supports `inprocess://` endpoints (local in-process agent) or remote ABI HTTP endpoint.
  - `complete_with_remote_agent(messages, config, *, thread_id, injection_preamble) -> str`
    - Joins streamed chunks from a remote agent, ignoring step events.

### Streaming APIs
- `stream_with_ollama(messages, config, system_prompt) -> AsyncGenerator[str, None]`
  - Streams JSON-lines from Ollama `POST {endpoint}/api/chat`.
- `stream_with_openai_compatible(messages, config, system_prompt) -> AsyncGenerator[str, None]`
  - Streams SSE-style `data:` lines from `POST {endpoint}/chat/completions`.
  - Adds OpenRouter attribution headers when endpoint contains `"openrouter"`.
- `stream_with_cloudflare(messages, config, system_prompt) -> AsyncGenerator[str, None]`
  - Streams SSE from Cloudflare Workers AI.
- `stream_with_abi(messages, config, system_prompt=None) -> AsyncGenerator[str | dict[str, Any], None]`
  - Streams SSE from ABI server `POST {endpoint}/agents/{agent}/stream-completion?token=...`.
  - May also yield dict step events (tool usage/response, routing, model calls).
- `stream_with_abi_inprocess(messages, config, thread_id, *, user_context_preamble) -> AsyncGenerator[str | dict[str, Any], None]`
  - Streams from an in-process ABI agent.
  - May yield text deltas (`str`) and structured UI/tool events (`dict`).
- `stream_with_ollama_tools(messages, config, system_prompt=None, tools=None) -> AsyncGenerator[str, None]`
  - Streams from Ollama, detects tool calls, executes tools, then continues streaming.

### Tools
- `AVAILABLE_TOOLS: list[dict]`
  - Tool schema list (currently includes `search_web`).
- `execute_tool(tool_name: str, arguments: dict) -> str`
  - Executes `search_web` by POSTing to `http://localhost:8000/api/search/web`.

### Health/status
- `check_ollama_status(endpoint: str | None = None) -> dict`
  - Calls `GET {endpoint}/api/tags` and returns `{status, models, multimodal_models, ...}`.

### In-process ABI model routing hook
- `register_inprocess_llm_model_resolver(resolver: Callable[[str, str|None], str|None]) -> None`
  - Registers a resolver used by `resolve_inprocess_llm_model_for_turn(...)`.
- `resolve_inprocess_llm_model_for_turn(agent_name: str, config_llm: str | None) -> str | None`
  - Computes the effective chat model id for an in-process ABI agent turn.

## Configuration/Dependencies

- Required:
  - `httpx`
  - `pydantic`
- Optional SDKs:
  - `anthropic` (required for `complete_with_anthropic`)
  - `openai` (required for `complete_with_openai`)
- Settings fallback (from `naas_abi.apps.nexus.apps.api.app.core.config.settings`):
  - `settings.anthropic_api_key`
  - `settings.openai_api_key`
  - `settings.cloudflare_api_token`
  - `settings.cloudflare_account_id`
- Ollama endpoint resolution:
  - `naas_abi.apps.nexus.apps.api.app.services.ollama.resolve_endpoint()`

### Endpoint safety validation
`validated_provider_endpoint()` enforces (via `_validate_endpoint_url`):

- Only `http`/`https` schemes.
- Optional HTTPS requirement (e.g., official/custom endpoints require HTTPS).
- No credentials in URL.
- No query/fragment in endpoint URL.
- Blocks metadata hosts (`169.254.169.254`, `metadata.google.internal`).
- Blocks local/private IPs and `.local` hostnames unless explicitly allowed (Ollama allows localhost/private LAN; ABI allows localhost for non-`inprocess://`).

## Usage

### Minimal completion (Ollama)
```python
import asyncio
from naas_abi.apps.nexus.apps.api.app.services.provider_runtime import (
    ProviderConfig, Message, complete_chat
)

async def main():
    cfg = ProviderConfig(
        id="ollama1",
        name="Ollama",
        type="ollama",
        enabled=True,
        endpoint="http://localhost:11434",
        model="llama3.1",
    )
    messages = [Message(role="user", content="Say hello in one sentence.")]
    text = await complete_chat(messages, cfg, system_prompt=None, injection_preamble=None)
    print(text)

asyncio.run(main())
```

### Minimal streaming (OpenAI-compatible)
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
        endpoint=None,   # uses official endpoint for known provider types
        api_key="YOUR_KEY",
        model="grok-2-latest",
    )
    messages = [Message(role="user", content="Stream three words.")]
    async for chunk in stream_with_openai_compatible(messages, cfg, system_prompt=None):
        print(chunk, end="")

asyncio.run(main())
```

## Caveats
- `complete_chat(...)` requires `injection_preamble` (no default); pass `None` explicitly if not used.
- `stream_with_openai_compatible(...)` uses `config.api_key` directly (no settings fallback) and will fail if it is missing.
- Custom endpoint paths differ:
  - `complete_with_custom`: `POST {endpoint}/v1/chat/completions`
  - `stream_with_openai_compatible`: `POST {endpoint}/chat/completions`
- `stream_with_abi(...)` and `stream_with_abi_inprocess(...)` may yield structured dict events in addition to text; consumers must handle both types.
- `execute_tool("search_web", ...)` calls a local Nexus API at `http://localhost:8000/...`; it will fail if that service is not available.
