# Nemotron3Super120bA12bModel

## What it is
- A model definition that registers/configures the **NVIDIA Nemotron 3 Super 120B A12B** chat model for use via **OpenRouter** using `langchain_openai.ChatOpenAI`.
- Exposes a ready-to-use `ChatModel` instance (`model`) preconfigured with OpenRouter base URL and API key.

## Public API
- `class Nemotron3Super120bA12bModel(ModelDefinition)`
  - Purpose: Holds metadata and a configured `ChatModel` for `nvidia/nemotron-3-super-120b-a12b`.
  - Public attributes:
    - `CANONICAL_ID`: `CanonicalModelId.NEMOTRON_3_SUPER_120B_A12B`
    - `MODEL_ID`: `"nvidia/nemotron-3-super-120b-a12b"`
    - `PROVIDER`: `ModelProvider.OPENROUTER`
    - `model: ChatModel`: The configured chat model wrapper (includes a `ChatOpenAI` instance).
- `model: ChatModel`
  - Purpose: Module-level shortcut to `Nemotron3Super120bA12bModel.model`.

## Configuration/Dependencies
- Depends on:
  - `langchain_openai.ChatOpenAI`
  - `naas_abi_core.models.Model` (`ChatModel`, `ModelDefinition`, `CanonicalModelId`, `ModelProvider`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule` for retrieving `openrouter_api_key`
  - `pydantic.SecretStr`
- OpenRouter configuration:
  - Base URL: `https://openrouter.ai/api/v1` (`OPENROUTER_BASE_URL`)
  - API key source: `ABIModule.get_instance().configuration.openrouter_api_key`
- `ChatOpenAI` is instantiated with:
  - `model=<MODEL_ID>`
  - `temperature=0`
  - `timeout=120`
  - `max_retries=3`
  - `base_url=OPENROUTER_BASE_URL`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.nvidia.nemotron_3_super_120b_a12b import model

# `model.model` is the underlying langchain ChatOpenAI instance
llm = model.model

# Example call style depends on your langchain version; this is a common pattern:
result = llm.invoke("Write a one-sentence summary of Nemotron 3 Super.")
print(result)
```

## Caveats
- Requires a valid OpenRouter API key available at `ABIModule.get_instance().configuration.openrouter_api_key`.
- The `ChatModel` metadata fields (e.g., `context_window=1000000`) may differ from provider-specific limits (e.g., `top_provider['context_length']=262144`).
