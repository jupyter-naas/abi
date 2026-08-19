# Gpt5NanoModel

## What it is
A `ModelDefinition` that registers an OpenRouter-hosted OpenAI chat model (`openai/gpt-5-nano`) as a `ChatModel` using `langchain_openai.ChatOpenAI`.

## Public API
- `class Gpt5NanoModel(ModelDefinition)`
  - Static identifiers:
    - `CANONICAL_ID`: `CanonicalModelId.GPT_5_NANO`
    - `MODEL_ID`: `"openai/gpt-5-nano"`
    - `PROVIDER`: `ModelProvider.OPENROUTER`
  - `model: ChatModel`
    - A fully constructed `ChatModel` wrapper containing a `ChatOpenAI` client configured for OpenRouter.
- `model: ChatModel`
  - Module-level alias to `Gpt5NanoModel.model` for convenience.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` types: `CanonicalModelId`, `ChatModel`, `ModelDefinition`, `ModelProvider`
  - `naas_abi_marketplace.ai.openrouter.ABIModule`
- **Runtime configuration**
  - Reads OpenRouter API key from:
    - `ABIModule.get_instance().configuration.openrouter_api_key`
  - Uses OpenRouter base URL:
    - `OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"`
- **Client defaults**
  - `temperature=0`, `timeout=120`, `max_retries=3`
  - `context_window=400000`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.openai.gpt_5_nano import model

# Access the underlying LangChain ChatOpenAI client
llm = model.model

# Example call (method name depends on your LangChain version)
result = llm.invoke("Hello! Summarize GPT-5 Nano in one sentence.")
print(result)
```

## Caveats
- Requires `ABIModule` to be properly configured with `openrouter_api_key` at import/runtime; otherwise model construction will fail.
- The module instantiates the `ChatOpenAI` client at import time (as part of class attribute initialization).
