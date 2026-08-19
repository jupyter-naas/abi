# `Gpt54Model`

## What it is
- A model definition that registers the OpenRouter-hosted **OpenAI `openai/gpt-5.4`** chat model using `langchain_openai.ChatOpenAI`.
- Exposes a ready-to-use `ChatModel` instance (`model`) configured with OpenRouter base URL and an API key read from the ABI module configuration.

## Public API
- `class Gpt54Model(ModelDefinition)`
  - Static metadata:
    - `CANONICAL_ID = CanonicalModelId.GPT_5_4`
    - `MODEL_ID = "openai/gpt-5.4"`
    - `PROVIDER = ModelProvider.OPENROUTER`
  - `model: ChatModel`
    - A preconfigured `ChatModel` that wraps a `ChatOpenAI` client:
      - `temperature=0`
      - `timeout=120`
      - `max_retries=3`
      - `base_url="https://openrouter.ai/api/v1"`
      - `api_key=SecretStr(ABIModule.get_instance().configuration.openrouter_api_key)`
- Module-level:
  - `OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"`
  - `model: ChatModel = Gpt54Model.model` (convenience alias)

## Configuration/Dependencies
- Dependencies:
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` (`ChatModel`, `ModelDefinition`, `CanonicalModelId`, `ModelProvider`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`
- Required configuration:
  - `ABIModule.get_instance().configuration.openrouter_api_key` must be set (used to authenticate to OpenRouter).

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.openai.gpt_5_4 import model

# The underlying LangChain client is available as `model.model`
llm = model.model

# Example invocation (LangChain-style); message types depend on your LangChain version
result = llm.invoke("Say hello in one sentence.")
print(result)
```

## Caveats
- The API key is fetched at import/construction time from `ABIModule` configuration; missing/invalid configuration will prevent successful requests.
- The configured base URL targets OpenRouter (`https://openrouter.ai/api/v1`), not OpenAI’s direct API endpoint.
