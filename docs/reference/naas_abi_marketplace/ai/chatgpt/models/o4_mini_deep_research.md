# o4_mini_deep_research

## What it is
- A module-level definition of a `ChatModel` configured for OpenAI’s `o4-mini-deep-research` via `langchain_openai.ChatOpenAI`.
- Exposes a ready-to-use `model` object preconfigured with:
  - `model_id="o4-mini-deep-research"`
  - `provider="openai"`
  - `temperature=0`
  - API key pulled from `ABIModule` configuration

## Public API
- **Constants**
  - `MODEL_ID: str` — `"o4-mini-deep-research"`
  - `PROVIDER: str` — `"openai"`
- **Module variable**
  - `model: ChatModel` — `naas_abi_core.models.Model.ChatModel` instance wrapping a `ChatOpenAI` client.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_openai.ChatOpenAI`
  - `naas_abi_core.models.Model.ChatModel`
  - `naas_abi_marketplace.ai.chatgpt.ABIModule`
  - `pydantic.SecretStr`
- **Configuration**
  - Requires `ABIModule.get_instance().configuration.openai_api_key` to be set; used to build the `ChatOpenAI` client.

## Usage
```python
from naas_abi_marketplace.ai.chatgpt.models.o4_mini_deep_research import model

# `model` is a ChatModel wrapper; use it according to your ChatModel interface.
print(model.model_id)   # "o4-mini-deep-research"
print(model.provider)   # "openai"

# Access the underlying LangChain client if needed:
llm = model.model
```

## Caveats
- Importing the module constructs the `ChatOpenAI` client immediately; it will access `ABIModule` configuration at import time.
- If `openai_api_key` is missing/invalid, instantiation may fail depending on upstream library behavior.
