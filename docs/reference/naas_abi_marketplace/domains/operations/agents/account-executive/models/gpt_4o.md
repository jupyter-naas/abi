# gpt_4o

## What it is
- A **non-functional template** for configuring a `gpt-4o` `ChatOpenAI` model intended for the **Account Executive** domain.
- Provides a `create_model()` factory that retrieves `OPENAI_API_KEY` from `naas_abi.secret` and builds a `ChatOpenAI` client.

## Public API
- `create_model() -> ChatOpenAI | None`
  - Logs a warning that the model is a template.
  - Reads `OPENAI_API_KEY` via `secret.get("OPENAI_API_KEY")`.
  - Returns:
    - a configured `ChatOpenAI` instance if the key exists
    - `None` if the key is missing (and logs an error)

- Module attribute: `model`
  - Currently set to `None` (placeholder; not initialized).

## Configuration/Dependencies
- Dependencies:
  - `langchain_openai.ChatOpenAI`
  - `naas_abi.secret` (expects `secret.get(...)`)
  - `naas_abi_core.logger`
- Required secret:
  - `OPENAI_API_KEY` must be available via `secret.get("OPENAI_API_KEY")`
- Model configuration used in `create_model()`:
  - `model="gpt-4o"`
  - `temperature=0.2`
  - `max_tokens=4000`

## Usage
```python
from naas_abi_marketplace.domains.account_executive.models import gpt_4o

llm = gpt_4o.create_model()
if llm is None:
    raise RuntimeError("Missing OPENAI_API_KEY")

# Use `llm` per langchain_openai.ChatOpenAI conventions.
```

## Caveats
- The module is explicitly marked **"NOT FUNCTIONAL YET"** and logs a warning on `create_model()`.
- `model` is **not automatically created** (it is hard-coded to `None`).
