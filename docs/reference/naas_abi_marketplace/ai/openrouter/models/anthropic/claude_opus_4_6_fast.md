# ClaudeOpus46FastModel

## What it is
- A model definition that registers/configures the **OpenRouter** chat model **`anthropic/claude-opus-4.6-fast`** using `langchain_openai.ChatOpenAI`.
- Exposes a ready-to-use `ChatModel` instance (`model`) preconfigured with OpenRouter base URL, API key, and model metadata.

## Public API
- `class ClaudeOpus46FastModel(ModelDefinition)`
  - `CANONICAL_ID`: `CanonicalModelId.CLAUDE_OPUS_4_6_FAST`
  - `MODEL_ID`: `"anthropic/claude-opus-4.6-fast"`
  - `PROVIDER`: `ModelProvider.OPENROUTER`
  - `model: ChatModel`: A fully configured `ChatModel` wrapping `ChatOpenAI`.
- `model: ChatModel`
  - Module-level alias to `ClaudeOpus46FastModel.model`.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` (`ChatModel`, `ModelDefinition`, `CanonicalModelId`, `ModelProvider`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`
- **Configuration required**
  - `ABIModule.get_instance().configuration.openrouter_api_key` must be set (used to initialize `ChatOpenAI`).
- **Hard-coded OpenRouter endpoint**
  - `OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"`
- **ChatOpenAI parameters set**
  - `temperature=0`
  - `timeout=120`
  - `max_retries=3`
  - `base_url=OPENROUTER_BASE_URL`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.anthropic.claude_opus_4_6_fast import model

# `model.model` is the underlying LangChain ChatOpenAI instance
llm = model.model

# Example call style depends on your LangChain version; this is a common pattern:
response = llm.invoke("Say hello in one sentence.")
print(response)
```

## Caveats
- Requires a valid OpenRouter API key accessible via `ABIModule` configuration; otherwise initialization will fail.
- The wrapper sets `temperature=0` and `timeout=120` explicitly in code.
