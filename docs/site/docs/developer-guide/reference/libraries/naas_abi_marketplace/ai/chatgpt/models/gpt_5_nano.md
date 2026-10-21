# gpt_5_nano

## What it is
A module-level registration of a `ChatModel` configured to use OpenAI’s `gpt-5-nano` via `langchain_openai.ChatOpenAI`, with the API key sourced from `ABIModule` configuration.

## Public API
- **Constants**
  - `MODEL_ID: str` — Set to `"gpt-5-nano"`.
  - `PROVIDER: str` — Set to `"openai"`.
- **Variables**
  - `model: ChatModel` — Preconfigured `ChatModel` instance wrapping a `ChatOpenAI` client.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_openai.ChatOpenAI`
  - `naas_abi_core.models.Model.ChatModel`
  - `naas_abi_marketplace.ai.chatgpt.ABIModule`
  - `pydantic.SecretStr`
- **Configuration**
  - Expects `ABIModule.get_instance().configuration.openai_api_key` to be set (used to build `SecretStr(...)` for `ChatOpenAI(api_key=...)`).
- **Model settings**
  - `model="gpt-5-nano"`
  - `temperature=0`

## Usage
```python
from naas_abi_marketplace.ai.chatgpt.models import gpt_5_nano

chat_model = gpt_5_nano.model  # ChatModel instance
llm = chat_model.model         # underlying ChatOpenAI instance
```

## Caveats
- This module only defines configuration and exports a prebuilt `ChatModel`; it does not define any helper functions for invocation.
- Importing this module requires that `ABIModule` can be instantiated and its configuration provides `openai_api_key`.
