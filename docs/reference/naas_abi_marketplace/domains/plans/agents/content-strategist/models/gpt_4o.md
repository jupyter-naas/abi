# gpt_4o (Content Strategist model template)

## What it is
- A **non-functional template** for configuring a `gpt-4o` `ChatOpenAI` model intended for the *Content Strategist* domain.
- Includes environment secret lookup and basic model parameters.
- Emits warnings/errors via a logger; returns `None` when not configured.

## Public API
- `create_model() -> ChatOpenAI | None`
  - Logs a warning that the model is a template and not functional yet.
  - Reads `OPENAI_API_KEY` via `naas_abi.secret.get("OPENAI_API_KEY")`.
  - Returns a configured `langchain_openai.ChatOpenAI` instance when the key exists; otherwise logs an error and returns `None`.
- `model: None`
  - Placeholder global model instance (currently always `None`; not auto-created).

## Configuration/Dependencies
- **Dependencies**
  - `langchain_openai.ChatOpenAI`
  - `naas_abi.secret` (for secret management)
  - `naas_abi_core.logger` (for logging)
- **Required secret**
  - `OPENAI_API_KEY` must be available to `secret.get(...)` for `create_model()` to return a model.
- **Model parameters (as configured)**
  - `model="gpt-4o"`
  - `temperature=0.1`
  - `max_tokens=4000`

## Usage
```python
from naas_abi_marketplace.domains.content_strategist.models.gpt_4o import create_model

model = create_model()
if model is None:
    raise RuntimeError("Model not created (missing OPENAI_API_KEY or template not functional).")

# Use `model` as a LangChain ChatOpenAI instance (calls depend on your LangChain version).
```

## Caveats
- Marked as **NOT FUNCTIONAL YET** in code and logs; intended as a configuration template.
- The module-level `model` is **not initialized** (it is explicitly set to `None`).
