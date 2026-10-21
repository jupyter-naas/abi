# MistralMedium3Model

## What it is
- A `ModelDefinition` that registers/configures the **Mistral Medium 3** chat model for use via **OpenRouter** using `langchain_openai.ChatOpenAI`.
- Exposes a ready-to-use `ChatModel` instance as a module-level `model`.

## Public API
- `class MistralMedium3Model(ModelDefinition)`
  - Static identifiers:
    - `CANONICAL_ID`: `CanonicalModelId.MISTRAL_MEDIUM_3`
    - `MODEL_ID`: `"mistralai/mistral-medium-3"`
    - `PROVIDER`: `ModelProvider.OPENROUTER`
  - `model: ChatModel`
    - Preconfigured `ChatModel` wrapping a `ChatOpenAI` client:
      - `temperature=0`
      - `timeout=120`
      - `max_retries=3`
      - `base_url="https://openrouter.ai/api/v1"`
      - `api_key` sourced from `ABIModule.get_instance().configuration.openrouter_api_key`
    - Metadata includes `context_window=131072`, pricing, architecture, supported/default parameters, etc.
- `model: ChatModel`
  - Module-level alias for `MistralMedium3Model.model`.

## Configuration/Dependencies
- Requires `langchain_openai.ChatOpenAI`.
- Requires NAAS ABI core model types:
  - `CanonicalModelId`, `ChatModel`, `ModelDefinition`, `ModelProvider`
- Requires `naas_abi_marketplace.ai.openrouter.ABIModule` to provide:
  - `ABIModule.get_instance().configuration.openrouter_api_key`
- Uses `pydantic.SecretStr` for the API key.
- OpenRouter endpoint:
  - `OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.mistral.mistral_medium_3 import model

# Access the underlying LangChain chat model
llm = model.model  # ChatOpenAI instance

# Example invocation (LangChain API)
response = llm.invoke("Say hello in one sentence.")
print(response)
```

## Caveats
- Importing this module constructs the `ChatOpenAI` client immediately and reads the OpenRouter API key from `ABIModule` configuration; ensure configuration is available before import.
