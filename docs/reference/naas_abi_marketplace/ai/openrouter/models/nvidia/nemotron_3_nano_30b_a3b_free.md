# Nemotron3Nano30bA3bFreeModel

## What it is
- A `ModelDefinition` that registers and exposes an OpenRouter-hosted chat model (`nvidia/nemotron-3-nano-30b-a3b:free`) using LangChain’s `ChatOpenAI`.
- Provides a ready-to-use `ChatModel` instance (`model`) configured with OpenRouter base URL and API key from `ABIModule` configuration.

## Public API
- `class Nemotron3Nano30bA3bFreeModel(ModelDefinition)`
  - Purpose: Defines metadata and a configured `ChatModel` for the NVIDIA Nemotron 3 Nano 30B A3B (free) model on OpenRouter.
  - Public attributes:
    - `CANONICAL_ID`: `CanonicalModelId.NEMOTRON_3_NANO_30B_A3B_FREE`
    - `MODEL_ID`: `"nvidia/nemotron-3-nano-30b-a3b:free"`
    - `PROVIDER`: `ModelProvider.OPENROUTER`
    - `model`: a `ChatModel` instance wrapping a `ChatOpenAI` client.
- `model: ChatModel`
  - Purpose: Module-level alias to `Nemotron3Nano30bA3bFreeModel.model` for convenient imports.

## Configuration/Dependencies
- Dependencies:
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` (`ModelDefinition`, `ChatModel`, `CanonicalModelId`, `ModelProvider`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`
- Configuration required:
  - `ABIModule.get_instance().configuration.openrouter_api_key` must be set (used to initialize `ChatOpenAI`).
- OpenRouter endpoint:
  - Base URL: `https://openrouter.ai/api/v1`
- Client defaults (as configured in code):
  - `temperature=0`
  - `timeout=120`
  - `max_retries=3`
  - `context_window=256000`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.nvidia.nemotron_3_nano_30b_a3b_free import model

# Access the underlying LangChain ChatOpenAI client
llm = model.model

# Example invocation (LangChain)
response = llm.invoke("Say hello in one sentence.")
print(response)
```

## Caveats
- Requires a valid OpenRouter API key available via `ABIModule` configuration; import-time initialization reads this value.
- The exported `model` is a `ChatModel` wrapper; use `model.model` to access the underlying `ChatOpenAI` instance.
