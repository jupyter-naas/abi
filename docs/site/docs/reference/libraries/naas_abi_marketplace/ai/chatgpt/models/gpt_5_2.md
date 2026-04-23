# gpt_5_2

## What it is
- A module-level definition of a `ChatModel` configured to use OpenAI’s `gpt-5.2` via `langchain_openai.ChatOpenAI`.
- Exposes a ready-to-use `model` object with deterministic settings (`temperature=0`).

## Public API
- **Constants**
  - `MODEL_ID: str` — Model identifier (`"gpt-5.2"`).
  - `PROVIDER: str` — Provider name (`"openai"`).
- **Variables**
  - `model: naas_abi_core.models.Model.ChatModel` — Preconfigured chat model wrapper:
    - `model_id=MODEL_ID`
    - `provider=PROVIDER`
    - `model=ChatOpenAI(model=MODEL_ID, temperature=0, api_key=SecretStr(...))`

## Configuration/Dependencies
- **Dependencies**
  - `langchain_openai.ChatOpenAI`
  - `naas_abi_core.models.Model.ChatModel`
  - `naas_abi_marketplace.ai.chatgpt.ABIModule`
  - `pydantic.SecretStr`
- **Configuration**
  - Requires `ABIModule.get_instance().configuration.openai_api_key` to be set; it is wrapped in `SecretStr` and passed to `ChatOpenAI` as `api_key`.

## Usage
```python
from naas_abi_marketplace.ai.chatgpt.models.gpt_5_2 import model

# Use the underlying LangChain chat model
llm = model.model  # ChatOpenAI instance
```

## Caveats
- This module only defines configuration and a `model` instance; it does not implement invocation helpers. How you call `ChatOpenAI` depends on your LangChain version and calling conventions.
- Importing this module will access `ABIModule` configuration; missing/invalid `openai_api_key` will fail at import-time.
