# Gpt35TurboInstructModel

## What it is
- A predefined **model definition** that configures LangChain’s `ChatOpenAI` client to call **OpenRouter** using the `openai/gpt-3.5-turbo-instruct` model.
- Exposes a ready-to-use `ChatModel` instance (`model`) with metadata (context window, pricing, supported parameters, etc.).

## Public API
- `class Gpt35TurboInstructModel(ModelDefinition)`
  - Constants:
    - `CANONICAL_ID`: `CanonicalModelId.GPT_3_5_TURBO_INSTRUCT`
    - `MODEL_ID`: `"openai/gpt-3.5-turbo-instruct"`
    - `PROVIDER`: `ModelProvider.OPENROUTER`
  - Attribute:
    - `model: ChatModel` — Configured `ChatModel` containing:
      - `model=ChatOpenAI(...)` with:
        - `model="openai/gpt-3.5-turbo-instruct"`
        - `temperature=0`
        - `timeout=120`
        - `max_retries=3`
        - `base_url="https://openrouter.ai/api/v1"`
        - `api_key=SecretStr(ABIModule.get_instance().configuration.openrouter_api_key)`
      - `context_window=4095`
      - Metadata fields like `name`, `description`, `created_at`, `pricing`, etc.

- Module-level:
  - `model: ChatModel` — Alias to `Gpt35TurboInstructModel.model`.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` (`ChatModel`, `ModelDefinition`, `ModelProvider`, `CanonicalModelId`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`
- **Configuration required**
  - `ABIModule.get_instance().configuration.openrouter_api_key` must be set (used as the OpenRouter API key).
- **Endpoint**
  - Uses OpenRouter base URL: `https://openrouter.ai/api/v1`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.openai.gpt_3_5_turbo_instruct import model

# Access the underlying LangChain ChatOpenAI client
llm = model.model

# Example invocation (LangChain-compatible input)
result = llm.invoke("Write a one-sentence summary of Python.")
print(result)
```

## Caveats
- Requires a valid OpenRouter API key available via `ABIModule` configuration.
- Context window is set to `4095` in the `ChatModel` metadata.
