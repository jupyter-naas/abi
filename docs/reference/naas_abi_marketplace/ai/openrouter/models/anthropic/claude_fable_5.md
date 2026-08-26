# ClaudeFable5Model

## What it is
- Defines an OpenRouter-backed LangChain chat model configuration for **Anthropic Claude Fable 5**.
- Exposes a ready-to-use `ChatModel` instance configured with `langchain_openai.ChatOpenAI`.

## Public API
- `class ClaudeFable5Model(ModelDefinition)`
  - Purpose: Registers metadata and a configured `ChatModel` for the canonical model `CanonicalModelId.CLAUDE_FABLE_5`.
  - Key attributes:
    - `CANONICAL_ID`: `CanonicalModelId.CLAUDE_FABLE_5`
    - `MODEL_ID`: `"anthropic/claude-fable-5"`
    - `PROVIDER`: `ModelProvider.OPENROUTER`
    - `model: ChatModel`: Fully configured model (metadata + LangChain `ChatOpenAI` client).
- `model: ChatModel`
  - Purpose: Module-level alias to `ClaudeFable5Model.model` for convenient imports.

## Configuration/Dependencies
- OpenRouter base URL:
  - `OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"`
- API key source:
  - `ABIModule.get_instance().configuration.openrouter_api_key`
  - Wrapped as `pydantic.SecretStr` and passed to `ChatOpenAI(api_key=...)`.
- Dependencies:
  - `langchain_openai.ChatOpenAI`
  - `naas_abi_core.models.Model` (`ChatModel`, `ModelDefinition`, `CanonicalModelId`, `ModelProvider`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`
  - `pydantic.SecretStr`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.anthropic.claude_fable_5 import model

# Access the underlying LangChain chat client
llm = model.model

# Example invocation (LangChain-style)
result = llm.invoke("Hello! Summarize what Claude Fable 5 is good for.")
print(result)
```

## Caveats
- Requires a configured OpenRouter API key via `ABIModule` (`configuration.openrouter_api_key`).
- The client is initialized with `temperature=0`, `timeout=120`, `max_retries=3`, and `base_url` set to OpenRouter.
