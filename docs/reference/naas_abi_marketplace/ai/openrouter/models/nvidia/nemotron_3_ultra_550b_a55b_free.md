# Nemotron3Ultra550bA55bFreeModel

## What it is
- A `ModelDefinition` that registers/configures the OpenRouter chat model **`nvidia/nemotron-3-ultra-550b-a55b:free`** for use via `langchain_openai.ChatOpenAI`.
- Exposes a ready-to-use `ChatModel` instance (`model`) with metadata (context window, pricing, supported parameters, etc.).

## Public API
- `class Nemotron3Ultra550bA55bFreeModel(ModelDefinition)`
  - Purpose: Defines a canonical model entry and constructs a `ChatModel` backed by `ChatOpenAI`.
  - Public attributes:
    - `CANONICAL_ID`: `CanonicalModelId.NEMOTRON_3_ULTRA_550B_A55B_FREE`
    - `MODEL_ID`: `"nvidia/nemotron-3-ultra-550b-a55b:free"`
    - `PROVIDER`: `ModelProvider.OPENROUTER`
    - `model: ChatModel`: Preconfigured chat model wrapper (includes the underlying `ChatOpenAI` instance and model metadata).
- Module-level:
  - `OPENROUTER_BASE_URL`: `"https://openrouter.ai/api/v1"`
  - `model: ChatModel`: Alias to `Nemotron3Ultra550bA55bFreeModel.model`

## Configuration/Dependencies
- Dependencies:
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` (`CanonicalModelId`, `ChatModel`, `ModelDefinition`, `ModelProvider`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule` (used to fetch configuration)
- Required configuration:
  - `ABIModule.get_instance().configuration.openrouter_api_key` must be set; it is passed into `ChatOpenAI(api_key=SecretStr(...))`.
- Runtime configuration baked into `ChatOpenAI`:
  - `model`: `"nvidia/nemotron-3-ultra-550b-a55b:free"`
  - `base_url`: `https://openrouter.ai/api/v1`
  - `temperature`: `0`
  - `timeout`: `120`
  - `max_retries`: `3`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.nvidia.nemotron_3_ultra_550b_a55b_free import model

# ChatModel wraps a langchain ChatOpenAI instance at model.model
llm = model.model

resp = llm.invoke("Say hello in one short sentence.")
print(resp)
```

## Caveats
- This module assumes OpenRouter credentials are available via `ABIModule` configuration; missing/invalid API keys will cause runtime failures when invoking the model.
- The `ChatModel` metadata includes a `context_window` of `1000000`; actual usable context and completion limits may be constrained by the upstream provider (`top_provider` metadata indicates `max_completion_tokens=65536`).
