# gemma3_4b

## What it is
- A small module that exposes a preconfigured `ChatModel` for the **Gemma3 4B** model via **Ollama** using LangChain’s `ChatOllama`.

## Public API
- `model: ChatModel`
  - Prebuilt chat model configuration:
    - `model_id`: `"gemma3:4b"`
    - `name`: `"Gemma3 4B"`
    - `description`: `"Google's open-source Gemma3 4B model for local deployment. Fast, lightweight alternative to cloud Gemini."`
    - `image`: `"https://naasai-public.s3.eu-west-3.amazonaws.com/logos/ollama_100x100.png"`
    - `provider`: `"ollama"`
    - `context_window`: `8192`
    - Underlying LangChain model: `ChatOllama(model="gemma3:4b", temperature=0.4)`

## Configuration/Dependencies
- Python dependencies:
  - `langchain_ollama.ChatOllama`
  - `naas_abi_core.models.Model.ChatModel`
- Runtime:
  - Ollama available and able to serve the model id `"gemma3:4b"`.

## Usage
```python
from naas_abi_marketplace.ai.gemma.models.gemma3_4b import model

llm = model.model  # underlying ChatOllama instance
resp = llm.invoke("Hello! Give me a one-sentence summary of Gemma.")
print(resp)
```

## Caveats
- This module only provides a configured `ChatModel` instance; it does not manage Ollama installation, model pulling, or server lifecycle.
