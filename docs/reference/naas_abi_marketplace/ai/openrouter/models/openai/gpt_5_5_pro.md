# `Gpt55ProModel`

## What it is
A model definition that registers the OpenRouter-hosted **OpenAI GPT-5.5 Pro** chat model as a `ChatModel`, preconfigured to use `langchain_openai.ChatOpenAI`.

## Public API
- **`class Gpt55ProModel(ModelDefinition)`**
  - **Purpose:** Declares metadata and runtime configuration for the `openai/gpt-5.5-pro` model via OpenRouter.
  - **Class attributes:**
    - `CANONICAL_ID`: `CanonicalModelId.GPT_5_5_PRO`
    - `MODEL_ID`: `"openai/gpt-5.5-pro"`
    - `PROVIDER`: `ModelProvider.OPENROUTER`
  - **Attributes:**
    - `model: ChatModel`: A fully constructed `ChatModel` containing:
      - `model_id`, `provider`, `context_window`, descriptive metadata
      - A `ChatOpenAI` instance configured with:
        - `model="openai/gpt-5.5-pro"`
        - `temperature=0`
        - `timeout=120`
        - `max_retries=3`
        - `base_url="https://openrouter.ai/api/v1"`
        - `api_key=SecretStr(ABIModule.get_instance().configuration.openrouter_api_key)`

- **`model: ChatModel`**
  - **Purpose:** Module-level alias to `Gpt55ProModel.model` for convenient import/use.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` (`ModelDefinition`, `ChatModel`, etc.)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`

- **Configuration**
  - Requires an OpenRouter API key available at:
    - `ABIModule.get_instance().configuration.openrouter_api_key`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.openai.gpt_5_5_pro import model

# Access the underlying LangChain chat model
llm = model.model  # ChatOpenAI instance

# Example invocation (LangChain-style)
response = llm.invoke("Explain the difference between TCP and UDP in one paragraph.")
print(response.content)
```

## Caveats
- This module constructs `ChatOpenAI` at import time; importing it requires `ABIModule` to be available and configured with `openrouter_api_key`.
- Network calls, timeouts, and retries are controlled by `timeout=120` and `max_retries=3` in the `ChatOpenAI` configuration.
