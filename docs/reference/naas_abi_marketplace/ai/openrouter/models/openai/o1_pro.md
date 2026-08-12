# O1ProModel

## What it is
- Defines the **OpenRouter-hosted** `openai/o1-pro` model as a `ModelDefinition`.
- Exposes a ready-to-use `ChatModel` wrapping a configured `langchain_openai.ChatOpenAI` client.

## Public API
- `class O1ProModel(ModelDefinition)`
  - `CANONICAL_ID`: `CanonicalModelId.O1_PRO`
  - `MODEL_ID`: `"openai/o1-pro"`
  - `PROVIDER`: `ModelProvider.OPENROUTER`
  - `model: ChatModel`: Preconfigured chat model definition + runtime client.
- `model: ChatModel`
  - Module-level alias to `O1ProModel.model` for convenient imports.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model`: `CanonicalModelId`, `ChatModel`, `ModelDefinition`, `ModelProvider`
  - `naas_abi_marketplace.ai.openrouter.ABIModule`
- **OpenRouter endpoint**
  - `OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"`
- **API key source**
  - `ABIModule.get_instance().configuration.openrouter_api_key`
- **Client configuration**
  - `model="openai/o1-pro"`
  - `temperature=0`
  - `timeout=120`
  - `max_retries=3`
  - `base_url=OPENROUTER_BASE_URL`
- **Metadata set on `ChatModel`**
  - `context_window=200000`, `name="o1-pro"`, `owner="openai"`, plus pricing/architecture/provider capability fields.

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.openai.o1_pro import model

# Underlying LangChain client
llm = model.model  # ChatOpenAI

# Basic invocation (API may vary by LangChain version)
resp = llm.invoke("Hello from o1-pro")
print(resp)
```

## Caveats
- Requires `ABIModule` to be configured with a valid `openrouter_api_key`; otherwise instantiation of the `ChatOpenAI` client will fail.
