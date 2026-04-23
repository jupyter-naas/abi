# claude_3_5_sonnet

## What it is
- A **non-functional template** for configuring an Anthropic Claude model (`claude-3-5-sonnet`) intended for the **Campaign Manager** domain.
- Provides a `create_model()` helper that attempts to build a `langchain_anthropic.ChatAnthropic` client when an API key is available.

## Public API
- `create_model() -> ChatAnthropic | None`
  - Logs a warning that this is **not functional yet**.
  - Reads `ANTHROPIC_API_KEY` via `naas_abi.secret.get("ANTHROPIC_API_KEY")`.
  - Returns:
    - a configured `ChatAnthropic` instance if the key exists
    - `None` if the key is missing (and logs an error)
- `model: None`
  - A module-level placeholder; **not initialized** (comment indicates it would be `create_model()` later).

## Configuration/Dependencies
- Dependencies:
  - `langchain_anthropic.ChatAnthropic`
  - `naas_abi.secret` for secret retrieval
  - `naas_abi_core.logger` for logging
- Required secret:
  - `ANTHROPIC_API_KEY` (retrieved through `secret.get(...)`)
- Model parameters used:
  - `model="claude-3-5-sonnet"`
  - `temperature=0.3`
  - `max_tokens=4000`

## Usage
```python
from naas_abi_marketplace.domains.campaign_manager.models.claude_3_5_sonnet import create_model

llm = create_model()
if llm is None:
    raise RuntimeError("Missing ANTHROPIC_API_KEY")

# Example call pattern depends on your LangChain version and setup.
# (This module only returns the configured ChatAnthropic instance.)
```

## Caveats
- The module is explicitly marked **“NOT FUNCTIONAL YET - template only”**.
- The exported `model` variable is `None` and will not work unless you call `create_model()` yourself.
- If `ANTHROPIC_API_KEY` is not available via `naas_abi.secret`, `create_model()` returns `None`.
