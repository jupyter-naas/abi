# O4MiniDeepResearchModel

## What it is
- Defines a `ModelDefinition` for OpenAI’s **`o4-mini-deep-research`** model.
- Exposes a preconfigured `ChatModel` instance (`model`) backed by `langchain_openai.ChatOpenAI` with:
  - `model="o4-mini-deep-research"`
  - `temperature=0`
  - `api_key` sourced from `ABIModule.get_instance().configuration.openai_api_key`

## Public API
- **Class**
  - `O4MiniDeepResearchModel (ModelDefinition)`
    - `CANONICAL_ID`: `CanonicalModelId.O4_MINI_DEEP_RESEARCH`
    - `MODEL_ID`: `"o4-mini-deep-research"`
    - `PROVIDER`: `ModelProvider.OPENAI`
    - `model: ChatModel` — prebuilt wrapper around a `ChatOpenAI` client
- **Module variable**
  - `model: ChatModel` — alias for `O4MiniDeepResearchModel.model`

## Configuration/Dependencies
- **Dependencies**
  - `langchain_openai.ChatOpenAI`
  - `naas_abi_core.models.Model`: `ChatModel`, `ModelDefinition`, `CanonicalModelId`, `ModelProvider`
  - `naas_abi_marketplace.ai.chatgpt.ABIModule`
  - `pydantic.SecretStr`
- **Required configuration**
  - `ABIModule.get_instance().configuration.openai_api_key` must be set (string API key)

## Usage
```python
from naas_abi_marketplace.ai.chatgpt.models.o4_mini_deep_research import model

# Metadata from the ChatModel wrapper
print(model.model_id)   # "o4-mini-deep-research"
print(model.provider)   # ModelProvider.OPENAI

# Underlying LangChain model/client
llm = model.model
```

## Caveats
- Import-time initialization: the `ChatOpenAI` client is constructed when the module is imported (via the class attribute initialization), and will read `ABIModule` configuration immediately.
- Missing/invalid `openai_api_key` can cause instantiation or downstream call failures depending on upstream library behavior.
