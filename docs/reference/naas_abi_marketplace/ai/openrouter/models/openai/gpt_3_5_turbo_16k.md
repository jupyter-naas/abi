# Gpt35Turbo16kModel

## What it is
- A `ModelDefinition` that registers/configures the OpenRouter-hosted **OpenAI GPT-3.5 Turbo 16k** chat model using `langchain_openai.ChatOpenAI`.
- Exposes a ready-to-use `ChatModel` instance (`model`) with metadata (context window, pricing, supported parameters, etc.).

## Public API
- `class Gpt35Turbo16kModel(ModelDefinition)`
  - Purpose: Defines the canonical model identity and provides a configured `ChatModel`.
  - Public attributes:
    - `CANONICAL_ID`: `CanonicalModelId.GPT_3_5_TURBO_16K`
    - `MODEL_ID`: `"openai/gpt-3.5-turbo-16k"`
    - `PROVIDER`: `ModelProvider.OPENROUTER`
    - `model: ChatModel`: Configured chat model wrapper containing:
      - `model.model`: a `ChatOpenAI` instance configured for OpenRouter (`base_url`, `api_key`, retries, timeout, temperature).
      - Metadata like `context_window=16385`, `created_at`, `pricing`, `supported_parameters`, etc.
- `model: ChatModel`
  - Purpose: Module-level alias to `Gpt35Turbo16kModel.model` for convenient imports.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` (`ChatModel`, `ModelDefinition`, `CanonicalModelId`, `ModelProvider`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`
- **OpenRouter endpoint**
  - `OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"`
- **API key source**
  - `ABIModule.get_instance().configuration.openrouter_api_key` (wrapped in `SecretStr`)
- **ChatOpenAI configuration**
  - `model="openai/gpt-3.5-turbo-16k"`
  - `temperature=0`
  - `timeout=120`
  - `max_retries=3`
  - `base_url=OPENROUTER_BASE_URL`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.openai.gpt_3_5_turbo_16k import model

# `model` is a ChatModel; the underlying LangChain model is in `model.model`
llm = model.model

resp = llm.invoke("Write a one-sentence summary of TCP.")
print(resp.content if hasattr(resp, "content") else resp)
```

## Caveats
- Requires a valid OpenRouter API key available via `ABIModule.get_instance().configuration.openrouter_api_key`.
- The module configures `temperature=0`, `timeout=120`, and `max_retries=3`; adjust by creating your own `ChatOpenAI` if different behavior is needed.
