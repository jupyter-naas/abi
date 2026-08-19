# llama_3_3_70b

## What it is
- A preconfigured `ChatModel` wrapper for **Meta Llama-3.3-70B-Instruct**, backed by `langchain_ollama.ChatOllama`.

## Public API
- **Constants**
  - `ID`: `"meta-llama/Llama-3.3-70B-Instruct"` (model identifier)
  - `NAME`: `"llama-3.3-70b-instruct"` (Ollama model name)
  - `DESCRIPTION`: Human-readable description
  - `IMAGE`: Model image URL
  - `CONTEXT_WINDOW`: `131072`
  - `PROVIDER`: `"meta"`
  - `TEMPERATURE`: `0`
  - `MAX_TOKENS`: `4096` (defined; not applied in configuration here)
  - `MAX_RETRIES`: `2` (defined; not applied in configuration here)

- **Objects**
  - `model: ChatModel`: `naas_abi_core.models.Model.ChatModel` instance configured with:
    - Metadata: `model_id`, `name`, `description`, `image`, `provider`
    - Backend: `ChatOllama(model=NAME, temperature=TEMPERATURE)`
    - `context_window=CONTEXT_WINDOW`

## Configuration/Dependencies
- **Dependencies**
  - `langchain_ollama.ChatOllama`
  - `naas_abi_core.models.Model.ChatModel`
- **Runtime expectation**
  - An Ollama environment must be available with the model named `llama-3.3-70b-instruct`.

## Usage
```python
from naas_abi_marketplace.ai.llama.models.llama_3_3_70b import model

print(model.name)
print(model.model_id)
```

## Caveats
- `MAX_TOKENS` and `MAX_RETRIES` are defined but not passed to `ChatOllama` or `ChatModel` in this module.
- How to send prompts (e.g., `invoke`) depends on the external `ChatModel`/`ChatOllama` implementations.
