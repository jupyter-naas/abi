# MistralSabaModel

## What it is
- Defines a **LangChain `ChatOpenAI`** chat model configuration for **Mistral Saba** served via **OpenRouter**.
- Exposes a ready-to-use `ChatModel` instance (`model`) with metadata (context window, pricing, supported parameters, etc.).

## Public API
- `class MistralSabaModel(ModelDefinition)`
  - `CANONICAL_ID`: `CanonicalModelId.MISTRAL_SABA`
  - `MODEL_ID`: `"mistralai/mistral-saba"`
  - `PROVIDER`: `ModelProvider.OPENROUTER`
  - `model: ChatModel`
    - Preconfigured `ChatModel` wrapping `langchain_openai.ChatOpenAI`:
      - `temperature=0`
      - `timeout=120`
      - `max_retries=3`
      - `base_url="https://openrouter.ai/api/v1"`
      - `api_key` read from `ABIModule.get_instance().configuration.openrouter_api_key`
    - Metadata includes:
      - `context_window=32768`
      - `name="Saba"`, `owner="mistralai"`, `canonical_slug="mistralai/mistral-saba-2502"`
      - `supported_parameters=[...]`, `default_parameters={"temperature": 0.3}`
      - `pricing`, `architecture`, `top_provider`, `created_at`, etc.

- `model: ChatModel`
  - Alias to `MistralSabaModel.model`.

## Configuration/Dependencies
- Environment/config dependency:
  - `ABIModule.get_instance().configuration.openrouter_api_key` must be set (used to build `SecretStr(...)` for the OpenRouter API key).
- External libraries:
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - Core types from `naas_abi_core.models.Model` (`ChatModel`, `ModelDefinition`, etc.)

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.mistral.mistral_saba import model

# `model.model` is the underlying LangChain ChatOpenAI instance.
llm = model.model

# Example invocation (LangChain v0.1+ style may vary by installed version):
result = llm.invoke("Hello! Summarize what Mistral Saba is optimized for.")
print(result)
```

## Caveats
- Requires a valid OpenRouter API key available via `ABIModule` configuration; otherwise initialization will fail when importing/constructing the model.
- The `ChatOpenAI` instance is configured with `temperature=0`, while the `ChatModel` metadata declares `default_parameters={"temperature": 0.3}`; these values are not automatically synchronized in this file.
