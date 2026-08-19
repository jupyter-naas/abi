# Gpt5ProModel

## What it is
- A `ModelDefinition` that registers/configures the OpenRouter-hosted **OpenAI GPT-5 Pro** chat model using `langchain_openai.ChatOpenAI`.
- Exposes a pre-built `ChatModel` instance (`model`) ready for use elsewhere in the package.

## Public API
- **`class Gpt5ProModel(ModelDefinition)`**
  - Static identifiers:
    - `CANONICAL_ID = CanonicalModelId.GPT_5_PRO`
    - `MODEL_ID = "openai/gpt-5-pro"`
    - `PROVIDER = ModelProvider.OPENROUTER`
  - **`model: ChatModel`**
    - A configured `ChatModel` wrapping `ChatOpenAI`:
      - `temperature=0`
      - `timeout=120`
      - `max_retries=3`
      - `base_url="https://openrouter.ai/api/v1"`
      - `api_key` sourced from `ABIModule.get_instance().configuration.openrouter_api_key`
    - Metadata includes:
      - `context_window=400000`
      - `name="GPT-5 Pro"`, `owner="openai"`, `canonical_slug="openai/gpt-5-pro-2025-10-06"`
      - `created_at=datetime.fromtimestamp(1759776663, tz=UTC)`
      - `pricing`, `architecture`, `top_provider`, `supported_parameters`, `default_parameters`
- **`model: ChatModel`** (module-level)
  - Alias to `Gpt5ProModel.model`.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` (`CanonicalModelId`, `ChatModel`, `ModelDefinition`, `ModelProvider`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`
- **Required configuration**
  - `ABIModule.get_instance().configuration.openrouter_api_key` must be set (used to build `SecretStr(...)` for `ChatOpenAI`).
- **Endpoint**
  - OpenRouter base URL: `https://openrouter.ai/api/v1`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.openai.gpt_5_pro import model

# Access the underlying LangChain chat model
llm = model.model

# Example call (LangChain-style)
response = llm.invoke("Say hello in one sentence.")
print(response)
```

## Caveats
- API key is loaded at import time via `ABIModule.get_instance().configuration.openrouter_api_key`; missing/invalid configuration may fail during import or initialization.
- The module sets `temperature=0`, `timeout=120`, and `max_retries=3` and does not expose overrides here.
