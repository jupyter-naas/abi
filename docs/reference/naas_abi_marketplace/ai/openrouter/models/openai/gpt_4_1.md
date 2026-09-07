# `Gpt41Model`

## What it is
- A model definition that registers the **OpenRouter**-hosted **OpenAI GPT‑4.1** chat model as a `ChatModel`.
- Provides a preconfigured `langchain_openai.ChatOpenAI` client (base URL set to OpenRouter).

## Public API
- `class Gpt41Model(ModelDefinition)`
  - `CANONICAL_ID`: `CanonicalModelId.GPT_4_1`
  - `MODEL_ID`: `"openai/gpt-4.1"`
  - `PROVIDER`: `ModelProvider.OPENROUTER`
  - `model: ChatModel`: Fully constructed `ChatModel` including:
    - `model`: `ChatOpenAI(model="openai/gpt-4.1", temperature=0, timeout=120, max_retries=3, base_url="https://openrouter.ai/api/v1", api_key=SecretStr(...))`
    - Metadata: `context_window=1047576`, `name="GPT-4.1"`, `owner="openai"`, `canonical_slug="openai/gpt-4.1-2025-04-14"`, `created_at=...`, `pricing=...`, `architecture=...`, etc.
- `model: ChatModel`
  - Module-level alias to `Gpt41Model.model`.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` (`ModelDefinition`, `ChatModel`, `CanonicalModelId`, `ModelProvider`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`
- **Configuration**
  - Reads the OpenRouter API key from:
    - `ABIModule.get_instance().configuration.openrouter_api_key`
- **Endpoint**
  - Uses OpenRouter base URL: `https://openrouter.ai/api/v1`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.openai.gpt_4_1 import model

llm = model.model  # langchain_openai.ChatOpenAI instance
result = llm.invoke("Say hello in one sentence.")
print(result)
```

## Caveats
- Requires `ABIModule` to be configured with `openrouter_api_key`; otherwise model construction/auth will fail at runtime.
- The `ChatOpenAI` client is configured with `temperature=0`, `timeout=120`, and `max_retries=3` in this definition.
