# Gpt5ChatModel

## What it is
A `ModelDefinition` that registers an OpenRouter-hosted **OpenAI GPT-5 Chat** model as a `ChatModel`, backed by `langchain_openai.ChatOpenAI`.

## Public API
- **`class Gpt5ChatModel(ModelDefinition)`**
  - **Purpose:** Defines metadata and runtime configuration for the GPT-5 Chat model.
  - **Class attributes:**
    - `CANONICAL_ID`: `CanonicalModelId.GPT_5_CHAT`
    - `MODEL_ID`: `"openai/gpt-5-chat"`
    - `PROVIDER`: `ModelProvider.OPENROUTER`
  - **Attributes:**
    - `model: ChatModel`: Fully constructed `ChatModel` instance (includes LangChain `ChatOpenAI` client and metadata).

- **`model: ChatModel` (module-level)**
  - **Purpose:** Convenience alias to `Gpt5ChatModel.model`.

## Configuration/Dependencies
- **External services**
  - Uses OpenRouter API at: `https://openrouter.ai/api/v1`

- **Configuration required**
  - `ABIModule.get_instance().configuration.openrouter_api_key` must be set (used to build a `pydantic.SecretStr` API key).

- **Key dependencies**
  - `langchain_openai.ChatOpenAI`
  - `naas_abi_core.models.Model` (`ChatModel`, `ModelDefinition`, `CanonicalModelId`, `ModelProvider`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`
  - `pydantic.SecretStr`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.openai.gpt_5_chat import model

# Access the underlying LangChain chat model client
llm = model.model

# Example call (requires OpenRouter API key configured in ABIModule)
resp = llm.invoke("Hello! Summarize what you can do in one sentence.")
print(resp)
```

## Caveats
- Requires a valid OpenRouter API key available via `ABIModule` configuration.
- Client is configured with:
  - `temperature=0`, `timeout=120`, `max_retries=3`
  - OpenRouter `base_url` (not OpenAI’s default endpoint)
