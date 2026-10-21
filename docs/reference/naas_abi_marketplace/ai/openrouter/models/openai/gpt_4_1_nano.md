# Gpt41NanoModel

## What it is
- A model definition that registers/configures the **OpenRouter** hosted **OpenAI `gpt-4.1-nano`** chat model using `langchain_openai.ChatOpenAI`.
- Exposes a ready-to-use `ChatModel` instance (`model`) preconfigured with base URL, API key, retries, timeout, and metadata.

## Public API
- `class Gpt41NanoModel(ModelDefinition)`
  - Static identifiers:
    - `CANONICAL_ID`: `CanonicalModelId.GPT_4_1_NANO`
    - `MODEL_ID`: `"openai/gpt-4.1-nano"`
    - `PROVIDER`: `ModelProvider.OPENROUTER`
  - `model: ChatModel`
    - A `ChatModel` wrapper that includes a configured `ChatOpenAI` client and model metadata (context window, pricing, supported parameters, etc.).

- `model: ChatModel`
  - Module-level alias to `Gpt41NanoModel.model` for convenient import/use.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` (`CanonicalModelId`, `ChatModel`, `ModelDefinition`, `ModelProvider`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`

- **Configuration**
  - Uses OpenRouter base URL:
    - `OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"`
  - Reads the API key from:
    - `ABIModule.get_instance().configuration.openrouter_api_key`

- **Client defaults**
  - `temperature=0`
  - `timeout=120`
  - `max_retries=3`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.openai.gpt_4_1_nano import model

# Access the underlying LangChain chat client
llm = model.model

# Example (LangChain): invoke with a simple prompt
result = llm.invoke("Say hello in one short sentence.")
print(result)
```

## Caveats
- Requires `ABIModule` to be properly initialized/configured so `openrouter_api_key` is available.
- The module configures the client to use OpenRouter (`base_url`), not OpenAI’s default endpoint.
