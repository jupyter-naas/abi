# O4MiniHighModel

## What it is
- Defines a `ModelDefinition` for the OpenRouter-hosted **OpenAI `o4-mini-high`** chat model.
- Exposes a preconfigured `ChatModel` instance (LangChain `ChatOpenAI`) with fixed defaults (timeouts, retries, base URL, etc.).

## Public API
- `class O4MiniHighModel(ModelDefinition)`
  - Purpose: Holds metadata and a configured `ChatModel` for `openai/o4-mini-high` via OpenRouter.
  - Public attributes:
    - `CANONICAL_ID`: `CanonicalModelId.O4_MINI_HIGH`
    - `MODEL_ID`: `"openai/o4-mini-high"`
    - `PROVIDER`: `ModelProvider.OPENROUTER`
    - `model: ChatModel`: The configured chat model object.
- `model: ChatModel`
  - Module-level alias to `O4MiniHighModel.model`.

## Configuration/Dependencies
- Dependencies:
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` (`ChatModel`, `ModelDefinition`, `CanonicalModelId`, `ModelProvider`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`
- Configuration:
  - Reads API key from: `ABIModule.get_instance().configuration.openrouter_api_key`
  - Uses OpenRouter base URL: `https://openrouter.ai/api/v1`
- Fixed model client settings (`ChatOpenAI`):
  - `temperature=0`
  - `timeout=120`
  - `max_retries=3`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.openai.o4_mini_high import model

# LangChain ChatOpenAI is available at:
llm = model.model

# Example invocation (requires OpenRouter API key configured in ABIModule):
response = llm.invoke("Hello!")
print(response)
```

## Caveats
- Requires `ABIModule` to be correctly initialized/configured with `openrouter_api_key`; otherwise model construction may fail at import time.
- The module configures `ChatOpenAI` at import; changing API keys after import will not affect the already-created instance.
