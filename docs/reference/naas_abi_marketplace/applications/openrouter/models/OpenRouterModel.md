# OpenRouterModel

## What it is
A minimal wrapper that creates a `langchain_openai.ChatOpenAI` client configured to use the OpenRouter API endpoint.

## Public API
- `class OpenRouterModel`
  - `__init__(api_key: str)`
    - Stores the provided API key and sets `base_url` to `https://openrouter.ai/api/v1`.
  - `get_model(model_id: str) -> langchain_openai.ChatOpenAI`
    - Returns a `ChatOpenAI` instance configured with:
      - `model=model_id`
      - `api_key=pydantic.SecretStr(self.api_key)`
      - `base_url=self.base_url`

## Configuration/Dependencies
- Dependencies:
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
- Configuration:
  - Requires an OpenRouter API key passed to `OpenRouterModel(api_key=...)`.
  - Uses a hardcoded base URL: `https://openrouter.ai/api/v1`.

## Usage
```python
from naas_abi_marketplace.applications.openrouter.models.OpenRouterModel import OpenRouterModel

openrouter = OpenRouterModel(api_key="YOUR_OPENROUTER_API_KEY")
llm = openrouter.get_model("openai/gpt-4o-mini")
```

## Caveats
- No validation is performed on `api_key` or `model_id`; errors will surface when using the returned `ChatOpenAI` client.
- The base URL is fixed and not configurable via the public API.
