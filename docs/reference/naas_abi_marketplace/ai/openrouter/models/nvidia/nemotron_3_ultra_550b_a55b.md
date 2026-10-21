# Nemotron3Ultra550bA55bModel

## What it is
- A model definition module that configures an OpenRouter-hosted NVIDIA chat model (`nvidia/nemotron-3-ultra-550b-a55b`) using `langchain_openai.ChatOpenAI`.
- Exposes a ready-to-use `ChatModel` instance (`model`) with metadata (context window, pricing, supported parameters, etc.).

## Public API
- `class Nemotron3Ultra550bA55bModel(ModelDefinition)`
  - Purpose: Declares a canonical model entry and constructs a `ChatModel` configured for OpenRouter.
  - Public attributes:
    - `CANONICAL_ID`: `CanonicalModelId.NEMOTRON_3_ULTRA_550B_A55B`
    - `MODEL_ID`: `"nvidia/nemotron-3-ultra-550b-a55b"`
    - `PROVIDER`: `ModelProvider.OPENROUTER`
    - `model`: `ChatModel` instance wrapping a `ChatOpenAI` client and model metadata.
- `model: ChatModel`
  - Purpose: Convenience export referencing `Nemotron3Ultra550bA55bModel.model`.

## Configuration/Dependencies
- Depends on:
  - `langchain_openai.ChatOpenAI`
  - `naas_abi_core.models.Model` (`ChatModel`, `ModelDefinition`, `CanonicalModelId`, `ModelProvider`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule` for configuration access
  - `pydantic.SecretStr`
- OpenRouter endpoint:
  - `OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"`
- API key source:
  - `ABIModule.get_instance().configuration.openrouter_api_key`
- `ChatOpenAI` client defaults set here:
  - `temperature=0`, `timeout=120`, `max_retries=3`, `base_url=OPENROUTER_BASE_URL`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.nvidia.nemotron_3_ultra_550b_a55b import model

# Access the underlying LangChain chat client
llm = model.model

# Example invocation (requires ABIModule OpenRouter API key configured)
result = llm.invoke("Write a one-sentence summary of mixture-of-experts models.")
print(result)
```

## Caveats
- Requires a valid OpenRouter API key available at `ABIModule.get_instance().configuration.openrouter_api_key`.
- The exported `ChatModel` wraps a LangChain `ChatOpenAI` instance; usage patterns follow LangChain’s chat model interface.
