# gpt_4o

## What it is
- A **non-functional template** for configuring a GPT-4o (`ChatOpenAI`) model intended for the “Project Manager” domain.
- Includes placeholder wiring for retrieving `OPENAI_API_KEY` via `naas_abi.secret` and logging via `naas_abi_core.logger`.

## Public API
- `create_model() -> ChatOpenAI | None`
  - Logs a warning that this is a template.
  - Reads `OPENAI_API_KEY` via `secret.get("OPENAI_API_KEY")`.
  - Returns:
    - A configured `ChatOpenAI` instance when the API key is present.
    - `None` and logs an error when the API key is missing.
- `model: None`
  - Module-level placeholder; currently not initialized (comment indicates it “would be: create_model()`).

## Configuration/Dependencies
- Dependencies:
  - `langchain_openai.ChatOpenAI`
  - `naas_abi.secret` (for `secret.get`)
  - `naas_abi_core.logger`
- Required secret:
  - `OPENAI_API_KEY`
- Model configuration used in `create_model()`:
  - `model="gpt-4o"`
  - `temperature=0`
  - `max_tokens=4000`
  - `frequency_penalty=0.1`
  - `presence_penalty=0.1`

## Usage
```python
from naas_abi_marketplace.domains.project_manager.models.gpt_4o import create_model

model = create_model()
if model is None:
    raise RuntimeError("Missing OPENAI_API_KEY")

# Example usage depends on langchain_openai APIs; model is a ChatOpenAI instance.
```

## Caveats
- The module is explicitly marked **“NOT FUNCTIONAL YET”** and logs a warning on `create_model()` calls.
- The exported `model` variable is **always `None`** in the current file (not auto-created).
