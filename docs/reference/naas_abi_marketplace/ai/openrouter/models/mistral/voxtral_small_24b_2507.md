# VoxtralSmall24b2507Model

## What it is
- A `ModelDefinition` that registers the **Mistral Voxtral Small 24B 2507** chat model for use via **OpenRouter** using `langchain_openai.ChatOpenAI`.
- Exposes a ready-to-use `ChatModel` instance as a module-level `model`.

## Public API
- `class VoxtralSmall24b2507Model(ModelDefinition)`
  - `CANONICAL_ID`: `CanonicalModelId.VOXTRAL_SMALL_24B_2507`
  - `MODEL_ID`: `"mistralai/voxtral-small-24b-2507"`
  - `PROVIDER`: `ModelProvider.OPENROUTER`
  - `model: ChatModel`: Preconfigured chat model wrapper containing:
    - `model`: `ChatOpenAI(...)` configured for OpenRouter (`base_url="https://openrouter.ai/api/v1"`)
    - `context_window=32000`
    - metadata (name, owner, description, pricing, etc.)
- `model: ChatModel`
  - Alias to `VoxtralSmall24b2507Model.model` for convenience.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` types (`ChatModel`, `ModelDefinition`, etc.)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`
- **Configuration**
  - Requires `ABIModule.get_instance().configuration.openrouter_api_key` to be set; it is passed to `ChatOpenAI` as a `SecretStr`.
- **OpenRouter endpoint**
  - `OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.mistral.voxtral_small_24b_2507 import model

# Access the underlying LangChain ChatOpenAI instance
llm = model.model

# Example invocation (LangChain API)
result = llm.invoke("Transcribe this audio: ...")  # depends on your message/content format
print(result)
```

## Caveats
- The `ChatOpenAI` client is initialized at import time and reads the OpenRouter API key from `ABIModule` immediately; missing/misconfigured credentials can cause import-time failures.
- Although metadata describes audio/file input modalities, this module only provides the model wrapper; correct multimodal message formatting depends on the upstream LangChain/OpenRouter interfaces.
