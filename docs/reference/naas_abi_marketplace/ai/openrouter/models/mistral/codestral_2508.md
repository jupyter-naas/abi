# Codestral2508Model

## What it is
- A model definition that registers/configures the **Mistral Codestral 2508** chat model for use via **OpenRouter** using `langchain_openai.ChatOpenAI`.
- Exposes a pre-built `ChatModel` instance (`model`) with metadata (context window, pricing, supported parameters, etc.).

## Public API
- `class Codestral2508Model(ModelDefinition)`
  - `CANONICAL_ID`: `CanonicalModelId.CODESTRAL_2508`
  - `MODEL_ID`: `"mistralai/codestral-2508"`
  - `PROVIDER`: `ModelProvider.OPENROUTER`
  - `model: ChatModel`: Preconfigured `ChatModel` wrapping a `ChatOpenAI` client pointed at OpenRouter.
- `model: ChatModel`
  - Alias to `Codestral2508Model.model` for convenient import/use.

## Configuration/Dependencies
- **Environment/Configuration**
  - Requires an OpenRouter API key available via:
    - `ABIModule.get_instance().configuration.openrouter_api_key`
- **External dependencies**
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` (`ChatModel`, `ModelDefinition`, `CanonicalModelId`, `ModelProvider`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`
- **Networking**
  - Base URL: `https://openrouter.ai/api/v1`
- **Client defaults configured in code**
  - `temperature=0`
  - `timeout=120`
  - `max_retries=3`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.mistral.codestral_2508 import model

# Access the underlying LangChain ChatOpenAI instance
llm = model.model

# Example call (method name depends on your LangChain version)
result = llm.invoke("Write a Python function that checks if a number is prime.")
print(result)
```

## Caveats
- This module only defines/configures the model; successful calls depend on:
  - A valid OpenRouter API key being present in `ABIModule` configuration.
  - Compatibility with your installed `langchain_openai`/LangChain version (e.g., whether `.invoke(...)` is available).
