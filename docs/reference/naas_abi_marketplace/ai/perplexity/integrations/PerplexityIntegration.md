# PerplexityIntegration

## What it is
A small client integration for Perplexity’s API that:
- Calls `POST /chat/completions` to answer a question using Perplexity models and web search options.
- Optionally exposes the capability as LangChain `StructuredTool` tools.

## Public API

- `PerplexityIntegrationConfiguration` (dataclass, extends `IntegrationConfiguration`)
  - Purpose: holds configuration for API access.
  - Fields:
    - `api_key: str` — Perplexity API key (Bearer token).
    - `base_url: str = "https://api.perplexity.ai"` — API base URL.
    - `system_prompt: str = "Be precise and concise and answer the question with sources."` — default system instruction.

- `PerplexityIntegration` (class, extends `Integration`)
  - Purpose: performs requests to Perplexity and returns the generated answer text.
  - `__init__(configuration: PerplexityIntegrationConfiguration)`
    - Sets `Authorization: Bearer <api_key>` and `Content-Type: application/json` headers.
  - `search_web(...) -> str`
    - Sends a chat completion request and returns `response["choices"][0]["message"]["content"]`.
    - Key parameters:
      - `question: str` — user prompt.
      - `system_prompt: str | None` — overrides config default when provided.
      - `model: str = "sonar-pro"`
      - Web/search options: `search_mode`, `search_context_size`, `user_location`, `search_recency_filter`, `search_domain_filter`
      - Generation options: `max_tokens`, `temperature`, `top_p`, `top_k`, `presence_penalty`, `frequency_penalty`, `reasoning_effort`, `stream`
      - Output options: `return_images`, `return_related_questions`, `response_format`
    - Removes payload keys whose values are `None`, `[]`, or `{}` before sending.

- `as_tools(configuration: PerplexityIntegrationConfiguration) -> list`
  - Purpose: returns a list of LangChain `StructuredTool` objects backed by `PerplexityIntegration.search_web`:
    - `perplexity_quick_search` — uses `model="sonar"`, accepts `question`, `user_location`, `search_context_size`.
    - `perplexity_search` — uses `model="sonar-pro"`, accepts `question`, `user_location`, `search_context_size`.
    - `perplexity_advanced_search` — uses `model="sonar-pro"` and forces `search_context_size="high"`, accepts `question`, `user_location`.

## Configuration/Dependencies
- Required:
  - `requests`
  - `pydantic`
  - `naas_abi_core.integration.integration` (`Integration`, `IntegrationConfiguration`, `IntegrationConnectionError`)
- Optional (only for `as_tools`):
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
# tools contains: perplexity_quick_search, perplexity_search, perplexity_advanced_search
```

## Caveats
- HTTP request failures are raised as `IntegrationConnectionError`.
- `search_web` assumes the response includes `choices[0].message.content`; if the API response shape differs, a `KeyError` will occur.
- `as_tools` imports `langchain_core` inside the function; calling it without that dependency installed will fail.
