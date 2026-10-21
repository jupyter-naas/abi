# Gpt5Model

## What it is
- Defines an OpenRouter-backed **GPT-5** chat model (`openai/gpt-5`) using `langchain_openai.ChatOpenAI`.
- Exposes a ready-to-use `ChatModel` instance with metadata (context window, pricing, supported parameters, etc.).

## Public API
- `class Gpt5Model(ModelDefinition)`
  - `CANONICAL_ID`: `CanonicalModelId.GPT_5`
  - `MODEL_ID`: `"openai/gpt-5"`
  - `PROVIDER`: `ModelProvider.OPENROUTER`
  - `model: ChatModel`: Preconfigured `ChatModel` wrapping a `ChatOpenAI` client:
    - `temperature=0`, `timeout=120`, `max_retries=3`
    - `base_url="https://openrouter.ai/api/v1"`
    - `api_key` sourced from `ABIModule.get_instance().configuration.openrouter_api_key`
    - `context_window=400000`
- `model: ChatModel`
  - Module-level alias to `Gpt5Model.model`.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` (`ModelDefinition`, `ChatModel`, `CanonicalModelId`, `ModelProvider`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`
- **Configuration**
  - Requires an OpenRouter API key available at:
    - `ABIModule.get_instance().configuration.openrouter_api_key`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.openai.gpt_5 import model

# Use the underlying LangChain ChatOpenAI client
llm = model.model
response = llm.invoke("Say hello.")
print(response)
```

## Caveats
- The API key is fetched at import time when `Gpt5Model.model` is constructed; missing/invalid configuration can fail during import/initialization.
- The module sets `temperature=0` in the `ChatOpenAI` client, while `default_parameters` in metadata include `temperature: None` (metadata vs. instantiated client may differ).
