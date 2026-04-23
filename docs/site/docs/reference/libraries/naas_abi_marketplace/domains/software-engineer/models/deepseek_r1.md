# deepseek_r1

## What it is
- A **non-functional template** for configuring a “DeepSeek R1” chat model for the *Software Engineer* domain.
- Currently uses `langchain_openai.ChatOpenAI` as a placeholder and logs warnings/errors.

## Public API
- `create_model() -> ChatOpenAI | None`
  - Logs a warning that the model is not functional yet.
  - Reads `DEEPSEEK_API_KEY` via `naas_abi.secret.get`.
  - Returns:
    - a `ChatOpenAI` instance configured with `model="deepseek-r1"` (placeholder) if the key exists
    - `None` if the key is missing (and logs an error)
- Module variable: `model`
  - Always `None` (the creation call is commented out).

## Configuration/Dependencies
- Environment/secret:
  - `DEEPSEEK_API_KEY` (required; retrieved via `naas_abi.secret.get("DEEPSEEK_API_KEY")`)
- Python dependencies:
  - `langchain_openai.ChatOpenAI`
  - `naas_abi.secret`
  - `naas_abi_core.logger`

## Usage
```python
from naas_abi_marketplace.domains.software_engineer.models.deepseek_r1 import create_model

model = create_model()
if model is None:
    raise RuntimeError("Missing DEEPSEEK_API_KEY or model template not usable")
```

## Caveats
- Marked **“NOT FUNCTIONAL YET”** in code and logs; it is a template only.
- Uses `ChatOpenAI` with a placeholder model name (`"deepseek-r1"`); no actual DeepSeek integration is implemented.
- The module-level `model` is not initialized (always `None`).
