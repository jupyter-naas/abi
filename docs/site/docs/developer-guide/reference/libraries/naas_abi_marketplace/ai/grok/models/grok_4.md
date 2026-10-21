# grok_4

## What it is
- A module that defines a preconfigured `ChatModel` instance for the **xAI Grok 4** chat model using `langchain_xai.ChatXAI`.
- Includes default settings for temperature, token limit, and live search parameters.

## Public API
- `model: ChatModel`
  - A ready-to-use `ChatModel` configured with:
    - `model_id="grok-4"`, `provider="xai"`, `context_window=200000`
    - Underlying LangChain model: `ChatXAI(...)` with:
      - `temperature=0.1`
      - `max_tokens=4096`
      - `api_key` from `ABIModule.get_instance().configuration.xai_api_key`
      - `search_parameters={"mode": "auto", "max_search_results": 5}` (live search enabled)

## Configuration/Dependencies
- Dependencies:
  - `langchain_xai.ChatXAI`
  - `naas_abi_marketplace.ai.grok.ABIModule`
  - `naas_abi_core.models.Model.ChatModel`
  - `pydantic.SecretStr`
- Required configuration:
  - `ABIModule.get_instance().configuration.xai_api_key` must be set (used to build the `ChatXAI` client).

## Usage
```python
from naas_abi_marketplace.ai.grok.models.grok_4 import model

# `model` is a ChatModel wrapping a ChatXAI client.
# Interactions depend on the ChatModel interface provided by naas_abi_core.
print(model.model_id)  # "grok-4"
print(model.provider)  # "xai"
```

## Caveats
- Importing this module constructs the `ChatXAI` instance immediately; missing/invalid `xai_api_key` in the ABIModule configuration will break initialization.
- Live search is enabled by default via `search_parameters` (`mode="auto"`, `max_search_results=5`).
