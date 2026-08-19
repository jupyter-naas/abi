# Gpt35TurboModel

## What it is
- A model definition for **OpenRouter-hosted** `openai/gpt-3.5-turbo`, exposed as a `ChatModel` configured via `langchain_openai.ChatOpenAI`.
- Provides a ready-to-use `model` object at module level.

## Public API
- `class Gpt35TurboModel(ModelDefinition)`
  - `CANONICAL_ID`: `CanonicalModelId.GPT_3_5_TURBO`
  - `MODEL_ID`: `"openai/gpt-3.5-turbo"`
  - `PROVIDER`: `ModelProvider.OPENROUTER`
  - `model: ChatModel`: Preconfigured chat model (LangChain `ChatOpenAI`) with metadata (context window, pricing, etc.).
- `model: ChatModel`
  - Alias to `Gpt35TurboModel.model` for convenient imports.

## Configuration/Dependencies
- **Environment/config source**
  - Reads the OpenRouter API key from: `ABIModule.get_instance().configuration.openrouter_api_key`
- **Network endpoint**
  - Uses `OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"`
- **Key dependencies**
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` types (`ChatModel`, `ModelDefinition`, etc.)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.openai.gpt_3_5_turbo import model

# Access the underlying LangChain ChatOpenAI instance
llm = model.model

# Example invocation (LangChain-style)
result = llm.invoke("Say hello in one sentence.")
print(result)
```

## Caveats
- API key must be available via `ABIModule` configuration (`openrouter_api_key`), otherwise instantiation will fail.
- The `ChatOpenAI` client is configured with:
  - `temperature=0`, `timeout=120`, `max_retries=3`
  - `base_url` set to OpenRouter (not OpenAI’s default).
