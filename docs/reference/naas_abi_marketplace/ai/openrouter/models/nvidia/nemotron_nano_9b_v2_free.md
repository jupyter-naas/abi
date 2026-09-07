# NemotronNano9bV2FreeModel

## What it is
- A model definition that registers the OpenRouter-hosted **`nvidia/nemotron-nano-9b-v2:free`** chat model as a `ChatModel`.
- Internally uses `langchain_openai.ChatOpenAI` configured to talk to OpenRouter (`https://openrouter.ai/api/v1`).

## Public API
- `class NemotronNano9bV2FreeModel(ModelDefinition)`
  - Static identifiers:
    - `CANONICAL_ID`: `CanonicalModelId.NEMOTRON_NANO_9B_V2_FREE`
    - `MODEL_ID`: `"nvidia/nemotron-nano-9b-v2:free"`
    - `PROVIDER`: `ModelProvider.OPENROUTER`
  - `model: ChatModel`
    - Preconfigured `ChatModel` instance with metadata (context window, description, pricing, etc.) and an underlying `ChatOpenAI` client.
- `model: ChatModel`
  - Module-level alias to `NemotronNano9bV2FreeModel.model`.

## Configuration/Dependencies
- Depends on:
  - `langchain_openai.ChatOpenAI`
  - `naas_abi_core.models.Model` (`ChatModel`, `ModelDefinition`, `CanonicalModelId`, `ModelProvider`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`
  - `pydantic.SecretStr`
- Requires OpenRouter API key available at:
  - `ABIModule.get_instance().configuration.openrouter_api_key`
- Client configuration:
  - `base_url`: `https://openrouter.ai/api/v1`
  - `temperature`: `0`
  - `timeout`: `120`
  - `max_retries`: `3`
  - `context_window`: `128000`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.nvidia.nemotron_nano_9b_v2_free import model

# Access the underlying LangChain ChatOpenAI client
llm = model.model

# Example (method availability depends on your LangChain version)
result = llm.invoke("Say hello in one sentence.")
print(result)
```

## Caveats
- This module does not set environment variables; it pulls the API key from `ABIModule` configuration. Ensure `ABIModule.get_instance().configuration.openrouter_api_key` is set before importing/using the model.
