# `Gpt54NanoModel`

## What it is
- A `ModelDefinition` that registers/configures an OpenRouter-hosted OpenAI chat model: `openai/gpt-5.4-nano`.
- Provides a prebuilt `ChatModel` wrapper around `langchain_openai.ChatOpenAI`, wired to OpenRouter’s API base URL.

## Public API
- `class Gpt54NanoModel(ModelDefinition)`
  - Constants:
    - `CANONICAL_ID`: `CanonicalModelId.GPT_5_4_NANO`
    - `MODEL_ID`: `"openai/gpt-5.4-nano"`
    - `PROVIDER`: `ModelProvider.OPENROUTER`
  - Attributes:
    - `model: ChatModel` — configured chat model instance (LangChain `ChatOpenAI` under the hood) with metadata:
      - `context_window=400000`
      - `name="GPT-5.4 Nano"`, `owner="openai"`, etc.
      - `supported_parameters=[...]`, `default_parameters={...}`

- Module-level:
  - `OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"`
  - `model: ChatModel = Gpt54NanoModel.model` — convenience alias to the configured model.

## Configuration/Dependencies
- Depends on:
  - `langchain_openai.ChatOpenAI`
  - `naas_abi_core.models.Model` (`ChatModel`, `ModelDefinition`, `CanonicalModelId`, `ModelProvider`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule` for configuration lookup
  - `pydantic.SecretStr`
- Required configuration:
  - `ABIModule.get_instance().configuration.openrouter_api_key` must be set; it is used as the OpenRouter API key.
- Model runtime configuration (fixed here):
  - `temperature=0`
  - `timeout=120`
  - `max_retries=3`
  - `base_url=OPENROUTER_BASE_URL`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.openai.gpt_5_4_nano import model

# `model.model` is the underlying LangChain ChatOpenAI instance.
llm = model.model

# Example call (LangChain-style)
result = llm.invoke("Say hello in one sentence.")
print(result)
```

## Caveats
- Requires an OpenRouter API key available via `ABIModule` configuration; otherwise model initialization will fail.
