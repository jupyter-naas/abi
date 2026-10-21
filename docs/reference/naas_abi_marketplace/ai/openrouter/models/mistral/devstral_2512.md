# Devstral2512Model

## What it is
- A model definition that configures the **Mistral Devstral 2 2512** chat model for use via **OpenRouter** using `langchain_openai.ChatOpenAI`.
- Exposes a ready-to-use `ChatModel` instance (`model`) with metadata (context window, pricing, supported parameters, etc.).

## Public API
- `class Devstral2512Model(ModelDefinition)`
  - `CANONICAL_ID`: `CanonicalModelId.DEVSTRAL_2512`
  - `MODEL_ID`: `"mistralai/devstral-2512"`
  - `PROVIDER`: `ModelProvider.OPENROUTER`
  - `model: ChatModel`
    - A preconfigured `ChatModel` wrapping a `ChatOpenAI` client:
      - `temperature=0`
      - `timeout=120`
      - `max_retries=3`
      - `base_url="https://openrouter.ai/api/v1"`
      - `api_key` sourced from `ABIModule.get_instance().configuration.openrouter_api_key`
    - Additional metadata:
      - `context_window=262144`
      - `name="Devstral 2 2512"`
      - `owner="mistralai"`
      - `canonical_slug="mistralai/devstral-2512"`
      - `hugging_face_id="mistralai/Devstral-2-123B-Instruct-2512"`
      - `created_at` set from a fixed timestamp
      - `pricing`, `architecture`, `top_provider`, `supported_parameters`, `default_parameters`
- `model: ChatModel`
  - Module-level alias to `Devstral2512Model.model`.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` (`CanonicalModelId`, `ChatModel`, `ModelDefinition`, `ModelProvider`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`
- **Required configuration**
  - `ABIModule.get_instance().configuration.openrouter_api_key` must be set (used as the OpenRouter API key).
- **OpenRouter endpoint**
  - `OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.mistral.devstral_2512 import model

# Access the underlying LangChain ChatOpenAI client
llm = model.model

# Example invocation (method depends on your langchain version)
response = llm.invoke("Write a short Python function that adds two numbers.")
print(response)
```

## Caveats
- This module assumes `ABIModule` is properly initialized and provides a valid `openrouter_api_key`; otherwise, model construction may fail.
- The `ChatOpenAI` client is configured with `temperature=0` at instantiation, even though `default_parameters` lists `temperature=0.3` in metadata.
