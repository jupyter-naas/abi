# Ministral3b2512Model

## What it is
- A model definition that configures an OpenRouter-hosted **MistralAI “ministral-3b-2512”** chat model using `langchain_openai.ChatOpenAI`.
- Exposes a ready-to-use `ChatModel` instance (`model`) with metadata (context window, pricing, architecture, etc.).

## Public API
- **`class Ministral3b2512Model(ModelDefinition)`**
  - **Purpose:** Provides a standardized `ModelDefinition` with a preconfigured `ChatModel`.
  - **Class attributes:**
    - `CANONICAL_ID`: `CanonicalModelId.MINISTRAL_3B_2512`
    - `MODEL_ID`: `"mistralai/ministral-3b-2512"`
    - `PROVIDER`: `ModelProvider.OPENROUTER`
  - **Field:**
    - `model: ChatModel`: A `ChatModel` wrapping a `ChatOpenAI` client configured for OpenRouter.
- **`model: ChatModel`**
  - **Purpose:** Module-level alias to `Ministral3b2512Model.model` for direct import/use.

## Configuration/Dependencies
- **OpenRouter base URL**
  - Constant: `OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"`
- **API key source**
  - Pulled from: `ABIModule.get_instance().configuration.openrouter_api_key`
  - Passed to `ChatOpenAI` as `pydantic.SecretStr(...)`
- **Client configuration (`ChatOpenAI`)**
  - `model`: `"mistralai/ministral-3b-2512"`
  - `temperature`: `0`
  - `timeout`: `120`
  - `max_retries`: `3`
  - `base_url`: `https://openrouter.ai/api/v1`
- **Notable model metadata**
  - `context_window`: `131072`
  - `supported_parameters`: includes `max_tokens`, `temperature`, `tools`, `response_format`, etc.
  - `default_parameters`: `{"temperature": 0.3, "top_p": None, "frequency_penalty": None}`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.mistral.ministral_3b_2512 import model

# ChatModel wraps a LangChain ChatOpenAI client at `model.model`
llm = model.model

response = llm.invoke("Say hello in one sentence.")
print(response)
```

## Caveats
- Requires a valid OpenRouter API key available at `ABIModule.get_instance().configuration.openrouter_api_key`.
- Although metadata mentions vision capabilities, this module only configures the chat client; actual multimodal usage depends on how inputs are constructed and what `ChatOpenAI` supports in your environment.
