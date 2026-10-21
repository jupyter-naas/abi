# Gpt51ChatModel

## What it is
- A model definition that registers/configures the **OpenRouter** hosted **OpenAI `openai/gpt-5.1-chat`** chat model using `langchain_openai.ChatOpenAI`.
- Exposes a ready-to-use `ChatModel` instance (`model`) with metadata (context window, pricing, supported parameters, etc.).

## Public API
- `class Gpt51ChatModel(ModelDefinition)`
  - Static metadata:
    - `CANONICAL_ID`: `CanonicalModelId.GPT_5_1_CHAT`
    - `MODEL_ID`: `"openai/gpt-5.1-chat"`
    - `PROVIDER`: `ModelProvider.OPENROUTER`
  - `model: ChatModel`
    - A configured `ChatModel` wrapping a `ChatOpenAI` client:
      - `model="openai/gpt-5.1-chat"`
      - `temperature=0`
      - `timeout=120`
      - `max_retries=3`
      - `api_key=SecretStr(ABIModule.get_instance().configuration.openrouter_api_key)`
      - `base_url="https://openrouter.ai/api/v1"`
- Module-level:
  - `OPENROUTER_BASE_URL`: `"https://openrouter.ai/api/v1"`
  - `model: ChatModel`: alias to `Gpt51ChatModel.model`

## Configuration/Dependencies
- Requires an OpenRouter API key available via:
  - `ABIModule.get_instance().configuration.openrouter_api_key`
- Key dependencies:
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` (`ChatModel`, `ModelDefinition`, `CanonicalModelId`, `ModelProvider`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.openai.gpt_5_1_chat import model

# Access the underlying LangChain chat client
llm = model.model

# Then use it as a ChatOpenAI instance in your LangChain flow
print(llm.model_name)  # may vary by langchain_openai version
```

## Caveats
- Importing this module will attempt to read the OpenRouter API key from `ABIModule` configuration; missing/misconfigured keys will break initialization.
- Network calls are not made at import time, but the `ChatOpenAI` client is instantiated immediately.
