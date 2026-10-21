# claude_3_5_sonnet

## What it is
- A **non-functional template** for configuring an Anthropic `claude-3-5-sonnet` chat model for the *Community Manager* domain.
- Provides a `create_model()` factory that attempts to create a `langchain_anthropic.ChatAnthropic` instance, gated by the `ANTHROPIC_API_KEY` secret.

## Public API
- `create_model() -> ChatAnthropic | None`
  - Logs a warning that this is **not functional yet**.
  - Reads `ANTHROPIC_API_KEY` via `naas_abi.secret.get`.
  - Returns:
    - a configured `ChatAnthropic` instance if the key is present
    - `None` if the key is missing (and logs an error)
- Module variable: `model`
  - Currently set to `None` (comment indicates it “would be” `create_model()`).

## Configuration/Dependencies
- Dependencies:
  - `langchain_anthropic.ChatAnthropic`
  - `naas_abi.secret` (used to retrieve `ANTHROPIC_API_KEY`)
  - `naas_abi_core.logger` (warning/error logging)
- Required secret/environment:
  - `ANTHROPIC_API_KEY`
- Model parameters (as configured in code):
  - `model="claude-3-5-sonnet"`
  - `temperature=0.1`
  - `max_tokens=4000`

## Usage
```python
from naas_abi_marketplace.domains.community_manager.models.claude_3_5_sonnet import create_model

model = create_model()
if model is None:
    raise RuntimeError("Missing ANTHROPIC_API_KEY or model not available")

# Use `model` per langchain_anthropic.ChatAnthropic API
```

## Caveats
- The module is explicitly marked **“NOT FUNCTIONAL YET - template only”** and always logs a warning when `create_model()` is called.
- `model` is not instantiated automatically (it remains `None`).
