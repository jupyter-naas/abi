# Llama33NemotronSuper49bV15Model

## What it is
- Defines a `ModelDefinition` for the OpenRouter-hosted NVIDIA model **`nvidia/llama-3.3-nemotron-super-49b-v1.5`**.
- Exposes a ready-to-use `ChatModel` backed by `langchain_openai.ChatOpenAI` configured for the OpenRouter API.

## Public API
- `class Llama33NemotronSuper49bV15Model(ModelDefinition)`
  - `CANONICAL_ID`: `CanonicalModelId.LLAMA_3_3_NEMOTRON_SUPER_49B_V1_5`
  - `MODEL_ID`: `"nvidia/llama-3.3-nemotron-super-49b-v1.5"`
  - `PROVIDER`: `ModelProvider.OPENROUTER`
  - `model: ChatModel`: preconfigured chat model wrapper including metadata (context window, pricing, supported parameters, etc.).
- `model: ChatModel`
  - Module-level alias to `Llama33NemotronSuper49bV15Model.model`.

## Configuration/Dependencies
- **OpenRouter endpoint**
  - `OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"`
- **API key**
  - Pulled from: `ABIModule.get_instance().configuration.openrouter_api_key`
  - Passed to LangChain as: `pydantic.SecretStr(...)`
- **Key dependencies**
  - `langchain_openai.ChatOpenAI`
  - `naas_abi_core.models.Model` (`ChatModel`, `ModelDefinition`, `CanonicalModelId`, `ModelProvider`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`
  - `pydantic.SecretStr`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.nvidia.llama_3_3_nemotron_super_49b_v1_5 import model

# Access the underlying LangChain ChatOpenAI instance
llm = model.model

# Example call (LangChain-style). Exact method depends on your LangChain version.
result = llm.invoke("Say hello in one sentence.")
print(result)
```

## Caveats
- Requires `ABIModule` to be properly initialized and to provide a valid `openrouter_api_key`.
- Network calls go to OpenRouter (`https://openrouter.ai/api/v1`) with `timeout=120` and `max_retries=3`.
