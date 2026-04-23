# deepseek_r1

## What it is
- A **non-functional template** for configuring a `deepseek-r1` chat model (Data Engineer domain) using `langchain_openai.ChatOpenAI`.
- Provides a `create_model()` factory that **logs warnings** and returns a configured model **only if** `DEEPSEEK_API_KEY` is available.

## Public API
- `create_model() -> ChatOpenAI | None`
  - Creates and returns a `ChatOpenAI` instance configured for the `"deepseek-r1"` model.
  - Behavior:
    - Logs a warning that the model is not functional yet.
    - Reads `DEEPSEEK_API_KEY` via `naas_abi.secret.get`.
    - If missing, logs an error and returns `None`.
    - Otherwise returns `ChatOpenAI(model="deepseek-r1", temperature=0.1, max_tokens=4000, api_key=...)`.
- `model: None`
  - Placeholder module-level variable (currently always `None`).
  - Comment indicates it *would be* `create_model()` in a functional version.

## Configuration/Dependencies
- Environment/Secrets:
  - `DEEPSEEK_API_KEY` (retrieved via `naas_abi.secret.get("DEEPSEEK_API_KEY")`)
- Python dependencies:
  - `langchain_openai.ChatOpenAI`
  - `naas_abi.secret`
  - `naas_abi_core.logger`

## Usage
```python
from naas_abi_marketplace.domains.data_engineer.models.deepseek_r1 import create_model

model = create_model()
if model is None:
    raise RuntimeError("Missing DEEPSEEK_API_KEY or model not available")

# If a compatible ChatOpenAI backend is available, you could use it like:
# response = model.invoke("Explain data warehouse vs data lake.")
# print(response)
```

## Caveats
- The module is explicitly marked **NOT FUNCTIONAL YET** and logs a warning on `create_model()` call.
- The exported `model` variable is a **placeholder** and is not initialized automatically.
