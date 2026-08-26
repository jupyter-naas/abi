# Gpt51CodexMaxModel

## What it is
- A `ModelDefinition` that registers an OpenRouter-hosted OpenAI chat model: `openai/gpt-5.1-codex-max`.
- Exposes a preconfigured `ChatModel` instance backed by `langchain_openai.ChatOpenAI`.

## Public API
- `class Gpt51CodexMaxModel(ModelDefinition)`
  - Purpose: Defines metadata and runtime configuration for the GPT-5.1 Codex Max model via OpenRouter.
  - Class attributes:
    - `CANONICAL_ID`: `CanonicalModelId.GPT_5_1_CODEX_MAX`
    - `MODEL_ID`: `"openai/gpt-5.1-codex-max"`
    - `PROVIDER`: `ModelProvider.OPENROUTER`
  - Public attribute:
    - `model: ChatModel`: Fully constructed chat model configuration and client.
- `model: ChatModel`
  - Module-level alias to `Gpt51CodexMaxModel.model` for convenient imports.

## Configuration/Dependencies
- Dependencies:
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` (`ChatModel`, `ModelDefinition`, `ModelProvider`, `CanonicalModelId`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`
- OpenRouter endpoint:
  - `OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"`
- Runtime configuration:
  - API key is read from: `ABIModule.get_instance().configuration.openrouter_api_key`
- Client defaults (as configured here):
  - `temperature=0`
  - `timeout=120`
  - `max_retries=3`
  - `base_url=OPENROUTER_BASE_URL`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.openai.gpt_5_1_codex_max import model

# Access the underlying LangChain chat client
llm = model.model

# Example call pattern depends on your LangChain version and message types.
# This demonstrates access to the configured client object:
print(model.model_id, model.provider)
```

## Caveats
- Requires `ABIModule` to be correctly initialized and to provide `configuration.openrouter_api_key`; otherwise model construction may fail at import time.
- The module sets large metadata values (e.g., `context_window=400000`), but actual limits are determined by the upstream provider/model enforcement.
