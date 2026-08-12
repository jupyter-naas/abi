# MistralMedium35Model

## What it is
- A `ModelDefinition` that registers/configures the **Mistral Medium 3.5** chat model for use via **OpenRouter** using `langchain_openai.ChatOpenAI`.
- Exposes a ready-to-use `ChatModel` instance as `model`.

## Public API
- `class MistralMedium35Model(ModelDefinition)`
  - `CANONICAL_ID`: `CanonicalModelId.MISTRAL_MEDIUM_3_5`
  - `MODEL_ID`: `"mistralai/mistral-medium-3-5"`
  - `PROVIDER`: `ModelProvider.OPENROUTER`
  - `model: ChatModel`: Preconfigured chat model definition and underlying `ChatOpenAI` client.
- `model: ChatModel`
  - Module-level alias to `MistralMedium35Model.model`.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` (`ChatModel`, `ModelDefinition`, etc.)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`
- **Runtime configuration**
  - Requires an OpenRouter API key from:
    - `ABIModule.get_instance().configuration.openrouter_api_key`
- **OpenRouter endpoint**
  - `OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"`
- **Client defaults**
  - `temperature=0`
  - `timeout=120`
  - `max_retries=3`
  - `model="mistralai/mistral-medium-3-5"`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.mistral.mistral_medium_3_5 import model

# Access the underlying LangChain ChatOpenAI client
llm = model.model

# Example call (requires ABIModule OpenRouter API key to be configured)
result = llm.invoke("Say hello in one sentence.")
print(result)
```

## Caveats
- Importing this module expects `ABIModule.get_instance().configuration.openrouter_api_key` to be available and set; otherwise initialization of the `ChatOpenAI` client may fail.
