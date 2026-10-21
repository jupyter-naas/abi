# Nemotron3Super120bA12bFreeModel

## What it is
- A model definition module that registers/configures an OpenRouter-hosted chat model: **`nvidia/nemotron-3-super-120b-a12b:free`**.
- Provides a ready-to-use `ChatModel` backed by `langchain_openai.ChatOpenAI`.

## Public API
- **`Nemotron3Super120bA12bFreeModel`** (`ModelDefinition`)
  - Holds metadata and a configured **`model: ChatModel`** instance.
  - Key identifiers:
    - `CANONICAL_ID = CanonicalModelId.NEMOTRON_3_SUPER_120B_A12B_FREE`
    - `MODEL_ID = "nvidia/nemotron-3-super-120b-a12b:free"`
    - `PROVIDER = ModelProvider.OPENROUTER`
- **`model: ChatModel`** (module-level)
  - Alias to `Nemotron3Super120bA12bFreeModel.model` for convenient imports.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` (`ChatModel`, `ModelDefinition`, `CanonicalModelId`, `ModelProvider`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`
- **Configuration**
  - Uses OpenRouter base URL: `https://openrouter.ai/api/v1`
  - Reads API key from: `ABIModule.get_instance().configuration.openrouter_api_key`
- **ChatOpenAI client settings**
  - `temperature=0`
  - `timeout=120`
  - `max_retries=3`
  - `base_url=OPENROUTER_BASE_URL`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.nvidia.nemotron_3_super_120b_a12b_free import model

# `model.model` is the underlying LangChain ChatOpenAI instance
llm = model.model

resp = llm.invoke("Say hello in one sentence.")
print(resp)
```

## Caveats
- Requires a valid OpenRouter API key available via `ABIModule` configuration (`openrouter_api_key`).
- The `ChatModel` metadata includes very large context window values; actual limits are also described in `top_provider` (e.g., `context_length`, `max_completion_tokens`).
