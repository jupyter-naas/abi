# deepseek_r1_8b

## What it is
- A module that provides a preconfigured `ChatModel` for the **DeepSeek R1 8B** model served via **Ollama**, backed by `langchain_ollama.ChatOllama`.

## Public API
- **Module constants**
  - `MODEL_ID`: `"deepseek-r1:8b"`
  - `NAME`: `"DeepSeek R1 8B"`
  - `DESCRIPTION`: model description string
  - `IMAGE`: Ollama logo URL string
  - `CONTEXT_WINDOW`: `32768`
  - `PROVIDER`: `"ollama"`
- **Module variable**
  - `model: ChatModel`
    - A ready-to-use `ChatModel` configured with:
      - `model_id=MODEL_ID`
      - `name=NAME`
      - `description=DESCRIPTION`
      - `image=IMAGE`
      - `provider=PROVIDER`
      - `context_window=CONTEXT_WINDOW`
      - underlying LangChain model: `ChatOllama(model=MODEL_ID, temperature=0.1)`

## Configuration/Dependencies
- **Dependencies**
  - `langchain_ollama.ChatOllama`
  - `naas_abi_core.models.Model.ChatModel`
- **Runtime requirement**
  - An Ollama environment where the model `"deepseek-r1:8b"` is available.

## Usage
```python
from naas_abi_marketplace.ai.deepseek.models.deepseek_r1_8b import model

# Metadata
print(model.model_id)         # "deepseek-r1:8b"
print(model.provider)         # "ollama"
print(model.context_window)   # 32768

# Use the underlying LangChain chat model
llm = model.model
resp = llm.invoke("Explain the Pythagorean theorem briefly.")
print(resp)
```

## Caveats
- This module only exposes a **pre-instantiated** `ChatModel`; it does not provide factory functions or additional helpers.
- Token limit configuration (`num_predict`) is present but commented out in the `ChatOllama` configuration.
