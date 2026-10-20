# o3_mini

## What it is
- Defines a preconfigured `ChatModel` instance for the OpenAI `o3-mini` chat model via `langchain_openai.ChatOpenAI`.

## Public API
- **Constants**
  - `MODEL_ID: str` — `"o3-mini"`.
  - `PROVIDER: str` — `"openai"`.
- **Module variable**
  - `model: ChatModel` — A `naas_abi_core.models.Model.ChatModel` wrapping a `ChatOpenAI` client configured with:
    - `model="o3-mini"`
    - `temperature=0`
    - `api_key` sourced from `ABIModule.get_instance().configuration.openai_api_key` (wrapped in `pydantic.SecretStr`)

## Configuration/Dependencies
- **Dependencies**
  - `langchain_openai.ChatOpenAI`
  - `naas_abi_core.models.Model.ChatModel`
  - `naas_abi_marketplace.ai.chatgpt.ABIModule`
  - `pydantic.SecretStr`
- **Configuration required**
  - `ABIModule.get_instance().configuration.openai_api_key` must be set and accessible at import time.

## Usage
```python
from naas_abi_marketplace.ai.chatgpt.models.o3_mini import model

# Access underlying LangChain chat model/client if needed
llm = model.model
print(llm.model_name if hasattr(llm, "model_name") else llm)
```

## Caveats
- Importing this module will attempt to read the OpenAI API key from `ABIModule` immediately; missing/invalid configuration may cause import-time failures.
