# llama_3_3_70b

## What it is
- A module that defines a preconfigured `ChatModel` wrapper for Meta’s **Llama-3.3-70B-Instruct** using `langchain_ollama.ChatOllama`.

## Public API
- **Constants**
  - `ID`: Model identifier (`"meta-llama/Llama-3.3-70B-Instruct"`).
  - `NAME`: Ollama model name (`"llama-3.3-70b-instruct"`).
  - `DESCRIPTION`: Human-readable model description.
  - `IMAGE`: Image URL for the model.
  - `CONTEXT_WINDOW`: Context window size (`131072`).
  - `PROVIDER`: Provider label (`"meta"`).
  - `TEMPERATURE`: Default temperature (`0`).
  - `MAX_TOKENS`: Defined but not used in configuration (`4096`).
  - `MAX_RETRIES`: Defined but not used in configuration (`2`).

- **Objects**
  - `model: ChatModel`: A `naas_abi_core.models.Model.ChatModel` instance configured with:
    - `model_id`, `name`, `description`, `image`, `provider`
    - `model=ChatOllama(model=NAME, temperature=TEMPERATURE)`
    - `context_window=CONTEXT_WINDOW`

## Configuration/Dependencies
- **Dependencies**
  - `langchain_ollama.ChatOllama`
  - `naas_abi_core.models.Model.ChatModel`
- **Runtime expectation**
  - The configured `ChatOllama` backend must be available and have the model named `llama-3.3-70b-instruct` accessible.

## Usage
```python
from naas_abi_marketplace.ai.llama.models.llama_3_3_70b import model

# `model` is a ChatModel wrapper around a ChatOllama instance
print(model.name)
print(model.model_id)
```

## Caveats
- `MAX_TOKENS` and `MAX_RETRIES` are defined in the module but are not applied to the `ChatOllama` or `ChatModel` configuration here.
- The exact invocation interface (e.g., `.invoke(...)`) depends on `ChatModel` and `ChatOllama` implementations, which are external to this module.
