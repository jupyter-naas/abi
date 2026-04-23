# gpt_4_1

## What it is
- A module-level `ChatModel` definition for OpenAI’s `gpt-4.1`, implemented via `langchain_openai.ChatOpenAI`.
- Intended to be imported and used as a preconfigured chat model within the `naas_abi_marketplace` ChatGPT integration.

## Public API
- `MODEL_ID: str`
  - Constant model identifier: `"gpt-4.1"`.
- `PROVIDER: str`
  - Constant provider name: `"openai"`.
- `model: naas_abi_core.models.Model.ChatModel`
  - Preconfigured chat model wrapper with:
    - `model_id="gpt-4.1"`
    - `provider="openai"`
    - `model=ChatOpenAI(...)` configured with temperature, timeout, retries, and API key.

## Configuration/Dependencies
- Dependencies:
  - `langchain_openai.ChatOpenAI`
  - `naas_abi_core.models.Model.ChatModel`
  - `naas_abi_marketplace.ai.chatgpt.ABIModule`
  - `pydantic.SecretStr`
- Configuration source:
  - OpenAI API key is pulled from:
    - `ABIModule.get_instance().configuration.openai_api_key`
  - Wrapped as `SecretStr` and passed to `ChatOpenAI(api_key=...)`.
- Fixed runtime parameters:
  - `temperature=0`
  - `timeout=180`
  - `max_retries=3`

## Usage
```python
from naas_abi_marketplace.ai.chatgpt.models.gpt_4_1 import model

# Pass `model` into the rest of your ABI pipeline where a ChatModel is expected.
# (Exact invocation depends on the consumer of `naas_abi_core.models.Model.ChatModel`.)
print(model.model_id)  # "gpt-4.1"
```

## Caveats
- This module does not define any functions or classes; it only instantiates a configured `ChatModel` at import time.
- Importing the module requires `ABIModule.get_instance().configuration.openai_api_key` to be available and valid.
