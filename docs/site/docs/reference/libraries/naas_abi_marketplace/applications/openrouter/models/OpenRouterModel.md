# OpenRouterModel

## What it is
A small wrapper that constructs a `langchain_openai.ChatOpenAI` client configured to call the OpenRouter API endpoint.

## Public API
- `class OpenRouterModel`
  - `__init__(api_key: str)`
    - Stores the OpenRouter API key and sets the fixed `base_url` to `https://openrouter.ai/api/v1`.
  - `get_model(model_id: str) -> langchain_openai.ChatOpenAI`
    - Returns a `ChatOpenAI` instance configured with:
      - `model=model_id`
      - `api_key=SecretStr(self.api_key)`
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

router = OpenRouterModel(api_key="YOUR_OPENROUTER_API_KEY")
llm = router.get_model("openai/gpt-4o-mini")  # model_id is passed through as-is

# llm is a langchain_openai.ChatOpenAI instance configured for OpenRouter
```

## Caveats
- No validation is performed for `api_key` or `model_id`; invalid values will fail when the returned client is used.
- The base URL is fixed in code and cannot be overridden via the public API.
