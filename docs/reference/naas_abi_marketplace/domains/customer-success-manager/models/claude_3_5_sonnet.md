# claude_3_5_sonnet

## What it is
A **non-functional template** for creating a `ChatAnthropic` client configured for the **Customer Success Manager** domain using the `claude-3-5-sonnet` model. The module currently **does not instantiate** the model by default.

## Public API
- `create_model() -> ChatAnthropic | None`
  - Attempts to build and return a `langchain_anthropic.ChatAnthropic` instance.
  - Logs a warning that this is **not functional yet**.
  - Returns `None` if `ANTHROPIC_API_KEY` is not available via `naas_abi.secret.get()`.

- `model: None`
  - Placeholder module-level variable; intentionally not created (comment indicates it “would be: `create_model()`”).

## Configuration/Dependencies
- Environment/secret:
  - `ANTHROPIC_API_KEY` (retrieved via `naas_abi.secret.get("ANTHROPIC_API_KEY")`)
- Dependencies:
  - `langchain_anthropic.ChatAnthropic`
  - `naas_abi.secret`
  - `naas_abi_core.logger`

## Usage
```python
from naas_abi_marketplace.domains.customer_success_manager.models.claude_3_5_sonnet import create_model

m = create_model()
if m is None:
    raise RuntimeError("Missing ANTHROPIC_API_KEY")

# Example: use according to ChatAnthropic/LangChain APIs in your environment
# response = m.invoke("Hello")
```

## Caveats
- The module is explicitly marked **“NOT FUNCTIONAL YET”** and logs a warning on `create_model()`.
- `model` is not initialized; you must call `create_model()` manually.
- If `ANTHROPIC_API_KEY` is missing, the function logs an error and returns `None`.
