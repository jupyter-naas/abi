# GptChatLatestModel

## What it is
- Defines a **LangChain `ChatOpenAI` chat model** configured to call **OpenRouter** for the OpenAI alias **`openai/gpt-chat-latest`**.
- Exposes the configured `ChatModel` instance as a module-level `model`.

## Public API
- `class GptChatLatestModel(ModelDefinition)`
  - Purpose: provides a predefined `ChatModel` configuration.
  - Class attributes:
    - `CANONICAL_ID`: `CanonicalModelId.GPT_CHAT_LATEST`
    - `MODEL_ID`: `"openai/gpt-chat-latest"`
    - `PROVIDER`: `ModelProvider.OPENROUTER`
  - Field:
    - `model: ChatModel`: configured chat model instance (includes metadata like context window, pricing, supported parameters, etc.)

- `model: ChatModel`
  - Purpose: convenience alias to `GptChatLatestModel.model`.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_openai.ChatOpenAI`
  - `naas_abi_core.models.Model` (`ChatModel`, `ModelDefinition`, `ModelProvider`, `CanonicalModelId`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule` (for configuration access)
  - `pydantic.SecretStr`

- **OpenRouter endpoint**
  - `OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"`

- **Auth**
  - Uses `ABIModule.get_instance().configuration.openrouter_api_key` as the API key (wrapped in `SecretStr`).

- **ChatOpenAI configuration (hard-coded)**
  - `model="openai/gpt-chat-latest"`
  - `temperature=0`
  - `timeout=120`
  - `max_retries=3`
  - `base_url=OPENROUTER_BASE_URL`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.openai.gpt_chat_latest import model

# Access the underlying LangChain ChatOpenAI instance
llm = model.model

# Example call (depends on your installed langchain version)
result = llm.invoke("Hello! Summarize what this model is.")
print(result)
```

## Caveats
- Requires `ABIModule` to be properly configured with `openrouter_api_key`; otherwise instantiation will fail when the module is imported.
- This module defines configuration/metadata only; behavior (request/response formats, parameter support) is governed by `langchain_openai.ChatOpenAI` and OpenRouter.
