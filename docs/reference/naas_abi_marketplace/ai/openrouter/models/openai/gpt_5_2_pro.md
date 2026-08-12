# Gpt52ProModel

## What it is
- A model definition that registers/configures the **OpenRouter** hosted **OpenAI `openai/gpt-5.2-pro`** chat model for use via `langchain_openai.ChatOpenAI`.
- Exposes a prebuilt `ChatModel` instance (`model`) with metadata (context window, pricing, supported parameters, etc.).

## Public API
- `class Gpt52ProModel(ModelDefinition)`
  - `CANONICAL_ID`: `CanonicalModelId.GPT_5_2_PRO`
  - `MODEL_ID`: `"openai/gpt-5.2-pro"`
  - `PROVIDER`: `ModelProvider.OPENROUTER`
  - `model: ChatModel`: Fully constructed `ChatModel` including a `ChatOpenAI` client configured for OpenRouter.
- `model: ChatModel`
  - Module-level alias to `Gpt52ProModel.model`.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` (`ChatModel`, `ModelDefinition`, `ModelProvider`, `CanonicalModelId`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`
- **Configuration**
  - Reads `ABIModule.get_instance().configuration.openrouter_api_key` and passes it as `api_key` (wrapped in `SecretStr`) to `ChatOpenAI`.
  - Uses OpenRouter base URL: `https://openrouter.ai/api/v1`.
- **Client defaults**
  - `temperature=0`, `timeout=120`, `max_retries=3`.

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.openai.gpt_5_2_pro import model

# Access the underlying LangChain client
llm = model.model  # ChatOpenAI instance

# Example call pattern depends on your LangChain version; this shows intent:
# response = llm.invoke("Hello!")
# print(response)
```

## Caveats
- Requires a valid OpenRouter API key available at `ABIModule.get_instance().configuration.openrouter_api_key`.
- The module constructs the `ChatOpenAI` client at import time; importing without proper configuration may fail.
