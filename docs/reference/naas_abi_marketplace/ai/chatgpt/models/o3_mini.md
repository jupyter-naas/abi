# O3MiniModel

## What it is
- Defines a preconfigured `ChatModel` for the OpenAI **`o3-mini`** chat model using `langchain_openai.ChatOpenAI`.
- Exposes the configured model as a module-level `model` for convenient import.

## Public API
- **Class**
  - `O3MiniModel(ModelDefinition)` — model definition container.
    - `CANONICAL_ID` — `CanonicalModelId.O3_MINI`
    - `MODEL_ID` — `"o3-mini"`
    - `PROVIDER` — `ModelProvider.OPENAI`
    - `model: ChatModel` — `ChatModel` instance wrapping a `ChatOpenAI` client configured with:
      - `model="o3-mini"`
      - `temperature=0`
      - `api_key=SecretStr(ABIModule.get_instance().configuration.openai_api_key)`
- **Module variable**
  - `model: ChatModel` — alias to `O3MiniModel.model`

## Configuration/Dependencies
- **Dependencies**
  - `langchain_openai.ChatOpenAI`
  - `naas_abi_core.models.Model`: `CanonicalModelId`, `ChatModel`, `ModelDefinition`, `ModelProvider`
  - `naas_abi_marketplace.ai.chatgpt.ABIModule`
  - `pydantic.SecretStr`
- **Required configuration**
  - `ABIModule.get_instance().configuration.openai_api_key` must be available at import time.

## Usage
```python
from naas_abi_marketplace.ai.chatgpt.models.o3_mini import model

# ChatModel wrapper
print(model.model_id, model.provider)

# Underlying LangChain ChatOpenAI instance
llm = model.model
print(type(llm))
```

## Caveats
- Importing this module reads `ABIModule.get_instance().configuration.openai_api_key` immediately; missing/invalid configuration can cause import-time failures.
