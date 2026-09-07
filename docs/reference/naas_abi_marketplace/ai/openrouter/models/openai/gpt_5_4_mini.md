# Gpt54MiniModel

## What it is
- Defines a `ModelDefinition` for the OpenRouter-hosted OpenAI model **`openai/gpt-5.4-mini`**.
- Exposes a preconfigured `ChatModel` wrapper around `langchain_openai.ChatOpenAI`.

## Public API
- `class Gpt54MiniModel(ModelDefinition)`
  - `CANONICAL_ID`: `CanonicalModelId.GPT_5_4_MINI`
  - `MODEL_ID`: `"openai/gpt-5.4-mini"`
  - `PROVIDER`: `ModelProvider.OPENROUTER`
  - `model: ChatModel`
    - Prebuilt `ChatModel` with:
      - `model_id`, `provider`, `context_window=400000`, metadata (name/owner/description/etc.)
      - underlying `ChatOpenAI` client configured with `temperature=0`, `timeout=120`, `max_retries=3`, `base_url="https://openrouter.ai/api/v1"`, and API key from `ABIModule` configuration.
- Module-level:
  - `model: ChatModel = Gpt54MiniModel.model` (convenience alias)

## Configuration/Dependencies
- Requires:
  - `langchain_openai.ChatOpenAI`
  - `naas_abi_core.models.Model` (`ChatModel`, `ModelDefinition`, `CanonicalModelId`, `ModelProvider`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule` for retrieving `openrouter_api_key`
  - `pydantic.SecretStr`
- API key source:
  - `ABIModule.get_instance().configuration.openrouter_api_key`
- OpenRouter base URL:
  - Constant `OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.openai.gpt_5_4_mini import model

# Access the underlying LangChain chat client
llm = model.model

# Example call (API key must be configured in ABIModule)
result = llm.invoke("Hello! Summarize what this model is for in one sentence.")
print(result)
```

## Caveats
- Importing this module constructs the `ChatOpenAI` client immediately and reads the OpenRouter API key from `ABIModule` configuration; missing/invalid configuration may fail at import or first use.
