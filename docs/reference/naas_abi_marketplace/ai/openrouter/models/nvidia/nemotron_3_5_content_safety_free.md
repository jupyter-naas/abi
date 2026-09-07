# Nemotron35ContentSafetyFreeModel

## What it is
- A model definition module that registers/configures NVIDIA’s **Nemotron 3.5 Content Safety (free)** chat model for use via **OpenRouter**.
- Exposes a ready-to-use `ChatModel` instance configured with `langchain_openai.ChatOpenAI`.

## Public API
- `class Nemotron35ContentSafetyFreeModel(ModelDefinition)`
  - Purpose: provides metadata and a configured `ChatModel` for `nvidia/nemotron-3.5-content-safety:free`.
  - Class attributes:
    - `CANONICAL_ID`: `CanonicalModelId.NEMOTRON_3_5_CONTENT_SAFETY_FREE`
    - `MODEL_ID`: `"nvidia/nemotron-3.5-content-safety:free"`
    - `PROVIDER`: `ModelProvider.OPENROUTER`
  - Field:
    - `model: ChatModel`: preconfigured `ChatModel` wrapping a `ChatOpenAI` client (temperature=0, timeout=120, max_retries=3, base_url set to OpenRouter).
- Module-level:
  - `model: ChatModel`
    - Purpose: convenience alias to `Nemotron35ContentSafetyFreeModel.model`.

## Configuration/Dependencies
- Depends on:
  - `langchain_openai.ChatOpenAI`
  - `naas_abi_core.models.Model` (`ModelDefinition`, `ChatModel`, `CanonicalModelId`, `ModelProvider`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule` for configuration access
  - `pydantic.SecretStr`
- Requires configuration:
  - `ABIModule.get_instance().configuration.openrouter_api_key` must be set; it is passed as the OpenRouter API key.
- Uses OpenRouter base URL:
  - `https://openrouter.ai/api/v1`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.nvidia.nemotron_3_5_content_safety_free import model

# Access underlying LangChain ChatOpenAI client if needed
llm = model.model

# Example invocation (LangChain API)
result = llm.invoke("Check this text for policy compliance.")
print(result)
```

## Caveats
- API key must be available via `ABIModule` configuration; otherwise initialization will fail at import time.
- The module configures `temperature=0`, `timeout=120`, and `max_retries=3` and sets `base_url` to OpenRouter; adjust by defining a different model definition if you need other settings.
