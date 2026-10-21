# gpt_4_1_mini

## What it is
- A module-level `ChatModel` configuration that wraps LangChain’s `ChatOpenAI` for the OpenAI model **`gpt-4.1-mini`**.
- Intended to be imported and used as a preconfigured chat model in the `naas_abi_marketplace` ChatGPT integration.

## Public API
- **Constants**
  - `MODEL_ID: str` — `"gpt-4.1-mini"`.
  - `PROVIDER: str` — `"openai"`.
- **Variables**
  - `model: ChatModel` — Preconfigured chat model instance:
    - `model_id` set to `MODEL_ID`
    - `provider` set to `PROVIDER`
    - `model` set to a `langchain_openai.ChatOpenAI` instance

## Configuration/Dependencies
- **Dependencies**
  - `langchain_openai.ChatOpenAI`
  - `naas_abi_core.models.Model.ChatModel`
  - `naas_abi_marketplace.ai.chatgpt.ABIModule`
  - `pydantic.SecretStr`
- **Runtime configuration**
  - Reads the OpenAI API key from:
    - `ABIModule.get_instance().configuration.openai_api_key`
  - `ChatOpenAI` parameters used:
    - `model="gpt-4.1-mini"`
    - `temperature=0`
    - `timeout=120`
    - `max_retries=3`
    - `api_key=SecretStr(...)`

## Usage
```python
from naas_abi_marketplace.ai.chatgpt.models.gpt_4_1_mini import model

# 'model' is a naas_abi_core ChatModel wrapper around a LangChain ChatOpenAI instance
print(model.model_id)   # gpt-4.1-mini
print(model.provider)   # openai

# Access the underlying LangChain model if needed
llm = model.model
```

## Caveats
- Importing this module requires `ABIModule.get_instance().configuration.openai_api_key` to be available; otherwise initialization may fail at import time.
- The configured `timeout` and `max_retries` are fixed in code (120s, 3 retries).
