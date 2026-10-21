# NemotronNano9bV2Model

## What it is
- A `ModelDefinition` that registers/configures the **NVIDIA Nemotron Nano 9B V2** chat model for use via **OpenRouter** using `langchain_openai.ChatOpenAI`.
- Exposes a ready-to-use `ChatModel` instance (`model`) with fixed provider/model metadata and OpenRouter connection settings.

## Public API
- **`NemotronNano9bV2Model`** (`ModelDefinition`)
  - Defines:
    - `CANONICAL_ID`: `CanonicalModelId.NEMOTRON_NANO_9B_V2`
    - `MODEL_ID`: `"nvidia/nemotron-nano-9b-v2"`
    - `PROVIDER`: `ModelProvider.OPENROUTER`
  - Provides:
    - `model: ChatModel` — fully constructed chat model including:
      - underlying `ChatOpenAI` client configured with:
        - `model="nvidia/nemotron-nano-9b-v2"`
        - `temperature=0`
        - `timeout=120`
        - `max_retries=3`
        - `base_url="https://openrouter.ai/api/v1"`
        - `api_key` sourced from `ABIModule.get_instance().configuration.openrouter_api_key`
      - metadata like `context_window=131072`, pricing, supported parameters, etc.
- **Module-level `model: ChatModel`**
  - Alias to `NemotronNano9bV2Model.model`.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` (`ModelDefinition`, `ChatModel`, `CanonicalModelId`, `ModelProvider`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`
- **Required configuration**
  - `ABIModule.get_instance().configuration.openrouter_api_key` must be set (used to create the `ChatOpenAI` client).
- **Network**
  - Calls OpenRouter at `https://openrouter.ai/api/v1`.

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.nvidia.nemotron_nano_9b_v2 import model

# Access the underlying LangChain chat client
llm = model.model  # ChatOpenAI instance

# Example invocation (LangChain-style)
response = llm.invoke("Hello! Give me one sentence about Nemotron Nano 9B V2.")
print(response)
```

## Caveats
- The API key is fetched at import/model construction time via `ABIModule.get_instance()`. If the OpenRouter configuration is not initialized, importing/using this module may fail.
- The `ChatOpenAI` client is configured with `temperature=0`, `timeout=120`, and `max_retries=3` and those values are not parameterized in this module.
