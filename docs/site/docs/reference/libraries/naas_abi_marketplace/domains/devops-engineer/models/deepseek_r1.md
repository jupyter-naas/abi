# `deepseek_r1`

## What it is
- A **non-functional template** for configuring a `deepseek-r1` chat model for the **Devops Engineer** domain.
- Provides a factory function to build a `langchain_openai.ChatOpenAI` client when a `DEEPSEEK_API_KEY` is available.

## Public API
- `create_model() -> ChatOpenAI | None`
  - Logs a warning that the model is not functional yet (template only).
  - Reads the API key from `naas_abi.secret.get("DEEPSEEK_API_KEY")`.
  - Returns:
    - a configured `ChatOpenAI` instance if the key exists
    - `None` if the key is missing (and logs an error)
- Module variable: `model`
  - Currently set to `None` (comment indicates it “would be: create_model()”)

## Configuration/Dependencies
- Dependencies:
  - `langchain_openai.ChatOpenAI`
  - `naas_abi.secret` (for retrieving secrets)
  - `naas_abi_core.logger` (for warnings/errors)
- Required secret/environment:
  - `DEEPSEEK_API_KEY` (retrieved via `secret.get("DEEPSEEK_API_KEY")`)
- Model settings (as configured in code):
  - `model="deepseek-r1"`
  - `temperature=0.1`
  - `max_tokens=4000`

## Usage
```python
from naas_abi_marketplace.domains.devops_engineer.models.deepseek_r1 import create_model

llm = create_model()
if llm is None:
    raise RuntimeError("Missing DEEPSEEK_API_KEY")

# Use `llm` as a LangChain ChatOpenAI instance in your pipeline.
```

## Caveats
- The module explicitly states it is **NOT FUNCTIONAL YET** and logs a warning on `create_model()` execution.
- The exported `model` variable is **always `None`** in the current implementation.
