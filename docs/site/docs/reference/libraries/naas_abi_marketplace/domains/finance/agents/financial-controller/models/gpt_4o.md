# gpt_4o

## What it is
- A **non-functional template** for configuring a `gpt-4o` `ChatOpenAI` model intended for the **Financial Controller** domain.
- Provides a `create_model()` factory that fetches `OPENAI_API_KEY` via `naas_abi.secret` and returns a configured `ChatOpenAI` instance (or `None` if missing).

## Public API
- `create_model() -> ChatOpenAI | None`
  - Logs a warning that this is a template.
  - Retrieves `OPENAI_API_KEY`.
  - Returns a `ChatOpenAI` configured with:
    - `model="gpt-4o"`
    - `temperature=0.1`
    - `max_tokens=4000`
  - Returns `None` if the API key is not found.
- `model`
  - Module-level placeholder set to `None` (comment indicates it “would be” `create_model()`).

## Configuration/Dependencies
- Dependencies:
  - `langchain_openai.ChatOpenAI`
  - `naas_abi.secret` (expects secret key retrieval)
  - `naas_abi_core.logger`
- Required secret:
  - `OPENAI_API_KEY` must be available via `secret.get("OPENAI_API_KEY")`.

## Usage
```python
from naas_abi_marketplace.domains.financial-controller.models import gpt_4o

model = gpt_4o.create_model()
if model is None:
    raise RuntimeError("Missing OPENAI_API_KEY")

# Model is a LangChain ChatOpenAI instance
print(model.model_name)
```

## Caveats
- The module is explicitly marked **“NOT FUNCTIONAL YET - template only”**.
- The module-level `model` is **always `None`** unless you call `create_model()` yourself.
