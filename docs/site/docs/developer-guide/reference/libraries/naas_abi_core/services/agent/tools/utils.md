# `can_bind_tools`

## What it is
A small utility that checks whether a LangChain `BaseChatModel` supports tool binding by attempting to bind a minimal tool.

## Public API
- `can_bind_tools(chat_model: BaseChatModel) -> bool`
  - Attempts to bind a single tool (`get_time_date`) to the provided chat model.
  - Returns `True` if binding succeeds without raising an exception; otherwise returns `False` and logs a debug message.

## Configuration/Dependencies
- Depends on:
  - `langchain_core.language_models.BaseChatModel`
  - `langchain_core.tools.tool` (used to define a test tool)
  - `naas_abi_core.logger` (debug logging on failure)
- The internal test tool uses:
  - `datetime` and `zoneinfo.ZoneInfo` (standard library)

## Usage
```python
from langchain_core.language_models import BaseChatModel
from naas_abi_core.services.agent.tools.utils import can_bind_tools

def check_model(model: BaseChatModel) -> None:
    if can_bind_tools(model):
        print("Model supports tool binding.")
    else:
        print("Model does NOT support tool binding.")
```

## Caveats
- This function uses a trial bind; any exception thrown by `chat_model.bind_tools(...)` is treated as “no tool support” (even if the failure is due to other issues, e.g., model misconfiguration).
- The bound tool is defined inside the function and is not exposed for reuse.
