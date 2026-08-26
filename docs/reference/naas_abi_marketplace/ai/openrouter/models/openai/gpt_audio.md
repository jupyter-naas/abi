# GptAudioModel

## What it is
Defines a `ChatModel` configuration for OpenRouter’s `openai/gpt-audio` using `langchain_openai.ChatOpenAI`, including metadata (context window, pricing, modalities) and client setup (API key, base URL, retries, timeout).

## Public API
- `class GptAudioModel(ModelDefinition)`
  - Purpose: Registers the canonical model definition for GPT Audio on OpenRouter.
  - Public attributes:
    - `CANONICAL_ID`: `CanonicalModelId.GPT_AUDIO`
    - `MODEL_ID`: `"openai/gpt-audio"`
    - `PROVIDER`: `ModelProvider.OPENROUTER`
    - `model: ChatModel`: Preconfigured `ChatModel` instance wrapping `ChatOpenAI(...)`.

- `model: ChatModel`
  - Purpose: Module-level alias to `GptAudioModel.model` for convenient import/use.

## Configuration/Dependencies
- Depends on:
  - `langchain_openai.ChatOpenAI`
  - `naas_abi_core.models.Model` (`ChatModel`, `ModelDefinition`, `CanonicalModelId`, `ModelProvider`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule` for reading configuration
  - `pydantic.SecretStr`
- Configuration:
  - Reads OpenRouter API key from: `ABIModule.get_instance().configuration.openrouter_api_key`
  - Uses base URL: `https://openrouter.ai/api/v1`
- Client settings:
  - `temperature=0`
  - `timeout=120`
  - `max_retries=3`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.openai.gpt_audio import model

# `model.model` is the underlying LangChain ChatOpenAI instance.
llm = model.model

# Example invocation shape depends on your LangChain version and message types.
# (Shown as a placeholder; adapt to your LangChain message imports.)
# result = llm.invoke([{"role": "user", "content": "Hello"}])
# print(result)
```

## Caveats
- Importing this module requires `ABIModule.get_instance().configuration.openrouter_api_key` to be available; otherwise initialization of `ChatOpenAI` may fail during import.
- This file only defines configuration/metadata; it does not implement audio input/output helpers or message formatting.
