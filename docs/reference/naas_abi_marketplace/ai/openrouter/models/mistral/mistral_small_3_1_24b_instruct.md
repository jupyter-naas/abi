# MistralSmall3124bInstructModel

## What it is
- A model definition that registers/configures the **Mistral Small 3.1 24B Instruct** chat model for use via **OpenRouter**, using `langchain_openai.ChatOpenAI`.
- Exposes a ready-to-use `ChatModel` instance (`model`) configured with API key, base URL, and default runtime parameters.

## Public API
- `class MistralSmall3124bInstructModel(ModelDefinition)`
  - Purpose: Defines metadata and a `ChatModel` wrapper for the OpenRouter-hosted model.
  - Public class attributes:
    - `CANONICAL_ID`: `CanonicalModelId.MISTRAL_SMALL_3_1_24B_INSTRUCT`
    - `MODEL_ID`: `"mistralai/mistral-small-3.1-24b-instruct"`
    - `PROVIDER`: `ModelProvider.OPENROUTER`
  - Public field:
    - `model: ChatModel`: Configured `ChatModel` instance (includes underlying `ChatOpenAI` client and model metadata).

- `model: ChatModel`
  - Purpose: Module-level alias to `MistralSmall3124bInstructModel.model` for convenient importing.

## Configuration/Dependencies
- Depends on:
  - `langchain_openai.ChatOpenAI`
  - `naas_abi_core.models.Model` (`ChatModel`, `ModelDefinition`, `ModelProvider`, `CanonicalModelId`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule` for retrieving `openrouter_api_key`
  - `pydantic.SecretStr`
- Configuration:
  - OpenRouter base URL: `https://openrouter.ai/api/v1`
  - `ChatOpenAI` is instantiated with:
    - `model`: `"mistralai/mistral-small-3.1-24b-instruct"`
    - `temperature`: `0`
    - `timeout`: `120`
    - `max_retries`: `3`
    - `api_key`: `ABIModule.get_instance().configuration.openrouter_api_key`
    - `base_url`: `OPENROUTER_BASE_URL`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.mistral.mistral_small_3_1_24b_instruct import model

# Access the underlying LangChain chat model/client
llm = model.model

# Example invocation (LangChain-style)
response = llm.invoke("Say hello in one short sentence.")
print(response)
```

## Caveats
- Requires `ABIModule.get_instance().configuration.openrouter_api_key` to be set/available at import time (the `ChatOpenAI` client is constructed during module import).
