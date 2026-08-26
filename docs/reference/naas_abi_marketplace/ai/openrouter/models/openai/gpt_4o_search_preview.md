# `Gpt4oSearchPreviewModel`

## What it is
- A `ModelDefinition` that registers an OpenRouter-hosted OpenAI model (`openai/gpt-4o-search-preview`) as a `ChatModel`.
- Uses `langchain_openai.ChatOpenAI` configured for OpenRouter’s API endpoint.

## Public API
- `class Gpt4oSearchPreviewModel(ModelDefinition)`
  - `CANONICAL_ID`: `CanonicalModelId.GPT_4O_SEARCH_PREVIEW`
  - `MODEL_ID`: `"openai/gpt-4o-search-preview"`
  - `PROVIDER`: `ModelProvider.OPENROUTER`
  - `model: ChatModel`: Fully constructed chat model definition, including:
    - `model`: a `ChatOpenAI` instance (temperature `0`, timeout `120`, max retries `3`)
    - `context_window`: `128000`
    - metadata (name/owner/description/slug/pricing/etc.)
- `model: ChatModel`
  - Module-level alias to `Gpt4oSearchPreviewModel.model`.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_marketplace.ai.openrouter.ABIModule`
  - `naas_abi_core.models.Model` types: `CanonicalModelId`, `ChatModel`, `ModelDefinition`, `ModelProvider`
- **Configuration**
  - Requires `ABIModule.get_instance().configuration.openrouter_api_key` to be set.
- **Endpoint**
  - OpenRouter base URL: `https://openrouter.ai/api/v1`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.openai.gpt_4o_search_preview import model

# Access the underlying LangChain chat model
llm = model.model

# Example call (method name depends on your LangChain version)
# e.g., llm.invoke("Search for the latest ...") or llm.predict(...)
response = llm.invoke("Find and summarize recent info about GPT-4o search preview.")
print(response)
```

## Caveats
- Importing this module constructs `ChatOpenAI` immediately and reads the OpenRouter API key from `ABIModule` configuration; missing/invalid configuration will break at import time.
- Supported parameters are declared in `supported_parameters` (e.g., `web_search_options`), but parameter handling depends on the underlying `ChatOpenAI`/LangChain integration.
