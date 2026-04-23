# deepseek_r1_8b

## What it is
- A module that defines a preconfigured `ChatModel` instance for **DeepSeek R1 8B** served via **Ollama** using `langchain_ollama.ChatOllama`.

## Public API
- **Module constant:** `model: ChatModel`
  - A ready-to-use chat model wrapper with:
    - `model_id`: `"deepseek-r1:8b"`
    - `name`: `"DeepSeek R1 8B"`
    - `description`: reasoning-oriented model description
    - `image`: Ollama logo URL
    - `provider`: `"ollama"`
    - `context_window`: `32768`
    - underlying LangChain model: `ChatOllama(model="deepseek-r1:8b", temperature=0.1)`

## Configuration/Dependencies
- **Dependencies**
  - `langchain_ollama.ChatOllama`
  - `naas_abi_core.models.Model.ChatModel`
- **Runtime requirements**
  - An Ollama runtime with the `deepseek-r1:8b` model available (as implied by `provider="ollama"` and `model_id="deepseek-r1:8b"`).

## Usage
```python
from naas_abi_marketplace.ai.deepseek.models.deepseek_r1_8b import model

# Access metadata
print(model.model_id)     # deepseek-r1:8b
print(model.provider)     # ollama

# Use the underlying LangChain chat model
llm = model.model
response = llm.invoke("Explain the Pythagorean theorem briefly.")
print(response)
```

## Caveats
- The module only exposes a **pre-instantiated** `ChatModel`; it does not define additional helper functions.
- Token prediction limits are not configured (the `num_predict` setting is present but commented out).
