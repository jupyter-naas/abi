# ClaudeOpus48Model

## What it is
- A `ModelDefinition` that registers/configures the OpenRouter-hosted Anthropic model **`anthropic/claude-opus-4.8`** for use via LangChain’s `ChatOpenAI`.
- Exposes a ready-to-use `ChatModel` instance (`model`) with metadata (context window, pricing, supported parameters, etc.).

## Public API
- `class ClaudeOpus48Model(ModelDefinition)`
  - Purpose: Defines the canonical model mapping and provides a configured `ChatModel`.
  - Public attributes:
    - `CANONICAL_ID`: `CanonicalModelId.CLAUDE_OPUS_4_8`
    - `MODEL_ID`: `"anthropic/claude-opus-4.8"`
    - `PROVIDER`: `ModelProvider.OPENROUTER`
    - `model`: `ChatModel` preconfigured with:
      - `model`: `langchain_openai.ChatOpenAI(...)` using OpenRouter base URL and API key from configuration.
      - `context_window`: `1000000`
      - `supported_parameters`: includes `include_reasoning`, `max_tokens`, `tools`, etc.
- Module-level:
  - `model: ChatModel = ClaudeOpus48Model.model`  
    - Purpose: Convenient alias to the configured `ChatModel`.

## Configuration/Dependencies
- Dependencies:
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` (`ChatModel`, `ModelDefinition`, `CanonicalModelId`, `ModelProvider`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`
- Configuration source:
  - API key is loaded from: `ABIModule.get_instance().configuration.openrouter_api_key`
- OpenRouter endpoint:
  - `OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"`
- ChatOpenAI settings (as configured here):
  - `temperature=0`
  - `timeout=120`
  - `max_retries=3`
  - `base_url=OPENROUTER_BASE_URL`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.anthropic.claude_opus_4_8 import model

# Access the underlying LangChain ChatOpenAI client
llm = model.model

# Example invocation (LangChain method availability depends on your installed version)
result = llm.invoke("Say hello in one sentence.")
print(result)
```

## Caveats
- Requires a valid OpenRouter API key available at `ABIModule.get_instance().configuration.openrouter_api_key`.
- The returned object from `invoke()` depends on LangChain’s `ChatOpenAI` behavior/version (e.g., message vs. structured result).
