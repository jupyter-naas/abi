# gpt_4o (Inside Sales Representative model template)

## What it is
- A **non-functional template** for configuring a `gpt-4o` `ChatOpenAI` model for the *Inside Sales Representative* domain.
- Provides a `create_model()` factory that validates the presence of `OPENAI_API_KEY` and returns a configured `ChatOpenAI` instance (or `None`).

## Public API
- `create_model() -> ChatOpenAI | None`
  - Logs a warning that this is a template.
  - Reads `OPENAI_API_KEY` via `naas_abi.secret.get(...)`.
  - Returns:
    - `ChatOpenAI(...)` configured with:
      - `model="gpt-4o"`
      - `temperature=0.2`
      - `max_tokens=4000`
    - `None` if the API key is missing.

- `model: None`
  - Placeholder module-level variable (comment indicates it “would be: create_model()”).

## Configuration/Dependencies
- Dependencies:
  - `langchain_openai.ChatOpenAI`
  - `naas_abi.secret` (expects `secret.get("OPENAI_API_KEY")`)
  - `naas_abi_core.logger`
- Required secret/environment:
  - `OPENAI_API_KEY` must be available via `naas_abi.secret`.

## Usage
```python
from naas_abi_marketplace.domains.inside-sales representative.models.gpt_4o import create_model

model = create_model()
if model is None:
    raise RuntimeError("Missing OPENAI_API_KEY")
# model is a ChatOpenAI instance configured for gpt-4o
```

## Caveats
- The module is explicitly marked **“NOT FUNCTIONAL YET - template only”** and logs a warning when `create_model()` is called.
- `model` is not instantiated (it is set to `None`).
