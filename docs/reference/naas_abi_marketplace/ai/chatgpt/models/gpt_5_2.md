# Gpt52Model

## What it is
- Defines a `ModelDefinition` for OpenAI’s `gpt-5.2` using `langchain_openai.ChatOpenAI`.
- Exposes a ready-to-use `ChatModel` instance (`model`) configured with `temperature=0`.

## Public API
- **Class: `Gpt52Model (ModelDefinition)`**
  - `CANONICAL_ID` — `CanonicalModelId.GPT_5_2`
  - `MODEL_ID` — `"gpt-5.2"`
  - `PROVIDER` — `ModelProvider.OPENAI`
  - `model: ChatModel` — Preconfigured wrapper containing:
    - `model_id="gpt-5.2"`
    - `provider=ModelProvider.OPENAI`
    - `model=ChatOpenAI(model="gpt-5.2", temperature=0, api_key=SecretStr(...))`

- **Module variable: `model: ChatModel`**
  - Alias to `Gpt52Model.model`.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_openai.ChatOpenAI`
  - `naas_abi_core.models.Model`: `ChatModel`, `ModelDefinition`, `CanonicalModelId`, `ModelProvider`
  - `naas_abi_marketplace.ai.chatgpt.ABIModule`
  - `pydantic.SecretStr`

- **Configuration**
  - Requires `ABIModule.get_instance().configuration.openai_api_key`.
  - The key is wrapped in `SecretStr` and passed to `ChatOpenAI` as `api_key`.

## Usage
```python
from naas_abi_marketplace.ai.chatgpt.models.gpt_5_2 import model

# Access the underlying LangChain model
llm = model.model  # ChatOpenAI instance
```

## Caveats
- Importing this module reads `ABIModule` configuration at import time; a missing/invalid `openai_api_key` will raise an error during import.
- This module only provides a configured model object; invocation depends on your LangChain usage/version.
