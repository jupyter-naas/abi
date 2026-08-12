# Gpt51CodexMiniModel

## What it is
- A model definition that registers the **OpenRouter**-hosted **OpenAI `gpt-5.1-codex-mini`** chat model as a `ChatModel`.
- Provides a preconfigured `langchain_openai.ChatOpenAI` client (timeout/retries/base URL/API key) and metadata (context window, pricing, supported parameters, etc.).

## Public API
- `class Gpt51CodexMiniModel(ModelDefinition)`
  - Defines a `ChatModel` instance under `Gpt51CodexMiniModel.model`.
  - Class constants:
    - `CANONICAL_ID = CanonicalModelId.GPT_5_1_CODEX_MINI`
    - `MODEL_ID = "openai/gpt-5.1-codex-mini"`
    - `PROVIDER = ModelProvider.OPENROUTER`
- `model: ChatModel`
  - Module-level alias to `Gpt51CodexMiniModel.model`.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` types: `CanonicalModelId`, `ChatModel`, `ModelDefinition`, `ModelProvider`
  - `naas_abi_marketplace.ai.openrouter.ABIModule`
- **Runtime configuration**
  - Reads the OpenRouter API key from:
    - `ABIModule.get_instance().configuration.openrouter_api_key`
  - Uses OpenRouter base URL:
    - `OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"`
- **Client defaults (ChatOpenAI)**
  - `temperature=0`
  - `timeout=120`
  - `max_retries=3`
  - `base_url=OPENROUTER_BASE_URL`
  - `model="openai/gpt-5.1-codex-mini"`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.openai.gpt_5_1_codex_mini import model

# Access the underlying LangChain chat client
llm = model.model

# Example call (requires ABIModule configuration with openrouter_api_key)
result = llm.invoke("Write a short Python function that adds two numbers.")
print(result)
```

## Caveats
- Requires `ABIModule` to be initialized/configured with `openrouter_api_key`; otherwise model construction may fail at import time.
- Network calls go to OpenRouter (`https://openrouter.ai/api/v1`) and depend on OpenRouter/OpenAI model availability and account limits.
