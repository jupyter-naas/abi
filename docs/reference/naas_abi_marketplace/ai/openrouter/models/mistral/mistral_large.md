# `MistralLargeModel`

## What it is
- A `ModelDefinition` that registers/configures the **Mistral Large** chat model (`mistralai/mistral-large`) for use via **OpenRouter** using `langchain_openai.ChatOpenAI`.

## Public API
- `class MistralLargeModel(ModelDefinition)`
  - Constants:
    - `CANONICAL_ID`: `CanonicalModelId.MISTRAL_LARGE`
    - `MODEL_ID`: `"mistralai/mistral-large"`
    - `PROVIDER`: `ModelProvider.OPENROUTER`
  - Attribute:
    - `model: ChatModel` — preconfigured `ChatModel` instance wrapping a `ChatOpenAI` client (temperature, timeouts, retries, base URL, API key).
- Module-level:
  - `model: ChatModel` — alias to `MistralLargeModel.model` for convenient import.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` (`ChatModel`, `ModelDefinition`, `CanonicalModelId`, `ModelProvider`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`
- **Runtime configuration**
  - Reads the OpenRouter API key from:
    - `ABIModule.get_instance().configuration.openrouter_api_key`
  - Uses OpenRouter base URL:
    - `OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.mistral.mistral_large import model

# model.model is the underlying langchain_openai.ChatOpenAI instance
llm = model.model

# Example call (LangChain messages API)
result = llm.invoke("Write a one-line haiku about build systems.")
print(result)
```

## Caveats
- Requires `ABIModule` to be initialized and configured with a valid `openrouter_api_key`; import-time initialization constructs `ChatOpenAI` with that key.
- The `ChatOpenAI` client is configured with:
  - `temperature=0`, `timeout=120`, `max_retries=3`, and `base_url` set to OpenRouter.
