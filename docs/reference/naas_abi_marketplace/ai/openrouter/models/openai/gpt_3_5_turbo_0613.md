# Gpt35Turbo0613Model

## What it is
- Defines a `ModelDefinition` for the OpenRouter-hosted **OpenAI `gpt-3.5-turbo-0613`** chat model using `langchain_openai.ChatOpenAI`.
- Exposes a ready-to-use `ChatModel` instance (`model`) preconfigured with provider metadata, pricing, limits, and runtime settings.

## Public API
- **`class Gpt35Turbo0613Model(ModelDefinition)`**
  - **Purpose:** Registers the model’s canonical ID, provider, and a fully configured `ChatModel`.
  - **Attributes:**
    - `CANONICAL_ID`: `CanonicalModelId.GPT_3_5_TURBO_0613`
    - `MODEL_ID`: `"openai/gpt-3.5-turbo-0613"`
    - `PROVIDER`: `ModelProvider.OPENROUTER`
    - `model: ChatModel`: A `ChatModel` containing:
      - `model_id`, `provider`, metadata (name/owner/description/etc.)
      - `model`: `ChatOpenAI(...)` configured for OpenRouter
      - `context_window=4095`
- **`model: ChatModel` (module-level)**
  - **Purpose:** Convenience alias for `Gpt35Turbo0613Model.model`.

## Configuration/Dependencies
- **OpenRouter base URL:** `https://openrouter.ai/api/v1`
- **API key source:** `ABIModule.get_instance().configuration.openrouter_api_key`
  - Passed to `ChatOpenAI` as `api_key=SecretStr(...)`.
- **Runtime settings (ChatOpenAI):**
  - `temperature=0`
  - `timeout=120`
  - `max_retries=3`
  - `model="openai/gpt-3.5-turbo-0613"`
  - `base_url=OPENROUTER_BASE_URL`
- **Key dependencies:**
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` (`ChatModel`, `ModelDefinition`, etc.)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.openai.gpt_3_5_turbo_0613 import model

# Access the underlying LangChain chat model
llm = model.model

# Minimal invocation (LangChain ChatOpenAI)
result = llm.invoke("Say hello in one short sentence.")
print(result)
```

## Caveats
- Requires `ABIModule` to be initialized/configured with a valid `openrouter_api_key`; otherwise model construction/import may fail when resolving the key.
- `context_window` is set to `4095` in the `ChatModel` metadata.
