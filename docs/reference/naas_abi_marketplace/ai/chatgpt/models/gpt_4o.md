# Gpt4oModel (gpt_4o)

## What it is
- Defines a preconfigured `ChatModel` for OpenAI’s `gpt-4o` using `langchain_openai.ChatOpenAI`.
- Exposes a ready-to-import module-level `model` instance.

## Public API
- `class Gpt4oModel(ModelDefinition)`
  - `CANONICAL_ID = CanonicalModelId.GPT_4O`
  - `MODEL_ID = "gpt-4o"`
  - `PROVIDER = ModelProvider.OPENAI`
  - `model: ChatModel`
    - A `ChatModel` constructed with:
      - `model_id="gpt-4o"`
      - `provider=ModelProvider.OPENAI`
      - `model=ChatOpenAI(model="gpt-4o", temperature=0, api_key=SecretStr(...))`
- `model: ChatModel`
  - Alias to `Gpt4oModel.model` for convenient imports.

## Configuration/Dependencies
- Dependencies:
  - `langchain_openai.ChatOpenAI`
  - `naas_abi_core.models.Model`: `ChatModel`, `ModelDefinition`, `CanonicalModelId`, `ModelProvider`
  - `naas_abi_marketplace.ai.chatgpt.ABIModule` (configuration access)
  - `pydantic.SecretStr`
- Required configuration:
  - `ABIModule.get_instance().configuration.openai_api_key` must be set (used to build `SecretStr(...)` passed to `ChatOpenAI`).

## Usage
```python
from naas_abi_marketplace.ai.chatgpt.models.gpt_4o import model

print(model.model_id)   # "gpt-4o"
print(model.provider)   # ModelProvider.OPENAI

# The wrapped LangChain client is available as:
client = model.model  # ChatOpenAI instance
```

## Caveats
- Importing the module constructs the `ChatOpenAI` client immediately and reads `openai_api_key` from `ABIModule` configuration; missing/invalid configuration can cause import-time failures.
