# gpt_4o (Treasurer model template)

## What it is
- A **non-functional template** for configuring an OpenAI `gpt-4o` chat model for the Treasurer domain.
- Provides a helper to build a `langchain_openai.ChatOpenAI` instance when an API key is available.

## Public API
- `create_model() -> ChatOpenAI | None`
  - Logs a warning that this is a template.
  - Reads `OPENAI_API_KEY` via `naas_abi.secret.get`.
  - Returns a configured `ChatOpenAI` instance if the key is present; otherwise logs an error and returns `None`.
- `model: None`
  - Placeholder for a module-level model instance (currently not created).

## Configuration/Dependencies
- **Environment/Secrets**
  - `OPENAI_API_KEY` must be available via `naas_abi.secret.get("OPENAI_API_KEY")`.
- **Dependencies**
  - `langchain_openai.ChatOpenAI`
  - `naas_abi.secret`
  - `naas_abi_core.logger`

## Usage
```python
from naas_abi_marketplace.domains.treasurer.models import gpt_4o

model = gpt_4o.create_model()
if model is None:
    raise RuntimeError("Missing OPENAI_API_KEY")

# Example call pattern depends on your LangChain version/setup.
# (This file only constructs the model instance.)
```

## Caveats
- The module is explicitly marked **NOT FUNCTIONAL YET**.
- The module-level `model` is **always `None`** (it does not auto-instantiate `create_model()`).
- If `OPENAI_API_KEY` is missing, `create_model()` returns `None` and logs an error.
