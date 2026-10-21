# `Gpt41MiniModel`

## What it is
- A small model-definition module that preconfigures a LangChain `ChatOpenAI` client for OpenAI’s **`gpt-4.1-mini`**.
- Exposes a `ChatModel` wrapper for use in `naas_abi_*` integrations.

## Public API
- **Class: `Gpt41MiniModel(ModelDefinition)`**
  - `CANONICAL_ID`: `CanonicalModelId.GPT_4_1_MINI`
  - `MODEL_ID`: `"gpt-4.1-mini"`
  - `PROVIDER`: `ModelProvider.OPENAI`
  - `model: ChatModel` — prebuilt wrapper containing:
    - `model_id="gpt-4.1-mini"`
    - `provider=ModelProvider.OPENAI`
    - `model=ChatOpenAI(...)` with fixed parameters (see below)

- **Module variable: `model: ChatModel`**
  - Backwards-compatible alias to `Gpt41MiniModel.model` for code that does `from ... import model`.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_openai.ChatOpenAI`
  - `naas_abi_core.models.Model`: `ChatModel`, `ModelDefinition`, `ModelProvider`, `CanonicalModelId`
  - `naas_abi_marketplace.ai.chatgpt.ABIModule`
  - `pydantic.SecretStr`

- **Runtime configuration**
  - Reads API key from: `ABIModule.get_instance().configuration.openai_api_key`
  - `ChatOpenAI` instantiated with:
    - `model="gpt-4.1-mini"`
    - `temperature=0`
    - `timeout=120`
    - `max_retries=3`
    - `api_key=SecretStr(<openai_api_key>)`

## Usage
```python
from naas_abi_marketplace.ai.chatgpt.models.gpt_4_1_mini import model

print(model.model_id)   # "gpt-4.1-mini"
print(model.provider)   # ModelProvider.OPENAI

# Underlying LangChain client:
llm = model.model
```

## Caveats
- Import-time initialization depends on `ABIModule.get_instance().configuration.openai_api_key` being available; missing/invalid configuration can fail during import.
- Network settings are fixed in code (`timeout=120`, `max_retries=3`).
