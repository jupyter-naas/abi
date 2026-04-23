# PerplexityIntegration

## What it is
A small integration client for Perplexity’s API that:
- Calls `POST /chat/completions` to perform web-backed Q&A via Perplexity models.
- Optionally exposes the search capability as LangChain `StructuredTool`s.

## Public API

### `PerplexityIntegrationConfiguration`
Dataclass configuration (extends `IntegrationConfiguration`):
- `api_key: str` — Perplexity API key (Bearer token).
- `base_url: str = "https://api.perplexity.ai"` — API base URL.
- `system_prompt: str = "Be precise and concise and answer the question with sources."` — default system prompt.

### `PerplexityIntegration`
Integration client (extends `Integration`):
- `__init__(configuration: PerplexityIntegrationConfiguration)`
  - Initializes headers with `Authorization: Bearer <api_key>` and JSON content type.
- `search_web(...) -> str`
  - Sends a chat completion request with web search options and returns `response["choices"][0]["message"]["content"]`.
  - Key parameters:
    - `question: str` — user question.
    - `system_prompt: str | None` — overrides config default when provided.
    - `model: str = "sonar-pro"` — model name passed to Perplexity.
    - Search/web options: `search_mode`, `search_context_size`, `user_location`, `search_recency_filter`, `search_domain_filter`, etc.
    - Generation controls: `max_tokens`, `temperature`, `top_p`, `top_k`, `presence_penalty`, `frequency_penalty`, `reasoning_effort`.
  - Internally removes payload keys where the value is `None`, `[]`, or `{}` before sending.

### `as_tools(configuration: PerplexityIntegrationConfiguration) -> list`
Factory returning LangChain `StructuredTool` objects backed by `PerplexityIntegration.search_web`:
- `perplexity_quick_search` — uses `model="sonar"`.
- `perplexity_search` — uses `model="sonar-pro"`.
- `perplexity_advanced_search` — uses `model="sonar-pro"` and forces `search_context_size="high"`.

Each tool uses a Pydantic schema for arguments:
- `question: str` (required)
- `user_location: str` (default `"FR"`)
- `search_context_size: str` (default `"medium"`, validated as `low|medium|high`) for quick/search tools.

## Configuration/Dependencies
- Requires:
  - `requests`
  - `pydantic`
  - `naas_abi_core.integration` (`Integration`, `IntegrationConfiguration`, `IntegrationConnectionError`)
- Optional (only if using `as_tools`):
  - `langchain_core.tools.StructuredTool`

## Usage

### Basic client usage
```python
from naas_abi_marketplace.ai.perplexity.integrations.PerplexityIntegration import (
    PerplexityIntegration,
    PerplexityIntegrationConfiguration,
)

config = PerplexityIntegrationConfiguration(api_key="YOUR_PERPLEXITY_API_KEY")
client = PerplexityIntegration(config)

answer = client.search_web(
    question="What is the current GDP of France? Provide sources.",
    user_location="FR",
    search_context_size="medium",
)
print(answer)
```

### LangChain tools
```python
from naas_abi_marketplace.ai.perplexity.integrations.PerplexityIntegration import (
    PerplexityIntegrationConfiguration,
    as_tools,
)

tools = as_tools(PerplexityIntegrationConfiguration(api_key="YOUR_PERPLEXITY_API_KEY"))
# tools is a list of StructuredTool instances (perplexity_quick_search, perplexity_search, perplexity_advanced_search)
```

## Caveats
- Errors from HTTP requests are wrapped and raised as `IntegrationConnectionError`.
- `search_web` assumes the API response contains `choices[0].message.content`; missing/changed response structure will raise a `KeyError`.
- `search_domain_filter` default is a mutable empty list (`[]`) in the function signature.
