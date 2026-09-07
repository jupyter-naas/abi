# Gpt53ChatModel

## What it is
- A model definition that registers/configures the **OpenRouter** hosted **OpenAI `openai/gpt-5.3-chat`** chat model using `langchain_openai.ChatOpenAI`.
- Exposes a ready-to-use `ChatModel` instance (also aliased as module-level `model`).

## Public API
- **`class Gpt53ChatModel(ModelDefinition)`**
  - **Purpose:** Provides metadata and a configured `ChatModel` for `openai/gpt-5.3-chat` via OpenRouter.
  - **Class attributes:**
    - `CANONICAL_ID`: `CanonicalModelId.GPT_5_3_CHAT`
    - `MODEL_ID`: `"openai/gpt-5.3-chat"`
    - `PROVIDER`: `ModelProvider.OPENROUTER`
  - **Attribute:**
    - `model: ChatModel`: Configured `ChatModel` wrapping a `ChatOpenAI` client.
- **`model: ChatModel` (module-level)**
  - **Purpose:** Convenience alias to `Gpt53ChatModel.model`.

## Configuration/Dependencies
- **External dependencies**
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` (`ChatModel`, `ModelDefinition`, `CanonicalModelId`, `ModelProvider`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`
- **Configuration required**
  - `ABIModule.get_instance().configuration.openrouter_api_key` must be set (used to build the `api_key`).
- **Network endpoint**
  - Base URL: `https://openrouter.ai/api/v1` (constant `OPENROUTER_BASE_URL`)
- **Client defaults (as configured here)**
  - `temperature=0`
  - `timeout=120`
  - `max_retries=3`
  - `model="openai/gpt-5.3-chat"`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.openai.gpt_5_3_chat import model

# `model.model` is the underlying LangChain ChatOpenAI client
resp = model.model.invoke("Say hello in one sentence.")
print(resp)
```

## Caveats
- Importing this module constructs the `ChatOpenAI` client immediately and reads the OpenRouter API key from `ABIModule` configuration; missing/invalid configuration will cause failures at import time or first request.
