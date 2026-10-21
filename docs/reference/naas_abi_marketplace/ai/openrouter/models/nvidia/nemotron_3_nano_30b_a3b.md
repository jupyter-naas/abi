# Nemotron3Nano30bA3bModel

## What it is
- A model definition that registers/configures the OpenRouter-hosted **NVIDIA Nemotron 3 Nano 30B A3B** chat model for use via `langchain_openai.ChatOpenAI`.
- Exposes a ready-to-use `ChatModel` instance with metadata (context window, pricing, etc.) and an underlying LangChain chat client.

## Public API
- `class Nemotron3Nano30bA3bModel(ModelDefinition)`
  - Purpose: Defines the canonical model identifiers and provides a configured `ChatModel` instance.
  - Public attributes:
    - `CANONICAL_ID`: `CanonicalModelId.NEMOTRON_3_NANO_30B_A3B`
    - `MODEL_ID`: `"nvidia/nemotron-3-nano-30b-a3b"`
    - `PROVIDER`: `ModelProvider.OPENROUTER`
    - `model: ChatModel`: Preconfigured chat model wrapper containing:
      - `model`: `ChatOpenAI(model=..., temperature=0, timeout=120, max_retries=3, api_key=..., base_url="https://openrouter.ai/api/v1")`
      - `context_window=262144`
      - Metadata such as `name`, `owner`, `pricing`, `supported_parameters`, etc.
- `model: ChatModel`
  - Purpose: Module-level alias to `Nemotron3Nano30bA3bModel.model` for convenient imports.

## Configuration/Dependencies
- Dependencies:
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` (`ChatModel`, `ModelDefinition`, `CanonicalModelId`, `ModelProvider`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`
- Configuration source:
  - Reads the OpenRouter API key from:
    - `ABIModule.get_instance().configuration.openrouter_api_key`
- OpenRouter endpoint:
  - `OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.nvidia.nemotron_3_nano_30b_a3b import model

# LangChain chat model client is available at model.model
response = model.model.invoke("Say hello in one sentence.")
print(response)
```

## Caveats
- Importing this module constructs the `ChatOpenAI` client immediately and requires `ABIModule.get_instance().configuration.openrouter_api_key` to be available at import time.
- The client is configured with `temperature=0`, `timeout=120`, and `max_retries=3` as fixed defaults in this file.
