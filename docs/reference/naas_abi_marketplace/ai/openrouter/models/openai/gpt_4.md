# Gpt4Model

## What it is
- A model definition that registers OpenAI **GPT-4** via the **OpenRouter** provider, implemented using `langchain_openai.ChatOpenAI`.
- Exposes a preconfigured `ChatModel` instance (`model`) for use elsewhere in the package.

## Public API
- **`class Gpt4Model(ModelDefinition)`**
  - Static metadata:
    - `CANONICAL_ID = CanonicalModelId.GPT_4`
    - `MODEL_ID = "openai/gpt-4"`
    - `PROVIDER = ModelProvider.OPENROUTER`
  - **`model: ChatModel`**
    - A configured `ChatModel` wrapping a `ChatOpenAI` client:
      - `temperature=0`
      - `timeout=120`
      - `max_retries=3`
      - `base_url="https://openrouter.ai/api/v1"`
      - `api_key` read from `ABIModule.get_instance().configuration.openrouter_api_key`
    - Includes metadata such as `context_window=8191`, `pricing`, `supported_parameters`, and `created_at`.

- **`model: ChatModel` (module-level)**
  - Alias to `Gpt4Model.model` for convenience.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` (`ChatModel`, `ModelDefinition`, `ModelProvider`, `CanonicalModelId`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule` (to fetch configuration)

- **Required configuration**
  - `ABIModule.get_instance().configuration.openrouter_api_key` must be set (used as the OpenRouter API key).

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.openai.gpt_4 import model

# Access the underlying LangChain ChatOpenAI client
llm = model.model

# Example call (method availability depends on langchain_openai version)
# result = llm.invoke("Hello!")
# print(result)
```

## Caveats
- The API key is loaded at import time via `ABIModule.get_instance()`. If the OpenRouter configuration is not initialized, importing this module may fail.
- The configured `context_window` is `8191`, and `top_provider` metadata indicates `max_completion_tokens=4096` (metadata only; enforcement depends on downstream usage).
