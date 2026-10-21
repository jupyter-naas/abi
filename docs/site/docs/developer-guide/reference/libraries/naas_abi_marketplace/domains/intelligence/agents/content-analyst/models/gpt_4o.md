# gpt_4o

## What it is
- A **non-functional template** for configuring a `gpt-4o` chat model (Content Analyst domain) using `langchain_openai.ChatOpenAI`.
- Provides a `create_model()` factory that validates `OPENAI_API_KEY` and returns a configured model instance or `None`.

## Public API
- `create_model() -> ChatOpenAI | None`
  - Logs a warning that the template is not functional yet.
  - Reads `OPENAI_API_KEY` via `naas_abi.secret.get`.
  - Returns:
    - A `ChatOpenAI` instance configured with:
      - `model="gpt-4o"`
      - `temperature=0.1`
      - `max_tokens=4000`
    - `None` if the API key is missing (and logs an error).
- `model: None`
  - Placeholder global model instance (currently not created).

## Configuration/Dependencies
- Environment/Secrets:
  - `OPENAI_API_KEY` must be available via `naas_abi.secret.get("OPENAI_API_KEY")`.
- Dependencies:
  - `langchain_openai.ChatOpenAI`
  - `naas_abi.secret`
  - `naas_abi_core.logger`

## Usage
```python
from naas_abi_marketplace.domains.content_analyst.models.gpt_4o import create_model

model = create_model()
if model is None:
    raise RuntimeError("Missing OPENAI_API_KEY")

# Use model per LangChain ChatOpenAI interface
# e.g., model.invoke("Hello")  # depending on your LangChain version
```

## Caveats
- Marked as **NOT FUNCTIONAL YET** in code and logs a warning on creation.
- The module-level `model` is **always `None`** (it does not call `create_model()`).
