# Gpt52CodexModel

## What it is
- Defines a `ModelDefinition` for the **OpenRouter**-hosted **OpenAI GPT-5.2-Codex** chat model.
- Exposes a ready-to-use `ChatModel` instance configured with `langchain_openai.ChatOpenAI`.

## Public API
- `class Gpt52CodexModel(ModelDefinition)`
  - `CANONICAL_ID`: `CanonicalModelId.GPT_5_2_CODEX`
  - `MODEL_ID`: `"openai/gpt-5.2-codex"`
  - `PROVIDER`: `ModelProvider.OPENROUTER`
  - `model: ChatModel`: preconfigured chat model definition (includes LangChain `ChatOpenAI` client and metadata).
- `model: ChatModel`
  - Module-level alias to `Gpt52CodexModel.model`.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` types: `ModelDefinition`, `ChatModel`, `CanonicalModelId`, `ModelProvider`
  - `naas_abi_marketplace.ai.openrouter.ABIModule` (for configuration access)
- **Runtime configuration**
  - Requires `ABIModule.get_instance().configuration.openrouter_api_key` to be available.
- **OpenRouter endpoint**
  - `OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.openai.gpt_5_2_codex import model

# Access the underlying LangChain ChatOpenAI client
llm = model.model

# Example call pattern (LangChain v0.1+ style)
result = llm.invoke("Write a Python function to compute Fibonacci numbers.")
print(result)
```

## Caveats
- The API key is pulled from `ABIModule` configuration at import time; missing/invalid configuration will fail during initialization.
- Client defaults are fixed in code: `temperature=0`, `timeout=120`, `max_retries=3`, `base_url` set to OpenRouter.
