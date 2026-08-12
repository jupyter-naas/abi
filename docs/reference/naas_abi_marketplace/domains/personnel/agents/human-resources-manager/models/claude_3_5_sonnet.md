# claude_3_5_sonnet (Human Resources model template)

## What it is
- A **non-functional template** for configuring an Anthropic `claude-3-5-sonnet` chat model for a Human Resources domain expert.
- Provides a `create_model()` factory that **may return** a `ChatAnthropic` instance **only if** an API key is available.
- The module-level `model` is currently **always `None`**.

## Public API
- `create_model() -> ChatAnthropic | None`
  - Logs a warning that this is a template.
  - Reads `ANTHROPIC_API_KEY` via `naas_abi.secret.get`.
  - Returns `None` if the key is missing; otherwise returns a configured `langchain_anthropic.ChatAnthropic`.

- `model: None`
  - Placeholder; not initialized (comment indicates it “would be” `create_model()`).

## Configuration/Dependencies
- Dependencies:
  - `langchain_anthropic.ChatAnthropic`
  - `naas_abi.secret` (for `secret.get("ANTHROPIC_API_KEY")`)
  - `naas_abi_core.logger`
- Required secret/environment:
  - `ANTHROPIC_API_KEY` must be retrievable via `secret.get(...)`.

## Usage
```python
from naas_abi_marketplace.domains.human-resources-manager.models.claude_3_5_sonnet import create_model

model = create_model()
if model is None:
    raise RuntimeError("Missing ANTHROPIC_API_KEY")

# Use `model` according to langchain_anthropic.ChatAnthropic expectations.
```

## Caveats
- Marked **“NOT FUNCTIONAL YET - template only”**:
  - Always emits a warning when `create_model()` is called.
  - The module-level `model` is **not instantiated** (set to `None`).
