# Terminal Agent App

The terminal app provides an interactive CLI chat interface around an `Agent` instance.

## Entry point

Use `run_agent(agent)` from `naas_abi_core.apps.terminal_agent.main`.

## Features

- Live tool usage/response rendering.
- Agent output rendering with markdown.
- Conversation logs saved to `storage/datastore/interfaces/terminal_agent/<timestamp>.txt`.
- Basic commands:
  - `/?` help
  - `/reset`
  - `/bye` / `/exit`

## Example

```python
from naas_abi_core.apps.terminal_agent.main import run_agent

run_agent(my_agent)
```
