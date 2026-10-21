# Gpt4TurboModel

## What it is
- Defines a `ModelDefinition` for OpenRouter’s `openai/gpt-4-turbo` using `langchain_openai.ChatOpenAI`.
- Exposes a ready-to-use `ChatModel` instance configured with OpenRouter base URL and an API key pulled from `ABIModule` configuration.

## Public API
- `class Gpt4TurboModel(ModelDefinition)`
  - `CANONICAL_ID`: `CanonicalModelId.GPT_4_TURBO`
  - `MODEL_ID`: `"openai/gpt-4-turbo"`
  - `PROVIDER`: `ModelProvider.OPENROUTER`
  - `model: ChatModel`: Preconfigured chat model definition (LangChain `ChatOpenAI` inside).
- `model: ChatModel`
  - Module-level alias to `Gpt4TurboModel.model`.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_openai.ChatOpenAI`
  - `naas_abi_core.models.Model` (`ModelDefinition`, `ChatModel`, `CanonicalModelId`, `ModelProvider`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`
  - `pydantic.SecretStr`
- **Configuration**
  - Uses `ABIModule.get_instance().configuration.openrouter_api_key` as the OpenRouter API key.
  - Uses `OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"` as the `base_url`.
- **ChatOpenAI settings**
  - `temperature=0`, `timeout=120`, `max_retries=3`
  - `model="openai/gpt-4-turbo"`
- **Metadata**
  - `context_window=128000`
  - `pricing={'prompt': '0.00001', 'completion': '0.00003'}`
  - `top_provider={'context_length': 128000, 'max_completion_tokens': 4096, 'is_moderated': True}`
  - `supported_parameters=[...]` (includes tools/function calling and JSON/structured output related params)

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.openai.gpt_4_turbo import model

# Access the underlying LangChain ChatOpenAI instance:
llm = model.model

# Example call (LangChain style):
result = llm.invoke("Say hello in one sentence.")
print(result)
```

## Caveats
- Requires `ABIModule` to be initialized and configured with `openrouter_api_key`; otherwise instantiation may fail when importing the module.
- Network calls and request behavior are governed by `langchain_openai.ChatOpenAI` and the OpenRouter API.
