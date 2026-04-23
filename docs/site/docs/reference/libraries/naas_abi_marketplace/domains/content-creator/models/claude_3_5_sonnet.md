# claude_3_5_sonnet

## What it is
- A **non-functional template** for configuring an Anthropic **Claude 3.5 Sonnet** chat model for the **Content Creator** domain.
- Provides a `create_model()` helper to build a `langchain_anthropic.ChatAnthropic` instance when an API key is available.

## Public API
- `create_model() -> ChatAnthropic | None`
  - Logs that the model is **not functional yet** (template-only).
  - Reads `ANTHROPIC_API_KEY` via `naas_abi.secret.get(...)`.
  - Returns:
    - a configured `ChatAnthropic` client when the API key is present
    - `None` when the key is missing (and logs an error)
- Module variable: `model`
  - Currently set to `None` (comment indicates it *would* be `create_model()` in the future).

## Configuration/Dependencies
- Dependencies:
  - `langchain_anthropic.ChatAnthropic`
  - `naas_abi.secret` (for secret retrieval)
  - `naas_abi_core.logger` (for warnings/errors)
- Required secret:
  - `ANTHROPIC_API_KEY`
- Model configuration (as coded):
  - `model="claude-3-5-sonnet"`
  - `temperature=0.1`
  - `max_tokens=4000`

## Usage
```python
from naas_abi_marketplace.domains.content_creator.models.claude_3_5_sonnet import create_model

model = create_model()
if model is None:
    raise RuntimeError("Missing ANTHROPIC_API_KEY")

# Example call shape depends on your LangChain usage;
# the object returned is a langchain_anthropic.ChatAnthropic instance.
```

## Caveats
- The module is explicitly marked **“NOT FUNCTIONAL YET - template only”**.
- `create_model()` returns `None` if `ANTHROPIC_API_KEY` is not available.
- The module-level `model` is **always `None`** in current code (it does not auto-instantiate).
