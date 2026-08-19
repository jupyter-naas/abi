# Ministral8b2512Model

## What it is
- Defines a **ModelDefinition** for the OpenRouter-hosted **Mistral “Ministral 3 8B 2512”** chat model.
- Exposes a preconfigured **LangChain `ChatOpenAI`** client wrapped in a `ChatModel` metadata container.

## Public API
- `class Ministral8b2512Model(ModelDefinition)`
  - Static identifiers:
    - `CANONICAL_ID`: `CanonicalModelId.MINISTRAL_8B_2512`
    - `MODEL_ID`: `"mistralai/ministral-8b-2512"`
    - `PROVIDER`: `ModelProvider.OPENROUTER`
  - `model: ChatModel`
    - Prebuilt `ChatModel` containing:
      - `model`: `langchain_openai.ChatOpenAI(...)` configured for OpenRouter
      - Metadata such as `context_window=262144`, `name`, `owner`, `pricing`, `supported_parameters`, etc.
- Module-level:
  - `model: ChatModel = Ministral8b2512Model.model` (convenience alias)
- Constant:
  - `OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"`

## Configuration/Dependencies
- Dependencies:
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` (`ModelDefinition`, `ChatModel`, `CanonicalModelId`, `ModelProvider`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`
- Configuration source:
  - API key is read from: `ABIModule.get_instance().configuration.openrouter_api_key`
- `ChatOpenAI` client configuration (as defined in code):
  - `model="mistralai/ministral-8b-2512"`
  - `temperature=0`
  - `timeout=120`
  - `max_retries=3`
  - `base_url=OPENROUTER_BASE_URL`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.mistral.ministral_8b_2512 import model

# Access the underlying LangChain chat model
llm = model.model  # ChatOpenAI instance

# Example invocation (requires ABIModule configuration with an OpenRouter API key)
response = llm.invoke("Say hello in one sentence.")
print(response)
```

## Caveats
- Requires `ABIModule` to be initialized/configured with a valid `openrouter_api_key`; otherwise instantiation may fail at import time.
- The module sets `ChatOpenAI(temperature=0)` while `ChatModel.default_parameters` lists `temperature=0.3`; this file does not apply those defaults to the `ChatOpenAI` instance.
