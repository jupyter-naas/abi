# gpt_4o

## What it is
- A **non-functional template** for configuring a `gpt-4o` `ChatOpenAI` model for the **Accountant** domain.
- Provides a `create_model()` factory that validates `OPENAI_API_KEY` via `naas_abi.secret` and returns a configured `ChatOpenAI` instance (or `None`).

## Public API
- `create_model() -> ChatOpenAI | None`
  - Logs a warning that this is a template.
  - Reads `OPENAI_API_KEY` using `secret.get("OPENAI_API_KEY")`.
  - Returns:
    - `None` if the key is missing (and logs an error).
    - A `ChatOpenAI` client configured with:
      - `model="gpt-4o"`
      - `temperature=0.1`
      - `max_tokens=4000`
- `model: None`
  - Placeholder module-level variable. Currently not initialized (comment indicates it would call `create_model()`).

## Configuration/Dependencies
- Environment/secret:
  - `OPENAI_API_KEY` (retrieved via `naas_abi.secret.get`)
- Python dependencies:
  - `langchain_openai.ChatOpenAI`
  - `naas_abi.secret`
  - `naas_abi_core.logger`

## Usage
```python
from naas_abi_marketplace.domains.accountant.models import gpt_4o

model = gpt_4o.create_model()
if model is None:
    raise RuntimeError("Missing OPENAI_API_KEY")

# Use `model` per langchain_openai ChatOpenAI interface.
```

## Caveats
- The module is explicitly marked **"NOT FUNCTIONAL YET"** and logs a warning on `create_model()`.
- The module-level `model` is **always `None`** unless you explicitly call `create_model()`.
- If `OPENAI_API_KEY` is not available via `secret.get`, `create_model()` returns `None`.
