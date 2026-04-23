# gpt_4o

## What it is
- A **non-functional template** for configuring a `gpt-4o` chat model (via `langchain_openai.ChatOpenAI`) for the **Sales Development Representative** domain.
- Emits warnings/errors via `naas_abi_core.logger` and reads the OpenAI key via `naas_abi.secret`.

## Public API
- `create_model() -> ChatOpenAI | None`
  - Logs a warning that this is **not functional yet**.
  - Retrieves `OPENAI_API_KEY` via `secret.get("OPENAI_API_KEY")`.
  - Returns:
    - A configured `ChatOpenAI` instance if the API key is present.
    - `None` if the API key is missing (and logs an error).
- Module attribute: `model`
  - Currently set to `None` (comment indicates it “would be: `create_model()`”).

## Configuration/Dependencies
- Dependencies:
  - `langchain_openai.ChatOpenAI`
  - `naas_abi.secret` (expects `secret.get("OPENAI_API_KEY")`)
  - `naas_abi_core.logger`
- Model configuration used in `create_model()`:
  - `model="gpt-4o"`
  - `temperature=0.2`
  - `max_tokens=4000`
  - `api_key=<OPENAI_API_KEY>`

## Usage
```python
from naas_abi_marketplace.domains.sales-development-representative.models.gpt_4o import create_model

llm = create_model()
if llm is None:
    raise RuntimeError("Missing OPENAI_API_KEY")

# Example: in LangChain, you would typically call llm.invoke(...) with messages,
# but this module only provides the model factory.
```

## Caveats
- The module is explicitly marked **“NOT FUNCTIONAL YET”** and logs a warning on `create_model()`.
- The exported `model` variable is **always `None`** in the current code (no automatic initialization).
- If `OPENAI_API_KEY` is not available via `naas_abi.secret`, `create_model()` returns `None`.
