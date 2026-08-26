# GptAudioMiniModel

## What it is
- Defines a `ModelDefinition` for the OpenRouter-hosted **OpenAI GPT Audio Mini** chat model.
- Exposes a preconfigured `langchain_openai.ChatOpenAI` instance via a `ChatModel` wrapper.

## Public API
- `class GptAudioMiniModel(ModelDefinition)`
  - Static metadata:
    - `CANONICAL_ID`: `CanonicalModelId.GPT_AUDIO_MINI`
    - `MODEL_ID`: `"openai/gpt-audio-mini"`
    - `PROVIDER`: `ModelProvider.OPENROUTER`
  - `model: ChatModel`
    - A fully configured `ChatModel` containing:
      - `model_id`, `provider`, `context_window`, metadata (name/owner/description/etc.)
      - `model`: a `ChatOpenAI` client configured for OpenRouter
- `model: ChatModel`
  - Module-level alias to `GptAudioMiniModel.model`.

## Configuration/Dependencies
- Depends on:
  - `langchain_openai.ChatOpenAI`
  - `naas_abi_core.models.Model` (`ModelDefinition`, `ChatModel`, `CanonicalModelId`, `ModelProvider`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule` for configuration
  - `pydantic.SecretStr`
- OpenRouter endpoint:
  - `OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"`
- Required configuration:
  - `ABIModule.get_instance().configuration.openrouter_api_key` must be set (used as the OpenRouter API key).
- Client defaults (as configured here):
  - `temperature=0`
  - `timeout=120`
  - `max_retries=3`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.openai.gpt_audio_mini import model

# Access the underlying LangChain ChatOpenAI client
llm = model.model

# Example call (requires valid OpenRouter API key in ABIModule configuration)
result = llm.invoke("Say hello in one sentence.")
print(result)
```

## Caveats
- This module only defines and exports the model configuration; successful calls require a valid OpenRouter API key available through `ABIModule` configuration.
