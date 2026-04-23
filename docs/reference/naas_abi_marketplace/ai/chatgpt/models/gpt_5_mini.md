# gpt_5_mini

## What it is
A module-level `ChatModel` definition that wraps LangChain’s `ChatOpenAI` configured for the OpenAI model **`gpt-5-mini`** with deterministic output (`temperature=0`).

## Public API
- **Constants**
  - `MODEL_ID: str` — set to `"gpt-5-mini"`.
  - `PROVIDER: str` — set to `"openai"`.

- **Objects**
  - `model: ChatModel` — preconfigured chat model instance:
    - `model_id` = `MODEL_ID`
    - `provider` = `PROVIDER`
    - `model` = `langchain_openai.ChatOpenAI(...)` with:
      - `model="gpt-5-mini"`
      - `temperature=0`
      - `api_key=SecretStr(ABIModule.get_instance().configuration.openai_api_key)`

## Configuration/Dependencies
- **Dependencies**
  - `langchain_openai.ChatOpenAI`
  - `naas_abi_core.models.Model.ChatModel`
  - `naas_abi_marketplace.ai.chatgpt.ABIModule`
  - `pydantic.SecretStr`
- **Required configuration**
  - `ABIModule.get_instance().configuration.openai_api_key` must be set and accessible at import time (used to build `SecretStr` for `api_key`).

## Usage
```python
from naas_abi_marketplace.ai.chatgpt.models.gpt_5_mini import model

# `model` is a ChatModel wrapper; use it according to your ChatModel interface.
print(model.model_id)   # "gpt-5-mini"
print(model.provider)   # "openai"

# Access underlying LangChain ChatOpenAI instance if needed:
llm = model.model
```

## Caveats
- The OpenAI API key is read during module import; missing/invalid configuration can cause import-time errors.
- This file does not define any methods; runtime interaction depends on the external `ChatModel` and `ChatOpenAI` interfaces.
