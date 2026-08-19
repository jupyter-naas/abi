# ClaudeHaiku45Model

## What it is
- A preconfigured Anthropic Claude **Haiku 4.5** chat model definition for the `naas_abi_marketplace` stack.
- Wraps `langchain_anthropic.ChatAnthropic` inside a `naas_abi_core.models.Model.ChatModel` with metadata (context window, pricing, architecture).

## Public API
- `class ClaudeHaiku45Model(ModelDefinition)`
  - Static identifiers:
    - `CANONICAL_ID`: `CanonicalModelId.CLAUDE_HAIKU_4_5`
    - `MODEL_ID`: `"claude-haiku-4-5-20251001"`
    - `PROVIDER`: `ModelProvider.ANTHROPIC`
  - `model: ChatModel`
    - A fully constructed `ChatModel` that contains:
      - `model`: `ChatAnthropic(...)` client configured with:
        - `model_name=MODEL_ID`
        - `temperature=0`
        - `max_retries=2`
        - `max_tokens_to_sample=8192`
        - `api_key=SecretStr(ABIModule.get_instance().configuration.anthropic_api_key)`
        - `timeout=None`, `stop=None`
      - `context_window=200000`
      - Additional descriptive metadata (`name`, `owner`, `description`, `pricing`, `top_provider`, `architecture`)
- Module variable: `model: ChatModel`
  - Alias to `ClaudeHaiku45Model.model`.

## Configuration/Dependencies
- Dependencies:
  - `langchain_anthropic.ChatAnthropic`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` (`ChatModel`, `ModelDefinition`, `CanonicalModelId`, `ModelProvider`)
  - `naas_abi_marketplace.ai.anthropic.ABIModule`
- Configuration required:
  - `ABIModule.get_instance().configuration.anthropic_api_key` must be set (used to build the Anthropic client API key).

## Usage
```python
from naas_abi_marketplace.ai.anthropic.models.claude_haiku_4_5 import model

# Access the underlying LangChain client:
llm = model.model  # ChatAnthropic instance

# Example call pattern depends on langchain_anthropic / LangChain versions.
# At minimum, you can pass the client around where a ChatAnthropic is expected.
print(type(llm), model.model_id, model.provider)
```

## Caveats
- The Anthropic API key is pulled from `ABIModule` at import time; missing/misconfigured `anthropic_api_key` will break initialization.
- Uses `max_tokens_to_sample` (not `max_tokens`) to avoid LangChain defaulting to 1024 tokens; this is intentional per code comments.
