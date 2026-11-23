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

Every provider HTTP call goes through `provider_client()`, the guarded outbound client of `naas_abi_core.utils.outbound`: each host is resolved once, non-public addresses are refused unless the origin (host and port) is listed in `provider_allowed_origins`, or, for Ollama calls only, is the platform Ollama's origin; the connection goes to the checked address. Keys come from the resolved configuration only, never from the platform's settings.

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
- `provider_origin_entries(*, ollama=False) -> list[str]`
  - `settings.provider_allowed_origins`, plus the platform Ollama's endpoint when `ollama`.
- `provider_client(timeout: float, *, ollama=False) -> httpx.AsyncClient`
  - The guarded client every provider call uses; `ollama=True` for the Ollama calls only.
- `client_error_message(exc) -> str`
  - What a chat client is told when a provider call fails; the exception text stays in the log.
- `agent_path_segment(name) -> str`
  - An agent name as one percent-encoded URL path segment; refuses empty, `.`, `..` and control characters.
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
  - Streams SSE from ABI server `POST {endpoint}/agents/{agent}/stream-completion`, the agent name encoded as one path segment and the token in `Authorization: Bearer`.
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
- Settings (from `naas_abi.apps.nexus.apps.api.app.core.config.settings`):
  - `settings.provider_allowed_origins` (see `provider_client`). There is no fallback to platform keys: `anthropic`, `openai` and `cloudflare` calls need the key (and account) of the resolved configuration.
- Ollama endpoint resolution:
  - `naas_abi.apps.nexus.apps.api.app.services.ollama.resolve_endpoint()`

### Endpoint safety validation
`validated_provider_endpoint()` enforces (via `_validate_endpoint_url`):

- Only `http`/`https` schemes.
- Optional HTTPS requirement (e.g., official/custom endpoints require HTTPS).
- No credentials in URL.
- No query/fragment in endpoint URL.
- Blocks cloud metadata hosts always.
- Blocks local and private hosts (`naas_abi_core.utils.outbound.host_refusal`) unless the endpoint's origin is listed in `provider_allowed_origins`, or, for the `ollama` type only, is the platform Ollama's origin.

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
- Every provider call uses `config.api_key` (and `config.account_id`) directly, with no settings fallback, and fails if it is missing.
- Custom endpoint paths differ:
  - `complete_with_custom`: `POST {endpoint}/v1/chat/completions`
  - `stream_with_openai_compatible`: `POST {endpoint}/chat/completions`
- `stream_with_abi(...)` and `stream_with_abi_inprocess(...)` may yield structured dict events in addition to text; consumers must handle both types.
- `execute_tool("search_web", ...)` calls a local Nexus API at `http://localhost:8000/...`; it will fail if that service is not available.
