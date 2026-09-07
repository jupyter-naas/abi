# Gpt54Image2Model

## What it is
- A `ModelDefinition` that registers/configures the OpenRouter-hosted OpenAI model **`openai/gpt-5.4-image-2`** for use as a `ChatModel` via `langchain_openai.ChatOpenAI`.
- Exposes a ready-to-use module-level `model` object.

## Public API
- `class Gpt54Image2Model(ModelDefinition)`
  - Purpose: defines metadata and a preconfigured `ChatModel` instance for GPT-5.4 Image 2 on OpenRouter.
  - Public attributes:
    - `CANONICAL_ID`: `CanonicalModelId.GPT_5_4_IMAGE_2`
    - `MODEL_ID`: `"openai/gpt-5.4-image-2"`
    - `PROVIDER`: `ModelProvider.OPENROUTER`
    - `model: ChatModel`: configured `ChatModel` wrapping `ChatOpenAI` (temperature `0`, timeout `120`, `max_retries=3`, OpenRouter base URL).
- `model: ChatModel`
  - Purpose: module-level shortcut to `Gpt54Image2Model.model`.

## Configuration/Dependencies
- **External dependencies**
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` (`ModelDefinition`, `ChatModel`, `CanonicalModelId`, `ModelProvider`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule` for configuration
- **Runtime configuration**
  - Reads API key from: `ABIModule.get_instance().configuration.openrouter_api_key`
  - Uses OpenRouter base URL: `https://openrouter.ai/api/v1`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.openai.gpt_5_4_image_2 import model

# Access the underlying LangChain chat model
llm = model.model

# Example invocation (method depends on your LangChain version)
result = llm.invoke("Hello!")
print(result)
```

## Caveats
- Importing this module requires `ABIModule.get_instance().configuration.openrouter_api_key` to be available; otherwise initialization of `ChatOpenAI` may fail.
- The module configures `temperature=0`, `timeout=120`, and `max_retries=3` and does not expose overrides in this file.
