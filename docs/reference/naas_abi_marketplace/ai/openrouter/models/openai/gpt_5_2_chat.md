# Gpt52ChatModel

## What it is
- A `ModelDefinition` that registers/configures an OpenRouter-hosted OpenAI chat model (`openai/gpt-5.2-chat`) using `langchain_openai.ChatOpenAI`.
- Exposes a ready-to-use `ChatModel` instance as both `Gpt52ChatModel.model` and a module-level `model`.

## Public API
- `class Gpt52ChatModel(ModelDefinition)`
  - Purpose: Defines metadata and a preconfigured `ChatModel` for `openai/gpt-5.2-chat` via OpenRouter.
  - Public attributes:
    - `CANONICAL_ID`: `CanonicalModelId.GPT_5_2_CHAT`
    - `MODEL_ID`: `"openai/gpt-5.2-chat"`
    - `PROVIDER`: `ModelProvider.OPENROUTER`
    - `model`: `ChatModel` (preconfigured with `ChatOpenAI`)
- `model: ChatModel`
  - Purpose: Module-level alias to `Gpt52ChatModel.model`.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` types: `CanonicalModelId`, `ChatModel`, `ModelDefinition`, `ModelProvider`
  - `naas_abi_marketplace.ai.openrouter.ABIModule` for configuration access
- **Configuration**
  - Reads OpenRouter API key from: `ABIModule.get_instance().configuration.openrouter_api_key`
  - Uses OpenRouter base URL: `https://openrouter.ai/api/v1`
- **ChatOpenAI defaults set here**
  - `temperature=0`
  - `timeout=120`
  - `max_retries=3`
  - `model="openai/gpt-5.2-chat"`
  - `base_url=OPENROUTER_BASE_URL`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.openai.gpt_5_2_chat import model

# model.model is a langchain_openai.ChatOpenAI instance
llm = model.model

# Example invocation (LangChain style)
result = llm.invoke("Hello! Summarize what OpenRouter is in one sentence.")
print(result)
```

## Caveats
- Requires `ABIModule` to be initialized/configured so `openrouter_api_key` is available; otherwise import/initialization may fail when building the `ChatOpenAI` instance.
