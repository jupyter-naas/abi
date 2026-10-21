# O3ProModel

## What it is
- Defines an OpenRouter-backed chat model configuration for **`openai/o3-pro`** using `langchain_openai.ChatOpenAI`.
- Exposes a ready-to-use `ChatModel` instance (`model`) with metadata (context window, pricing, supported parameters, etc.).

## Public API
- `class O3ProModel(ModelDefinition)`
  - `CANONICAL_ID`: `CanonicalModelId.O3_PRO`
  - `MODEL_ID`: `"openai/o3-pro"`
  - `PROVIDER`: `ModelProvider.OPENROUTER`
  - `model: ChatModel`: Preconfigured chat model wrapping a `ChatOpenAI` client:
    - `temperature=0`
    - `timeout=120`
    - `max_retries=3`
    - `base_url="https://openrouter.ai/api/v1"`
    - `api_key` read from `ABIModule.get_instance().configuration.openrouter_api_key`
    - `context_window=200000`
    - plus descriptive metadata (name, owner, pricing, supported parameters, etc.)
- `model: ChatModel`
  - Alias for `O3ProModel.model` for convenient import/use.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` (`ModelDefinition`, `ChatModel`, `CanonicalModelId`, `ModelProvider`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`
- **Configuration**
  - Requires `ABIModule.get_instance().configuration.openrouter_api_key` to be set (OpenRouter API key).
- **Network**
  - Uses OpenRouter endpoint: `https://openrouter.ai/api/v1`.

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.openai.o3_pro import model

# Access the underlying LangChain ChatOpenAI client:
llm = model.model

# Example call pattern depends on your LangChain version.
# Typical usage is via the underlying client, e.g.:
result = llm.invoke("Explain what the o3-pro model is in one sentence.")
print(result)
```

## Caveats
- Importing this module constructs the `ChatOpenAI` client immediately and reads the API key from `ABIModule` configuration.
- The `ChatOpenAI` client is configured with `temperature=0`, `timeout=120`, and `max_retries=3` and will use OpenRouter’s base URL.
