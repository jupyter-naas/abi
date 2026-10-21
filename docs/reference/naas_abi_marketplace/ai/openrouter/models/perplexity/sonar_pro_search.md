# SonarProSearchModel

## What it is
- A model definition that configures a LangChain `ChatOpenAI` client to use OpenRouter’s `perplexity/sonar-pro-search` chat model.
- Exposes a ready-to-use `ChatModel` instance via the module-level `model`.

## Public API
- `class SonarProSearchModel(ModelDefinition)`
  - `CANONICAL_ID`: `CanonicalModelId.SONAR_PRO_SEARCH`
  - `MODEL_ID`: `"perplexity/sonar-pro-search"`
  - `PROVIDER`: `ModelProvider.OPENROUTER`
  - `model: ChatModel`: Preconfigured chat model wrapper around `ChatOpenAI` with:
    - `temperature=0`
    - `timeout=120`
    - `max_retries=3`
    - `base_url="https://openrouter.ai/api/v1"`
    - `api_key` read from `ABIModule.get_instance().configuration.openrouter_api_key`
- `model: ChatModel`
  - Alias to `SonarProSearchModel.model` for convenient import/use.

## Configuration/Dependencies
- Depends on:
  - `langchain_openai.ChatOpenAI`
  - `naas_abi_core.models.Model` (`ChatModel`, `ModelDefinition`, `CanonicalModelId`, `ModelProvider`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule` (for `openrouter_api_key`)
  - `pydantic.SecretStr`
- Requires an OpenRouter API key available at:
  - `ABIModule.get_instance().configuration.openrouter_api_key`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.perplexity.sonar_pro_search import model

# Use the underlying LangChain chat model
llm = model.model
resp = llm.invoke("Find recent info about OpenRouter and summarize in 3 bullets.")
print(resp.content)
```

## Caveats
- The API key is obtained at import time; importing this module will attempt to read `ABIModule` configuration immediately.
