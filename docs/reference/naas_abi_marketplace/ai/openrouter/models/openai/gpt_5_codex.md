# Gpt5CodexModel

## What it is
- Defines a `ModelDefinition` for the **OpenRouter**-hosted **OpenAI GPT-5 Codex** chat model.
- Exposes a ready-to-use `ChatModel` instance configured via `langchain_openai.ChatOpenAI`.

## Public API
- `class Gpt5CodexModel(ModelDefinition)`
  - Purpose: provides metadata and a configured `ChatModel` for `openai/gpt-5-codex`.
  - Public attributes:
    - `CANONICAL_ID`: `CanonicalModelId.GPT_5_CODEX`
    - `MODEL_ID`: `"openai/gpt-5-codex"`
    - `PROVIDER`: `ModelProvider.OPENROUTER`
    - `model: ChatModel`: preconfigured chat model wrapper (includes LangChain `ChatOpenAI` instance and metadata such as context window and pricing).
- `model: ChatModel`
  - Module-level alias for `Gpt5CodexModel.model`.

## Configuration/Dependencies
- External dependencies:
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` (`CanonicalModelId`, `ChatModel`, `ModelDefinition`, `ModelProvider`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`
- Runtime configuration:
  - OpenRouter API key is read from:
    - `ABIModule.get_instance().configuration.openrouter_api_key`
  - OpenRouter base URL is fixed:
    - `OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"`
- `ChatOpenAI` is instantiated with:
  - `model="openai/gpt-5-codex"`, `temperature=0`, `timeout=120`, `max_retries=3`
  - `api_key=SecretStr(...)`, `base_url=OPENROUTER_BASE_URL`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.openai.gpt_5_codex import model

# Access the underlying LangChain chat model
llm = model.model  # ChatOpenAI instance

# Example invocation (LangChain style)
response = llm.invoke("Write a Python function that adds two numbers.")
print(response)
```

## Caveats
- Requires `ABIModule` to be configured with a valid `openrouter_api_key`; importing this module instantiates `ChatOpenAI` immediately using that configuration.
