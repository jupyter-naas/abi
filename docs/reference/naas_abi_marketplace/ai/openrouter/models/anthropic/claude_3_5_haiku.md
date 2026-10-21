# Claude35HaikuModel

## What it is
- A predefined `ModelDefinition` that registers/configures the OpenRouter-hosted **Anthropic Claude 3.5 Haiku** chat model for use via LangChain’s `ChatOpenAI` client.
- Exposes a ready-to-use `ChatModel` instance as `model`.

## Public API
- `class Claude35HaikuModel(ModelDefinition)`
  - `CANONICAL_ID`: `CanonicalModelId.CLAUDE_3_5_HAIKU`
  - `MODEL_ID`: `"anthropic/claude-3.5-haiku"`
  - `PROVIDER`: `ModelProvider.OPENROUTER`
  - `model: ChatModel`: Fully configured chat model wrapper, including:
    - LangChain client: `ChatOpenAI(model=..., base_url="https://openrouter.ai/api/v1", timeout=120, max_retries=3, temperature=0, api_key=...)`
    - Metadata: context window, pricing, architecture, supported/default parameters, etc.
- `model: ChatModel`
  - Module-level alias for `Claude35HaikuModel.model`.

## Configuration/Dependencies
- Depends on:
  - `langchain_openai.ChatOpenAI`
  - `naas_abi_core.models.Model` (`ChatModel`, `ModelDefinition`, `ModelProvider`, `CanonicalModelId`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule` for configuration access
  - `pydantic.SecretStr`
- Requires OpenRouter API key to be available at:
  - `ABIModule.get_instance().configuration.openrouter_api_key`
- Uses OpenRouter base URL:
  - `https://openrouter.ai/api/v1`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.anthropic.claude_3_5_haiku import model

# Access the underlying LangChain chat client:
llm = model.model  # ChatOpenAI instance

# Example call (LangChain API):
result = llm.invoke("Write a one-sentence summary of Claude 3.5 Haiku.")
print(result)
```

## Caveats
- Instantiation reads the OpenRouter API key from `ABIModule` at import time; missing/invalid configuration can break imports.
- The underlying client is `ChatOpenAI` pointed at OpenRouter (not OpenAI).
