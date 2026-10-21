# gpt_5_1

## What it is
A module-level `ChatModel` configuration for the `gpt-5.1` OpenAI chat model, built with `langchain_openai.ChatOpenAI` and an API key sourced from `ABIModule` configuration.

## Public API
- `MODEL_ID: str`
  - Constant model identifier: `"gpt-5.1"`.
- `PROVIDER: str`
  - Constant provider identifier: `"openai"`.
- `model: naas_abi_core.models.Model.ChatModel`
  - Preconfigured chat model wrapper with:
    - `model_id="gpt-5.1"`
    - `provider="openai"`
    - underlying `ChatOpenAI(model="gpt-5.1", temperature=0, api_key=SecretStr(...))`

## Configuration/Dependencies
- Dependencies:
  - `langchain_openai.ChatOpenAI`
  - `naas_abi_core.models.Model.ChatModel`
  - `naas_abi_marketplace.ai.chatgpt.ABIModule`
  - `pydantic.SecretStr`
- Configuration requirement:
  - `ABIModule.get_instance().configuration.openai_api_key` must be set (used to build `SecretStr` for `ChatOpenAI.api_key`).

## Usage
```python
from naas_abi_marketplace.ai.chatgpt.models.gpt_5_1 import model

# `model.model` is the underlying LangChain ChatOpenAI instance.
llm = model.model

# Example call (method availability depends on your LangChain version)
result = llm.invoke("Hello!")
print(result)
```

## Caveats
- Importing this module constructs the `ChatOpenAI` instance immediately; missing/invalid `openai_api_key` in `ABIModule` configuration will cause failures at import time.
