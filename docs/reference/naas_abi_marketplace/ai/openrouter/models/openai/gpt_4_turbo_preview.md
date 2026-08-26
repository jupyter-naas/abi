# Gpt4TurboPreviewModel

## What it is
- Defines a `ModelDefinition` for the OpenRouter-hosted **OpenAI GPT-4 Turbo Preview** chat model.
- Exposes a preconfigured `ChatModel` (LangChain `ChatOpenAI`) with fixed defaults (temperature, timeout, retries, base URL).

## Public API
- **Class `Gpt4TurboPreviewModel(ModelDefinition)`**
  - **Class attributes**
    - `CANONICAL_ID`: `CanonicalModelId.GPT_4_TURBO_PREVIEW`
    - `MODEL_ID`: `"openai/gpt-4-turbo-preview"`
    - `PROVIDER`: `ModelProvider.OPENROUTER`
  - **Attribute**
    - `model: ChatModel`: A configured `ChatModel` instance wrapping `langchain_openai.ChatOpenAI`, plus metadata such as context window, pricing, and supported parameters.

- **Module-level `model: ChatModel`**
  - Alias to `Gpt4TurboPreviewModel.model` for convenient import/use.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` (`CanonicalModelId`, `ChatModel`, `ModelDefinition`, `ModelProvider`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`
- **Configuration**
  - Requires an OpenRouter API key at:
    - `ABIModule.get_instance().configuration.openrouter_api_key`
  - Uses OpenRouter base URL:
    - `OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"`

- **ChatOpenAI defaults**
  - `model="openai/gpt-4-turbo-preview"`
  - `temperature=0`
  - `timeout=120`
  - `max_retries=3`
  - `base_url="https://openrouter.ai/api/v1"`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.openai.gpt_4_turbo_preview import model

# `model.model` is a LangChain ChatOpenAI instance
llm = model.model

resp = llm.invoke("Say hello in one sentence.")
print(resp.content)
```

## Caveats
- Instantiation depends on `ABIModule` being configured with a valid `openrouter_api_key`; missing/invalid configuration will prevent creating the underlying `ChatOpenAI` client.
- The model is configured to use OpenRouter (not OpenAI’s direct API endpoint).
