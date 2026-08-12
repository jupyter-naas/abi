# Gpt5MiniModel

## What it is
A module that defines and exports a preconfigured `ChatModel` wrapper around LangChain’s `ChatOpenAI` for the OpenAI model **`gpt-5-mini`**, with `temperature=0`.

## Public API
- **Class**
  - `Gpt5MiniModel (ModelDefinition)` — model definition container with:
    - `CANONICAL_ID = CanonicalModelId.GPT_5_MINI`
    - `MODEL_ID = "gpt-5-mini"`
    - `PROVIDER = ModelProvider.OPENAI`
    - `model: ChatModel` — configured `ChatModel` instance using `ChatOpenAI(...)`.

- **Module variable**
  - `model: ChatModel` — alias to `Gpt5MiniModel.model` for convenient import.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_openai.ChatOpenAI`
  - `naas_abi_core.models.Model`:
    - `CanonicalModelId`, `ChatModel`, `ModelDefinition`, `ModelProvider`
  - `naas_abi_marketplace.ai.chatgpt.ABIModule`
  - `pydantic.SecretStr`

- **Required configuration**
  - `ABIModule.get_instance().configuration.openai_api_key` is read at import time and wrapped as `SecretStr(...)` for `ChatOpenAI(api_key=...)`.

## Usage
```python
from naas_abi_marketplace.ai.chatgpt.models.gpt_5_mini import model

print(model.model_id)   # "gpt-5-mini"
print(model.provider)   # ModelProvider.OPENAI

# Underlying LangChain model (ChatOpenAI)
llm = model.model
```

## Caveats
- The OpenAI API key is accessed during module import; missing or misconfigured `openai_api_key` can raise errors when importing this module.
