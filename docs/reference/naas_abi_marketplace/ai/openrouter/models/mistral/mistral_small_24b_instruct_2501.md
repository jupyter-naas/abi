# MistralSmall24bInstruct2501Model

## What it is
- A `ModelDefinition` that registers/configures the **Mistral Small 24B Instruct 2501** chat model for use via **OpenRouter** using `langchain_openai.ChatOpenAI`.
- Exposes a ready-to-use `ChatModel` instance as a module-level `model`.

## Public API
- `class MistralSmall24bInstruct2501Model(ModelDefinition)`
  - Purpose: defines metadata and the configured `ChatModel` for `mistralai/mistral-small-24b-instruct-2501`.
  - Public class attributes:
    - `CANONICAL_ID`: `CanonicalModelId.MISTRAL_SMALL_24B_INSTRUCT_2501`
    - `MODEL_ID`: `"mistralai/mistral-small-24b-instruct-2501"`
    - `PROVIDER`: `ModelProvider.OPENROUTER`
  - Public field:
    - `model: ChatModel`: wraps a `ChatOpenAI` client with OpenRouter base URL, API key, and model metadata.
- `model: ChatModel`
  - Purpose: convenience alias for `MistralSmall24bInstruct2501Model.model`.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` (`ChatModel`, `ModelDefinition`, `CanonicalModelId`, `ModelProvider`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`
- **Runtime configuration**
  - Reads OpenRouter API key from:
    - `ABIModule.get_instance().configuration.openrouter_api_key`
- **Connection settings**
  - `OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"`
  - `ChatOpenAI(..., temperature=0, timeout=120, max_retries=3, base_url=OPENROUTER_BASE_URL)`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.mistral.mistral_small_24b_instruct_2501 import model

# Access the underlying LangChain chat client
llm = model.model

# Example call (method depends on your LangChain version)
# response = llm.invoke("Say hello in one sentence.")
# print(response)
```

## Caveats
- Requires `ABIModule` to be properly initialized and to provide a valid `openrouter_api_key`; otherwise model construction/import may fail.
- The configured `ChatOpenAI` instance uses `temperature=0` even though `default_parameters` in metadata indicates `temperature: 0.3`.
