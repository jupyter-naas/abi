# qwen3_8b

## What it is
A module that defines a preconfigured `ChatModel` instance for Alibaba’s **Qwen3 8B** running locally via **Ollama** (through `langchain_ollama.ChatOllama`).

## Public API
- `model: ChatModel`
  - A configured chat model wrapper with:
    - `model_id`: `"qwen3:8b"`
    - `provider`: `"alibaba"`
    - `name`: `"Qwen3 8B"`
    - `description`: short human-readable description
    - `image`: Ollama logo URL
    - `context_window`: `32768`
    - `model`: `ChatOllama(model="qwen3:8b", temperature=0.3)`

## Configuration/Dependencies
- Dependencies:
  - `langchain_ollama.ChatOllama`
  - `naas_abi_core.models.Model.ChatModel`
- Runtime requirements:
  - An Ollama environment capable of serving the `qwen3:8b` model.
- Key configuration constants (module-level):
  - `MODEL_ID = "qwen3:8b"`
  - `PROVIDER = "alibaba"` (note: assigned twice in code; final value is `"alibaba"`)
  - `CONTEXT_WINDOW = 32768`
  - `TEMPERATURE = 0.3`

## Usage
```python
from naas_abi_marketplace.ai.qwen.models.qwen3_8b import model

# `model` is a ChatModel wrapper around a ChatOllama instance.
# Use it according to your ChatModel interface (e.g., passing it into your app/agent pipeline).
print(model.model_id, model.provider, model.name)
```

## Caveats
- `PROVIDER` is defined twice (`"qwen"` then `"alibaba"`); the effective value used is `"alibaba"`.
- This module only defines configuration and instantiation; it does not provide helper functions for prompting or invocation beyond what `ChatModel`/`ChatOllama` expose.
