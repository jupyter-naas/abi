# gemma3_4b

## What it is
- A module that defines a preconfigured `ChatModel` instance for the **Gemma3 4B** model served via **Ollama** (LangChain `ChatOllama` backend).

## Public API
- `model: ChatModel`
  - Ready-to-use chat model configuration:
    - `model_id`: `"gemma3:4b"`
    - `name`: `"Gemma3 4B"`
    - `description`: `"Google's open-source Gemma3 4B model for local deployment. Fast, lightweight alternative to cloud Gemini."`
    - `provider`: `"ollama"`
    - `image`: Ollama logo URL
    - `context_window`: `8192`
    - Underlying LangChain model: `ChatOllama(model="gemma3:4b", temperature=0.4)`

## Configuration/Dependencies
- Dependencies:
  - `langchain_ollama.ChatOllama`
  - `naas_abi_core.models.Model.ChatModel`
- Runtime requirement:
  - An Ollama setup capable of serving the model id `"gemma3:4b"`.

## Usage
```python
from naas_abi_marketplace.ai.gemma.models.gemma3_4b import model

# Access underlying LangChain chat model
llm = model.model

# Example call (LangChain interface)
response = llm.invoke("Hello! Give me a one-sentence summary of Gemma.")
print(response)
```

## Caveats
- The module only exports a configured `ChatModel` instance; it does not include Ollama installation, model pulling, or server lifecycle management.
