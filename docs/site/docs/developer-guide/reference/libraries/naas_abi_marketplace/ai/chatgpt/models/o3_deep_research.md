# o3_deep_research

## What it is
- A module-level configuration that registers/exports a `ChatModel` instance for OpenAI’s `o3-deep-research` model using LangChain’s `ChatOpenAI`.

## Public API
- `MODEL_ID: str`
  - Constant model identifier: `"o3-deep-research"`.
- `PROVIDER: str`
  - Constant provider identifier: `"openai"`.
- `model: naas_abi_core.models.Model.ChatModel`
  - Preconfigured chat model wrapper containing:
    - `model_id` and `provider`
    - a `langchain_openai.ChatOpenAI` instance with `temperature=0` and an API key sourced from `ABIModule` configuration.

## Configuration/Dependencies
- Dependencies:
  - `langchain_openai.ChatOpenAI`
  - `naas_abi_core.models.Model.ChatModel`
  - `naas_abi_marketplace.ai.chatgpt.ABIModule`
  - `pydantic.SecretStr`
- Configuration required:
  - `ABIModule.get_instance().configuration.openai_api_key` must be set (used to build the `ChatOpenAI` `api_key`).

## Usage
```python
from naas_abi_marketplace.ai.chatgpt.models import o3_deep_research

chat_model = o3_deep_research.model  # ChatModel wrapper
llm = chat_model.model               # underlying ChatOpenAI instance
```

## Caveats
- This module only defines a preconfigured model instance; it does not expose helper functions for invoking or formatting prompts.
- Importing/initializing requires `ABIModule` to be configured with a valid OpenAI API key.
