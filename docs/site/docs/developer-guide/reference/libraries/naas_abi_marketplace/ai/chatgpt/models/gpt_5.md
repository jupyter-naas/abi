# gpt_5

## What it is
A preconfigured `ChatModel` instance for the OpenAI `gpt-5` chat model, built using `langchain_openai.ChatOpenAI` and keyed from the marketplace `ABIModule` configuration.

## Public API
- **Constants**
  - `MODEL_ID: str = "gpt-5"`: Model identifier passed to the OpenAI chat client.
  - `PROVIDER: str = "openai"`: Provider label for the `ChatModel`.
- **Module variable**
  - `model: ChatModel`: Ready-to-use chat model wrapper configured with:
    - `model_id="gpt-5"`
    - `provider="openai"`
    - underlying `ChatOpenAI(model="gpt-5", temperature=0, api_key=SecretStr(...))`

## Configuration/Dependencies
- **Dependencies**
  - `langchain_openai.ChatOpenAI`
  - `naas_abi_core.models.Model.ChatModel`
  - `naas_abi_marketplace.ai.chatgpt.ABIModule`
  - `pydantic.SecretStr`
- **Required configuration**
  - `ABIModule.get_instance().configuration.openai_api_key` must be set (used to build `SecretStr` for `api_key`).

## Usage
```python
from naas_abi_marketplace.ai.chatgpt.models.gpt_5 import model

# Access the configured ChatModel instance
chat_model = model

# Use chat_model according to the ChatModel interface in naas_abi_core
print(chat_model.model_id, chat_model.provider)
```

## Caveats
- Instantiation occurs at import time; missing/invalid `openai_api_key` configuration will break imports of this module.
