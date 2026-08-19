# Qwen25ThreeBModel

## What it is
- A model definition for **Qwen2.5 3B** as the default **local** chat model running via **Ollama**.
- Provides a preconfigured `ChatOllama` client with a **32k context window** and **temperature=0**.
- Exposes a backward-compatible `model` variable for direct importers.

## Public API
- `class Qwen25ThreeBModel(ModelDefinition)`
  - Static metadata and client configuration for the model.
  - Key attributes:
    - `CANONICAL_ID`: `CanonicalModelId.QWEN_2_5_3B`
    - `MODEL_ID`: `DEFAULT_CHAT_MODEL_TAG`
    - `CONTEXT_WINDOW`: `32768`
    - `PROVIDER`: `ModelProvider.OLLAMA`
    - `model: ChatModel`: fully constructed `ChatModel` including a `ChatOllama` instance.

- `model: ChatModel`
  - Alias to `Qwen25ThreeBModel.model` for backward compatibility.

## Configuration/Dependencies
- Dependencies:
  - `langchain_ollama.ChatOllama`
  - `naas_abi_core.models.Model` (`CanonicalModelId`, `ChatModel`, `ModelDefinition`, `ModelProvider`)
  - `naas_abi_marketplace.ai.ollama.ABIModule` (for `resolved_base_url()`)
  - `naas_abi_marketplace.ai.ollama.defaults.DEFAULT_CHAT_MODEL_TAG` (Ollama model tag)

- Important configuration embedded in the client:
  - `base_url = ABIModule.resolved_base_url()`
  - `temperature = 0`
  - `num_ctx = 32768` (to prevent Ollama’s default 4096-token context truncation)

## Usage
```python
from naas_abi_marketplace.ai.ollama.models.qwen2_5_3b import model

# Access the underlying LangChain ChatOllama client:
llm = model.model

# Example invocation (LangChain style):
result = llm.invoke("Say hello in one sentence.")
print(result)
```

## Caveats
- The context window is explicitly set to **32768** via `num_ctx` to avoid **silent truncation** by Ollama’s default 4096 context.
- Increasing `num_ctx` increases memory usage (KV cache) compared to the default.
