# Gpt53CodexModel

## What it is
- A model definition that registers and configures the OpenRouter-hosted OpenAI chat model **`openai/gpt-5.3-codex`** using `langchain_openai.ChatOpenAI`.
- Exposes a ready-to-use `ChatModel` instance via `Gpt53CodexModel.model` (and module-level `model` alias).

## Public API
- **Constant:** `OPENROUTER_BASE_URL`
  - OpenRouter API base URL: `https://openrouter.ai/api/v1`

- **Class:** `Gpt53CodexModel(ModelDefinition)`
  - **Class attributes**
    - `CANONICAL_ID`: `CanonicalModelId.GPT_5_3_CODEX`
    - `MODEL_ID`: `"openai/gpt-5.3-codex"`
    - `PROVIDER`: `ModelProvider.OPENROUTER`
  - **Attribute**
    - `model: ChatModel`
      - A configured `ChatModel` wrapping a `ChatOpenAI` client:
        - `temperature=0`
        - `timeout=120`
        - `max_retries=3`
        - `base_url=OPENROUTER_BASE_URL`
        - `api_key` read from `ABIModule.get_instance().configuration.openrouter_api_key`
      - Metadata includes `context_window=400000`, `created_at`, `pricing`, `architecture`, and supported/default parameters.

- **Module variable:** `model: ChatModel`
  - Alias to `Gpt53CodexModel.model`.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` (`ChatModel`, `ModelDefinition`, `CanonicalModelId`, `ModelProvider`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule` (for configuration)

- **Required configuration**
  - `ABIModule.get_instance().configuration.openrouter_api_key` must be set (used as the OpenRouter API key).

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.openai.gpt_5_3_codex import model

# `model.model` is the underlying LangChain ChatOpenAI instance.
llm = model.model

# Example call (method name depends on your LangChain version):
# resp = llm.invoke("Write a Python function that adds two numbers.")
# print(resp)
```

## Caveats
- The OpenRouter API key is pulled from `ABIModule` at import time; missing/invalid configuration can cause initialization failures when importing this module.
- The underlying LangChain client is configured with `temperature=0`, `timeout=120`, and `max_retries=3` as hard-coded defaults in this definition.
