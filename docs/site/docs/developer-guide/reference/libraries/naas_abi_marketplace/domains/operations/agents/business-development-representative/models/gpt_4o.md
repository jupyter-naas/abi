# gpt_4o

## What it is
- A **non-functional (template-only)** model configuration module intended to create a `gpt-4o` `ChatOpenAI` client for the *Business Development Representative* domain.
- Provides a `create_model()` factory that validates an OpenAI API key and returns a configured LangChain model, or `None` if unavailable.

## Public API
- `create_model() -> ChatOpenAI | None`
  - Logs a warning that this is a template.
  - Reads `OPENAI_API_KEY` via `naas_abi.secret.get(...)`.
  - Returns a configured `langchain_openai.ChatOpenAI` instance when the key is present.
  - Returns `None` and logs an error when the key is missing.
- `model: None`
  - Placeholder module-level variable. The code does **not** auto-instantiate the model.

## Configuration/Dependencies
- Dependencies:
  - `langchain_openai.ChatOpenAI`
  - `naas_abi.secret` (for `secret.get("OPENAI_API_KEY")`)
  - `naas_abi_core.logger` (for warning/error logs)
- Required configuration:
  - `OPENAI_API_KEY` must be available to `naas_abi.secret.get`.

## Usage
```python
from naas_abi_marketplace.domains.business-development-representative.models.gpt_4o import create_model

model = create_model()
if model is None:
    raise RuntimeError("Model not created (missing OPENAI_API_KEY or template-only module).")

# Example call pattern depends on your LangChain version and setup.
```

## Caveats
- The module explicitly warns it is **NOT FUNCTIONAL YET** and is a **template**.
- The module-level `model` is set to `None` and is **not** created automatically.
