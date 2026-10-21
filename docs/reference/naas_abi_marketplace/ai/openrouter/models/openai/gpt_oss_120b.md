# GptOss120bModel

## What it is
- A `ModelDefinition` that registers an OpenRouter-backed LangChain `ChatOpenAI` chat model for **`openai/gpt-oss-120b`**.
- Exposes a ready-to-use `ChatModel` instance (`model`) configured with OpenRouter base URL and API key from `ABIModule` configuration.

## Public API
- `class GptOss120bModel(ModelDefinition)`
  - Purpose: Defines metadata and a preconfigured `ChatModel` for the OpenRouter model.
  - Public attributes:
    - `CANONICAL_ID`: `CanonicalModelId.GPT_OSS_120B`
    - `MODEL_ID`: `"openai/gpt-oss-120b"`
    - `PROVIDER`: `ModelProvider.OPENROUTER`
    - `model: ChatModel`: The configured model wrapper, including underlying `ChatOpenAI` client and metadata (context window, pricing, etc.).
- `model: ChatModel`
  - Purpose: Module-level alias to `GptOss120bModel.model` for convenient imports.

## Configuration/Dependencies
- Dependencies:
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` (`CanonicalModelId`, `ChatModel`, `ModelDefinition`, `ModelProvider`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`
- Configuration requirements:
  - `ABIModule.get_instance().configuration.openrouter_api_key` must be set; it is passed as `api_key=SecretStr(...)`.
- OpenRouter endpoint:
  - `OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.openai.gpt_oss_120b import model

# Access the underlying LangChain ChatOpenAI instance
llm = model.model

# Example call (LangChain v0.1+ style)
resp = llm.invoke("Write a one-sentence summary of Mixture-of-Experts models.")
print(resp)
```

## Caveats
- The API key is pulled at import time via `ABIModule.get_instance().configuration.openrouter_api_key`; importing this module may fail if `ABIModule` is not initialized/configured.
