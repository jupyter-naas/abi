# Ministral14b2512Model

## What it is
- Defines a **LangChain `ChatOpenAI`**-backed chat model configuration for **OpenRouter** targeting `mistralai/ministral-14b-2512`.
- Exposes the configured `ChatModel` as a module-level `model`.

## Public API
- `class Ministral14b2512Model(ModelDefinition)`
  - `CANONICAL_ID`: `CanonicalModelId.MINISTRAL_14B_2512`
  - `MODEL_ID`: `"mistralai/ministral-14b-2512"`
  - `PROVIDER`: `ModelProvider.OPENROUTER`
  - `model: ChatModel`: Preconfigured chat model instance (LangChain `ChatOpenAI` under the hood).
- `model: ChatModel`
  - Alias to `Ministral14b2512Model.model` for convenient import/use.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model`: `ChatModel`, `ModelDefinition`, `CanonicalModelId`, `ModelProvider`
  - `naas_abi_marketplace.ai.openrouter.ABIModule` for configuration access
- **Runtime configuration**
  - Requires `ABIModule.get_instance().configuration.openrouter_api_key` to be set.
- **OpenRouter endpoint**
  - Base URL: `https://openrouter.ai/api/v1`
- **Model client defaults (ChatOpenAI)**
  - `temperature=0`
  - `timeout=120`
  - `max_retries=3`
  - `model="mistralai/ministral-14b-2512"`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.mistral.ministral_14b_2512 import model

# `model.model` is the underlying LangChain ChatOpenAI instance
llm = model.model

response = llm.invoke("Say hello in one sentence.")
print(response)
```

## Caveats
- Importing this module will access `ABIModule.get_instance().configuration.openrouter_api_key`; missing/invalid configuration can fail at import time.
- Although metadata indicates multimodal support (`text+image->text`), this file only configures a `ChatOpenAI` instance; actual multimodal usage depends on downstream support and calling conventions.
