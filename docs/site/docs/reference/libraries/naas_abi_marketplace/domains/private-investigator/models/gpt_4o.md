# gpt_4o (Private Investigator model template)

## What it is
- A **non-functional template** for configuring a `gpt-4o` `ChatOpenAI` model intended for the *Private Investigator* domain.
- Provides a `create_model()` factory that:
  - Logs a warning that it’s not functional yet.
  - Loads `OPENAI_API_KEY` from `naas_abi.secret`.
  - Returns a configured `ChatOpenAI` instance, or `None` if the key is missing.

## Public API
- `create_model() -> ChatOpenAI | None`
  - Creates and returns a `ChatOpenAI` configured with:
    - `model="gpt-4o"`
    - `temperature=0.1`
    - `max_tokens=4000`
  - Returns `None` if `OPENAI_API_KEY` is not available.
- Module variable: `model`
  - Currently set to `None` (placeholder; not initialized).

## Configuration/Dependencies
- Environment/Secrets:
  - `OPENAI_API_KEY` must be available via `naas_abi.secret.get("OPENAI_API_KEY")`.
- Dependencies:
  - `langchain_openai.ChatOpenAI`
  - `naas_abi.secret`
  - `naas_abi_core.logger`

## Usage
```python
from naas_abi_marketplace.domains.private_investigator.models.gpt_4o import create_model

model = create_model()
if model is None:
    raise RuntimeError("Missing OPENAI_API_KEY")

# Example call (LangChain interface)
response = model.invoke("Summarize the key facts from this case note.")
print(response)
```

## Caveats
- Marked as **NOT FUNCTIONAL YET** in the module docstring and via a runtime warning.
- The module-level `model` is **not created** automatically (`model = None`).
- If `OPENAI_API_KEY` is missing, `create_model()` logs an error and returns `None`.
