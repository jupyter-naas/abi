# Gpt51Model

## What it is
Defines and exports a preconfigured `ChatModel` wrapper for the OpenAI chat model `"gpt-5.1"`, backed by `langchain_openai.ChatOpenAI` and an API key read from `ABIModule` configuration.

## Public API
- `class Gpt51Model(ModelDefinition)`
  - `CANONICAL_ID`
    - Canonical identifier: `CanonicalModelId.GPT_5_1`.
  - `MODEL_ID`
    - Model string: `"gpt-5.1"`.
  - `PROVIDER`
    - Provider: `ModelProvider.OPENAI`.
  - `model: ChatModel`
    - Prebuilt `ChatModel` configured with:
      - `model_id="gpt-5.1"`
      - `provider=ModelProvider.OPENAI`
      - underlying `ChatOpenAI(model="gpt-5.1", temperature=0, api_key=SecretStr(...))`
- `model: ChatModel`
  - Module-level alias to `Gpt51Model.model`.

## Configuration/Dependencies
- Dependencies:
  - `langchain_openai.ChatOpenAI`
  - `naas_abi_core.models.Model` (`ChatModel`, `ModelDefinition`, `CanonicalModelId`, `ModelProvider`)
  - `naas_abi_marketplace.ai.chatgpt.ABIModule`
  - `pydantic.SecretStr`
- Configuration:
  - `ABIModule.get_instance().configuration.openai_api_key` is read and wrapped as `SecretStr` for `ChatOpenAI(api_key=...)`.

## Usage
```python
from naas_abi_marketplace.ai.chatgpt.models.gpt_5_1 import model

llm = model.model  # underlying ChatOpenAI instance

result = llm.invoke("Hello!")
print(result)
```

## Caveats
- Importing this module instantiates `ChatOpenAI` immediately; if `ABIModule.get_instance().configuration.openai_api_key` is missing/invalid, import-time errors may occur.
