# Gpt51CodexModel

## What it is
- Defines a `ModelDefinition` for the OpenRouter-hosted **OpenAI GPT-5.1-Codex** chat model.
- Exposes a ready-to-use `ChatModel` instance configured via `langchain_openai.ChatOpenAI`.

## Public API
- **`OPENROUTER_BASE_URL: str`**
  - Constant base URL: `https://openrouter.ai/api/v1`.

- **`class Gpt51CodexModel(ModelDefinition)`**
  - **Class attributes**
    - `CANONICAL_ID`: `CanonicalModelId.GPT_5_1_CODEX`
    - `MODEL_ID`: `"openai/gpt-5.1-codex"`
    - `PROVIDER`: `ModelProvider.OPENROUTER`
  - **`model: ChatModel`**
    - A `ChatModel` wrapping a `ChatOpenAI` client with:
      - `model="openai/gpt-5.1-codex"`
      - `temperature=0`, `timeout=120`, `max_retries=3`
      - `api_key` sourced from `ABIModule.get_instance().configuration.openrouter_api_key`
      - `base_url=OPENROUTER_BASE_URL`
    - Metadata includes `context_window=400000`, name/owner/description, created timestamp, pricing, architecture, supported/default parameters, etc.

- **`model: ChatModel` (module-level)**
  - Alias to `Gpt51CodexModel.model`.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` (`ChatModel`, `ModelDefinition`, `CanonicalModelId`, `ModelProvider`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule` for configuration access

- **Required configuration**
  - `ABIModule.get_instance().configuration.openrouter_api_key` must be set (used as the OpenRouter API key).

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.openai.gpt_5_1_codex import model

# Access the underlying LangChain ChatOpenAI client
llm = model.model

# Example invocation (LangChain API)
result = llm.invoke("Write a Python function that adds two numbers.")
print(result)
```

## Caveats
- The OpenRouter API key is pulled from `ABIModule` configuration; this module must be correctly initialized/configured before use.
- Network call settings are fixed here (`timeout=120`, `max_retries=3`, `temperature=0`) unless you wrap/replace the model client elsewhere.
