# Nemotron3NanoOmni30bA3bReasoningFreeModel

## What it is
- A model definition that registers/configures the OpenRouter-hosted `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` chat model using `langchain_openai.ChatOpenAI`.
- Exposes a ready-to-use `ChatModel` instance (`model`) with OpenRouter base URL and API key pulled from `ABIModule` configuration.

## Public API
- `class Nemotron3NanoOmni30bA3bReasoningFreeModel(ModelDefinition)`
  - Static identifiers:
    - `CANONICAL_ID`: `CanonicalModelId.NEMOTRON_3_NANO_OMNI_30B_A3B_REASONING_FREE`
    - `MODEL_ID`: `"nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free"`
    - `PROVIDER`: `ModelProvider.OPENROUTER`
  - `model: ChatModel`
    - Preconfigured `ChatModel` wrapper containing:
      - `model`: a `ChatOpenAI` client configured with:
        - `model`: `MODEL_ID`
        - `temperature=0`, `timeout=120`, `max_retries=3`
        - `api_key`: `SecretStr(ABIModule.get_instance().configuration.openrouter_api_key)`
        - `base_url`: `https://openrouter.ai/api/v1`
      - Metadata such as `context_window=256000`, `supported_parameters`, `default_parameters`, pricing, etc.
- Module-level:
  - `model: ChatModel`
    - Alias to `Nemotron3NanoOmni30bA3bReasoningFreeModel.model`

## Configuration/Dependencies
- Dependencies:
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` (`ChatModel`, `ModelDefinition`, `CanonicalModelId`, `ModelProvider`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`
- Required configuration:
  - `ABIModule.get_instance().configuration.openrouter_api_key` must be set (used to authenticate to OpenRouter).
- Endpoint:
  - OpenRouter base URL is fixed to `https://openrouter.ai/api/v1`.

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.nvidia.nemotron_3_nano_omni_30b_a3b_reasoning_free import model

# Access the underlying LangChain chat client
llm = model.model

# Example call (LangChain-style)
response = llm.invoke("Hello! Summarize what you can do in one sentence.")
print(response)
```

## Caveats
- This module only defines configuration/metadata and a prebuilt client; actual invocation patterns depend on `langchain_openai.ChatOpenAI` and the surrounding `ChatModel` wrapper behavior.
- The OpenRouter API key must be available via `ABIModule` configuration at import/runtime.
