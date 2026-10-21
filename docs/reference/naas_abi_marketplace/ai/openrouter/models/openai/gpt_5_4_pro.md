# Gpt54ProModel

## What it is
- A model definition that registers the **OpenRouter**-hosted **OpenAI `openai/gpt-5.4-pro`** chat model using `langchain_openai.ChatOpenAI`.
- Exposes a ready-to-use `ChatModel` instance (`model`) preconfigured with base URL, retries, timeout, and API key source.

## Public API
- `class Gpt54ProModel(ModelDefinition)`
  - Static identifiers:
    - `CANONICAL_ID`: `CanonicalModelId.GPT_5_4_PRO`
    - `MODEL_ID`: `"openai/gpt-5.4-pro"`
    - `PROVIDER`: `ModelProvider.OPENROUTER`
  - `model: ChatModel`
    - A `naas_abi_core.models.Model.ChatModel` wrapping a `ChatOpenAI` client configured for OpenRouter.
- `model: ChatModel`
  - Module-level alias to `Gpt54ProModel.model` for convenient import.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_openai.ChatOpenAI`
  - `naas_abi_core.models.Model` (`ChatModel`, `ModelDefinition`, `CanonicalModelId`, `ModelProvider`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`
  - `pydantic.SecretStr`
- **Configuration**
  - Requires `ABIModule.get_instance().configuration.openrouter_api_key` to be set.
  - Uses `OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"`.
- **Client settings (hard-coded)**
  - `temperature=0`
  - `timeout=120`
  - `max_retries=3`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.openai.gpt_5_4_pro import model

# Access the underlying LangChain ChatOpenAI instance
llm = model.model

# Example call (LangChain API; exact method availability depends on your langchain_openai version)
response = llm.invoke("Say hello in one sentence.")
print(response)
```

## Caveats
- The API key is pulled from `ABIModule` at import time; importing this module without a configured `openrouter_api_key` can fail.
- The configured base URL targets OpenRouter (`https://openrouter.ai/api/v1`), not OpenAI’s native API endpoint.
