# GptOss120bFreeModel

## What it is
- A `ModelDefinition` that registers/configures the OpenRouter-hosted chat model `openai/gpt-oss-120b:free` using `langchain_openai.ChatOpenAI`.
- Exposes a ready-to-use `ChatModel` instance via both the class attribute `GptOss120bFreeModel.model` and the module-level variable `model`.

## Public API
- `class GptOss120bFreeModel(ModelDefinition)`
  - Purpose: Defines metadata and the instantiated LangChain chat client for the model.
  - Public attributes:
    - `CANONICAL_ID`: `CanonicalModelId.GPT_OSS_120B_FREE`
    - `MODEL_ID`: `"openai/gpt-oss-120b:free"`
    - `PROVIDER`: `ModelProvider.OPENROUTER`
    - `model: ChatModel`: Fully configured `ChatModel` wrapper.
- `model: ChatModel`
  - Purpose: Convenience alias to `GptOss120bFreeModel.model`.

## Configuration/Dependencies
- **Base URL**
  - `OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"`
- **API key source**
  - Pulled from: `ABIModule.get_instance().configuration.openrouter_api_key`
  - Passed to LangChain as: `api_key=SecretStr(...)`
- **Client implementation**
  - Uses `langchain_openai.ChatOpenAI` with:
    - `model="openai/gpt-oss-120b:free"`
    - `temperature=0`
    - `timeout=120`
    - `max_retries=3`
    - `base_url=OPENROUTER_BASE_URL`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.openai.gpt_oss_120b_free import model

# The underlying LangChain chat model (ChatOpenAI instance)
llm = model.model

# Use it as a normal LangChain chat model
response = llm.invoke("Say hello in one sentence.")
print(response)
```

## Caveats
- Requires `ABIModule` to be initialized/configured so `configuration.openrouter_api_key` is available.
- The `model` object is created at import time, so missing/invalid configuration can fail during import.
