# O3MiniModel

## What it is
- Defines the OpenRouter-hosted **OpenAI `o3-mini`** chat model as a `ModelDefinition`.
- Exposes a ready-to-use `ChatModel` configured via `langchain_openai.ChatOpenAI`, using an OpenRouter API key from `ABIModule` configuration.

## Public API
- `class O3MiniModel(ModelDefinition)`
  - Purpose: registers metadata and a configured `ChatModel` instance for the `openai/o3-mini` model.
  - Public class attributes:
    - `CANONICAL_ID`: `CanonicalModelId.O3_MINI`
    - `MODEL_ID`: `"openai/o3-mini"`
    - `PROVIDER`: `ModelProvider.OPENROUTER`
    - `model: ChatModel`: fully configured model wrapper (includes a `ChatOpenAI` instance plus metadata like context window, pricing, supported parameters).
- `model: ChatModel`
  - Module-level alias for `O3MiniModel.model`.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` (`ChatModel`, `ModelDefinition`, `CanonicalModelId`, `ModelProvider`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`
- **Configuration**
  - Requires `ABIModule.get_instance().configuration.openrouter_api_key` to be set.
- **Endpoint**
  - OpenRouter base URL: `https://openrouter.ai/api/v1`
- **ChatOpenAI defaults (as configured here)**
  - `temperature=0`, `timeout=120`, `max_retries=3`
  - `model="openai/o3-mini"`, `base_url=OPENROUTER_BASE_URL`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.openai.o3_mini import model

# Access the underlying LangChain ChatOpenAI client
llm = model.model

# Minimal call (LangChain v0.1+ style)
response = llm.invoke("Explain Newton's second law in one sentence.")
print(response.content)
```

## Caveats
- The OpenRouter API key must be available via `ABIModule` configuration; otherwise model initialization will fail.
- This module sets `temperature=0` explicitly in the underlying `ChatOpenAI` client.
