# gpt_4o (Osint Researcher model template)

## What it is
- A **non-functional template** for configuring a `gpt-4o` chat model (`ChatOpenAI`) intended for the *Osint Researcher* domain.
- Provides a `create_model()` factory that validates presence of `OPENAI_API_KEY` and returns a configured `ChatOpenAI` instance, otherwise returns `None`.

## Public API
- `create_model() -> ChatOpenAI | None`
  - Logs a warning that this is a template/not functional yet.
  - Reads `OPENAI_API_KEY` via `naas_abi.secret.get("OPENAI_API_KEY")`.
  - If missing: logs an error and returns `None`.
  - If present: returns `langchain_openai.ChatOpenAI` configured with:
    - `model="gpt-4o"`
    - `temperature=0.1`
    - `max_tokens=4000`

- Module variable: `model`
  - Currently set to `None` (comment indicates it *would be* `create_model()` in a functional version).

## Configuration/Dependencies
- Environment/Secrets:
  - `OPENAI_API_KEY` must be available via `naas_abi.secret.get("OPENAI_API_KEY")`.
- Python dependencies:
  - `langchain_openai.ChatOpenAI`
  - `naas_abi.secret`
  - `naas_abi_core.logger`

## Usage
```python
from naas_abi_marketplace.domains.osint_researcher.models.gpt_4o import create_model

model = create_model()
if model is None:
    raise RuntimeError("Model not created (missing OPENAI_API_KEY or template not enabled).")

# `model` is a ChatOpenAI instance when created successfully.
```

## Caveats
- The module is explicitly marked **"NOT FUNCTIONAL YET"**.
- The exported `model` variable is **always `None`** in current code (it does not auto-initialize).
- If `OPENAI_API_KEY` is not available through `naas_abi.secret`, `create_model()` returns `None`.
