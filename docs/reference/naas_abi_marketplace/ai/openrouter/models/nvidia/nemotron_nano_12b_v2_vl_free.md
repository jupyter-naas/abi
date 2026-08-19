# NemotronNano12bV2VlFreeModel

## What it is
- A `ModelDefinition` that registers an OpenRouter-backed `ChatOpenAI` chat model for **`nvidia/nemotron-nano-12b-v2-vl:free`**.
- Exposes a ready-to-use `ChatModel` instance (`model`) configured with:
  - `temperature=0`, `timeout=120`, `max_retries=3`
  - OpenRouter base URL: `https://openrouter.ai/api/v1`
  - API key sourced from `ABIModule.get_instance().configuration.openrouter_api_key`

## Public API
- `class NemotronNano12bV2VlFreeModel(ModelDefinition)`
  - Purpose: Defines metadata and the instantiated `ChatModel` for this OpenRouter model.
  - Public attributes:
    - `CANONICAL_ID`: `CanonicalModelId.NEMOTRON_NANO_12B_V2_VL_FREE`
    - `MODEL_ID`: `"nvidia/nemotron-nano-12b-v2-vl:free"`
    - `PROVIDER`: `ModelProvider.OPENROUTER`
    - `model`: `ChatModel` (fully configured instance)
- `model: ChatModel`
  - Purpose: Module-level alias to `NemotronNano12bV2VlFreeModel.model`.

## Configuration/Dependencies
- Dependencies:
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` (`ModelDefinition`, `ChatModel`, `CanonicalModelId`, `ModelProvider`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`
- Required configuration:
  - `ABIModule.get_instance().configuration.openrouter_api_key` must be set (used to create `SecretStr(...)` for `ChatOpenAI`).

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.nvidia.nemotron_nano_12b_v2_vl_free import model

# Access the underlying LangChain chat model
llm = model.model

# Example invocation (LangChain API)
result = llm.invoke("Hello! Summarize what you can do.")
print(result)
```

## Caveats
- The OpenRouter API key is fetched at import time via `ABIModule.get_instance()...`; missing/misconfigured credentials can cause initialization errors when importing this module.
- The `ChatOpenAI` instance is configured with `base_url` pointing to OpenRouter, not OpenAI.
