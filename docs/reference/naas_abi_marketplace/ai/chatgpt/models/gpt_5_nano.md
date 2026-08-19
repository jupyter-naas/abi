# Gpt5NanoModel

## What it is
Defines and exports a preconfigured `ChatModel` for OpenAI’s `gpt-5-nano` using `langchain_openai.ChatOpenAI`, with the API key sourced from `ABIModule` configuration.

## Public API
- **Class: `Gpt5NanoModel(ModelDefinition)`**
  - `CANONICAL_ID` — `CanonicalModelId.GPT_5_NANO`
  - `MODEL_ID` — `"gpt-5-nano"`
  - `PROVIDER` — `ModelProvider.OPENAI`
  - `model: ChatModel` — `ChatModel` instance wrapping a `ChatOpenAI` client configured with:
    - `model="gpt-5-nano"`
    - `temperature=0`
    - `api_key=SecretStr(ABIModule.get_instance().configuration.openai_api_key)`

- **Module variable: `model: ChatModel`**
  - Alias to `Gpt5NanoModel.model` for convenient import.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_openai.ChatOpenAI`
  - `naas_abi_core.models.Model`: `ChatModel`, `ModelDefinition`, `ModelProvider`, `CanonicalModelId`
  - `naas_abi_marketplace.ai.chatgpt.ABIModule`
  - `pydantic.SecretStr`
- **Required configuration**
  - `ABIModule.get_instance().configuration.openai_api_key` must be set.

## Usage
```python
from naas_abi_marketplace.ai.chatgpt.models.gpt_5_nano import model

chat_model = model                # ChatModel
llm = chat_model.model            # underlying ChatOpenAI client
```

## Caveats
- Importing this module triggers access to `ABIModule.get_instance().configuration.openai_api_key`; missing/invalid configuration may raise errors at import time.
- This module only provides a configured model object; it does not add invocation helpers beyond what `ChatOpenAI`/`ChatModel` provide.
