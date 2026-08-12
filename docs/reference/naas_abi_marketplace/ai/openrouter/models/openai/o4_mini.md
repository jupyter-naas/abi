# O4MiniModel

## What it is
- Defines a `ModelDefinition` for the OpenRouter-hosted **OpenAI o4-mini** chat model.
- Exposes a preconfigured `ChatModel` backed by `langchain_openai.ChatOpenAI`.

## Public API
- **Constants**
  - `OPENROUTER_BASE_URL`: Base URL for OpenRouter API (`https://openrouter.ai/api/v1`).

- **Class: `O4MiniModel(ModelDefinition)`**
  - Purpose: Provides a canonical model definition and an instantiated `ChatModel`.
  - Public class attributes:
    - `CANONICAL_ID`: `CanonicalModelId.O4_MINI`
    - `MODEL_ID`: `"openai/o4-mini"`
    - `PROVIDER`: `ModelProvider.OPENROUTER`
  - Public attribute:
    - `model: ChatModel`: Configured chat model instance (see configuration below).

- **Module-level export**
  - `model: ChatModel`: Alias to `O4MiniModel.model`.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` (`CanonicalModelId`, `ChatModel`, `ModelDefinition`, `ModelProvider`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`

- **Runtime configuration**
  - OpenRouter API key is pulled from:
    - `ABIModule.get_instance().configuration.openrouter_api_key`
  - `ChatOpenAI` is configured with:
    - `model="openai/o4-mini"`
    - `temperature=0`
    - `timeout=120`
    - `max_retries=3`
    - `base_url=OPENROUTER_BASE_URL`
    - `api_key=SecretStr(...)`

- **Model metadata (selected)**
  - `context_window=200000`
  - `supported_parameters`: `['include_reasoning', 'max_tokens', 'reasoning', 'response_format', 'seed', 'structured_outputs', 'tool_choice', 'tools']`
  - Additional fields: `pricing`, `architecture`, `top_provider`, `created_at`, etc.

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.openai.o4_mini import model

# Access the underlying LangChain ChatOpenAI instance
llm = model.model

# You can now use `llm` with LangChain (e.g., in chains/agents) as needed.
print(type(llm))
```

## Caveats
- Requires a valid OpenRouter API key available at `ABIModule.get_instance().configuration.openrouter_api_key`.
- The module only defines/configures the model; it does not implement higher-level invocation helpers beyond exposing the configured `ChatOpenAI` instance.
