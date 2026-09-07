# Gpt4oMiniSearchPreviewModel

## What it is
- A `ModelDefinition` that registers an OpenRouter-hosted OpenAI chat model (`openai/gpt-4o-mini-search-preview`) using `langchain_openai.ChatOpenAI`.
- Exposes a preconfigured `ChatModel` instance as a module-level variable `model`.

## Public API
- `class Gpt4oMiniSearchPreviewModel(ModelDefinition)`
  - `CANONICAL_ID`: `CanonicalModelId.GPT_4O_MINI_SEARCH_PREVIEW`
  - `MODEL_ID`: `"openai/gpt-4o-mini-search-preview"`
  - `PROVIDER`: `ModelProvider.OPENROUTER`
  - `model: ChatModel`: A configured chat model wrapper containing:
    - `model`: `ChatOpenAI(...)` configured with `temperature=0`, `timeout=120`, `max_retries=3`, `base_url="https://openrouter.ai/api/v1"`, and API key from `ABIModule` configuration.
    - Metadata such as `context_window=128000`, name/owner/description, created_at, pricing, and supported parameters.
- `model: ChatModel`
  - Module-level alias to `Gpt4oMiniSearchPreviewModel.model`.

## Configuration/Dependencies
- Depends on:
  - `langchain_openai.ChatOpenAI`
  - `naas_abi_core.models.Model` (`ModelDefinition`, `ChatModel`, `CanonicalModelId`, `ModelProvider`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule` for configuration access
  - `pydantic.SecretStr`
- Configuration required:
  - `ABIModule.get_instance().configuration.openrouter_api_key` must be set (used to authenticate to OpenRouter).
- Network endpoint:
  - Base URL is fixed to `https://openrouter.ai/api/v1`.

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.openai.gpt_4o_mini_search_preview import model

# Access the underlying LangChain ChatOpenAI instance
llm = model.model

# Example call shape (exact invocation methods depend on your LangChain version)
result = llm.invoke("Search for the latest Python release and summarize in one sentence.")
print(result)
```

## Caveats
- API key is loaded at import time via `ABIModule.get_instance()`. If the OpenRouter API key is not configured, importing this module may fail.
- The wrapper is configured with `temperature=0`, `timeout=120`, and `max_retries=3` and uses the OpenRouter base URL; these are not parameterized in this module.
