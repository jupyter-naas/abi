# O4MiniDeepResearchModel

## What it is
- A model definition that registers the **OpenRouter-hosted** `openai/o4-mini-deep-research` chat model using `langchain_openai.ChatOpenAI`.
- Exposes a ready-to-use `ChatModel` instance (`model`) preconfigured with base URL, retries, timeout, and API key lookup via `ABIModule`.

## Public API
- `class O4MiniDeepResearchModel(ModelDefinition)`
  - Purpose: Defines metadata and the configured `ChatModel` for the canonical model id `CanonicalModelId.O4_MINI_DEEP_RESEARCH`.
  - Key attributes:
    - `CANONICAL_ID`: `CanonicalModelId.O4_MINI_DEEP_RESEARCH`
    - `MODEL_ID`: `"openai/o4-mini-deep-research"`
    - `PROVIDER`: `ModelProvider.OPENROUTER`
    - `model`: `ChatModel` wrapping a `ChatOpenAI` client configured for OpenRouter.
- `model: ChatModel`
  - Purpose: Module-level alias to `O4MiniDeepResearchModel.model` for convenient imports.

## Configuration/Dependencies
- External dependencies:
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` (`ChatModel`, `ModelDefinition`, `CanonicalModelId`, `ModelProvider`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`
- Configuration:
  - Requires `ABIModule.get_instance().configuration.openrouter_api_key` to be set.
- OpenRouter endpoint:
  - `OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"`
- ChatOpenAI client defaults in this module:
  - `temperature=0`
  - `timeout=120`
  - `max_retries=3`
  - `model="openai/o4-mini-deep-research"`
  - `base_url=OPENROUTER_BASE_URL`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.openai.o4_mini_deep_research import model

# Access the underlying LangChain chat model (ChatOpenAI instance)
llm = model.model

# Example call (method name depends on your LangChain version)
result = llm.invoke("Summarize the main points of the latest paper on X.")
print(result)
```

## Caveats
- The model description notes it **always uses the `web_search` tool**, which may add additional cost.
- API key is pulled from `ABIModule` configuration; if it is missing/invalid, client initialization or calls will fail.
