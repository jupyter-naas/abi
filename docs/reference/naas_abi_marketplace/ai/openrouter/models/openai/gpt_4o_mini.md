# Gpt4oMiniModel

## What it is
- A model definition that registers OpenRouter’s `openai/gpt-4o-mini` as a `ChatModel` using LangChain’s `ChatOpenAI`.
- Exposes a preconfigured `ChatOpenAI` client (temperature 0, timeout 120s, retries 3) targeting OpenRouter’s API base URL.

## Public API
- `class Gpt4oMiniModel(ModelDefinition)`
  - `CANONICAL_ID`: `CanonicalModelId.GPT_4O_MINI`
  - `MODEL_ID`: `"openai/gpt-4o-mini"`
  - `PROVIDER`: `ModelProvider.OPENROUTER`
  - `model: ChatModel`
    - A `ChatModel` instance containing:
      - `model_id`, `provider`
      - `model`: a configured `langchain_openai.ChatOpenAI`
      - metadata such as `context_window`, `name`, `owner`, `created_at`, pricing, supported parameters, etc.
- `model: ChatModel`
  - Module-level alias to `Gpt4oMiniModel.model`.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` types: `ChatModel`, `ModelDefinition`, `ModelProvider`, `CanonicalModelId`
  - `naas_abi_marketplace.ai.openrouter.ABIModule`
- **Configuration**
  - Requires an OpenRouter API key retrieved from:
    - `ABIModule.get_instance().configuration.openrouter_api_key`
  - Uses OpenRouter base URL:
    - `https://openrouter.ai/api/v1`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.openai.gpt_4o_mini import model

# Access the underlying LangChain ChatOpenAI client
llm = model.model

# Example call shape (depends on langchain_openai / langchain versions)
# response = llm.invoke("Hello!")
# print(response)
print(model.model_id, model.provider)
```

## Caveats
- Importing this module will attempt to read `openrouter_api_key` from `ABIModule` configuration; missing/invalid configuration may raise errors during import or client initialization.
- The module defines a LangChain `ChatOpenAI` client pointing at OpenRouter; behavior and invocation APIs depend on the installed `langchain_openai`/LangChain versions.
