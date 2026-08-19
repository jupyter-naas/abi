# grok_4

## What it is
- A module that exports a preconfigured `ChatModel` for the **xAI Grok 4** chat model.
- Wraps a `langchain_xai.ChatXAI` client with defaults for temperature, token limit, and live search.

## Public API
- `model: ChatModel`
  - A ready-to-use `ChatModel` configured with:
    - `model_id="grok-4"`, `name="Grok 4"`, `provider="xai"`, `context_window=200000`
    - `description` and `image` metadata
    - Underlying `ChatXAI` client configured with:
      - `model="grok-4"`
      - `temperature=0.1`
      - `max_tokens=4096`
      - `api_key=SecretStr(ABIModule.get_instance().configuration.xai_api_key)`
      - `search_parameters={"mode": "auto", "max_search_results": 5}`

## Configuration/Dependencies
- Dependencies:
  - `langchain_xai.ChatXAI`
  - `naas_abi_core.models.Model.ChatModel`
  - `naas_abi_marketplace.ai.grok.ABIModule`
  - `pydantic.SecretStr`
- Required configuration:
  - `ABIModule.get_instance().configuration.xai_api_key` must be set (used to create the `ChatXAI` client).

## Usage
```python
from naas_abi_marketplace.ai.grok.models.grok_4 import model

print(model.model_id)        # grok-4
print(model.provider)        # xai
print(model.context_window)  # 200000
```

## Caveats
- Importing this module instantiates `ChatXAI` immediately; missing/invalid `xai_api_key` will cause initialization to fail.
- Live search is enabled by default via `search_parameters` (`mode="auto"`, `max_search_results=5`).
