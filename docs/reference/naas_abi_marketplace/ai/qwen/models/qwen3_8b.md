# qwen3_8b

## What it is
A small configuration module that exports a preconfigured `ChatModel` wrapping an Ollama-served **Qwen3 8B** chat model via `langchain_ollama.ChatOllama`.

## Public API
- `model: ChatModel`
  - A ready-to-use chat model configuration with:
    - `model_id`: `"qwen3:8b"`
    - `provider`: `"alibaba"`
    - `name`: `"Qwen3 8B"`
    - `description`: `"Alibaba's Qwen3 8B model for local deployment..."`
    - `image`: Ollama logo URL
    - `context_window`: `32768`
    - `model`: `ChatOllama(model="qwen3:8b", temperature=0.3)`

## Configuration/Dependencies
- Dependencies:
  - `langchain_ollama.ChatOllama`
  - `naas_abi_core.models.Model.ChatModel`
- Module constants:
  - `MODEL_ID = "qwen3:8b"`
  - `NAME = "Qwen3 8B"`
  - `DESCRIPTION = "..."`
  - `IMAGE = "https://naasai-public.../ollama_100x100.png"`
  - `CONTEXT_WINDOW = 32768`
  - `TEMPERATURE = 0.3`
  - `PROVIDER` is assigned twice; final effective value is `"alibaba"`.
- Runtime requirement:
  - An Ollama setup that can serve/pull the `qwen3:8b` model.

## Usage
```python
from naas_abi_marketplace.ai.qwen.models.qwen3_8b import model

print(model.model_id)     # qwen3:8b
print(model.provider)     # alibaba
print(model.context_window)
```

## Caveats
- `PROVIDER` is defined twice (`"qwen"` then `"alibaba"`); the latter value is used.
- The module only instantiates configuration; invocation and prompting are handled by the underlying `ChatModel` / `ChatOllama` interfaces.
