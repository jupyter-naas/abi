# `agent_tools`

## What it is
A small adapter that exposes a `naas_abi_sdk` agent as a LangChain `StructuredTool`, with both async and sync invocation support (sync requires an existing running event loop).

## Public API
- `agent_tools(agent: AgentProxy) -> list[StructuredTool]`
  - Builds and returns a single-item list containing a LangChain `StructuredTool`.
  - The tool:
    - Uses `agent.name` as the tool name.
    - Uses `agent.description` (or `agent.name` if missing) as the description.
    - Supports:
      - `tool.ainvoke(...)` via an async coroutine.
      - `tool.invoke(...)` via a sync wrapper that schedules work on an existing event loop.

### Invocation behavior
- Async path (`ainvoke`):
  - Reads `thread_id` from `config["configurable"]["thread_id"]` if present; otherwise uses `agent.state.thread_id`.
  - Duplicates the agent with a scoped `AgentState(thread_id)` and calls `scoped.invoke(prompt)`.

- Sync path (`invoke`):
  - Requires a running event loop captured at `agent_tools(...)` creation time.
  - Schedules the async invocation onto that loop using `asyncio.run_coroutine_threadsafe(...)`.

## Configuration/Dependencies
- Depends on LangChain core:
  - `langchain_core.tools.StructuredTool`
  - `langchain_core.runnables.RunnableConfig`
- Depends on `naas_abi_sdk`:
  - `naas_abi_sdk.agent.AgentState`
  - An `AgentProxy` instance (type is imported only for type checking)
- Runnable config key used:
  - `config["configurable"]["thread_id"]` (optional)

## Usage
```python
import asyncio
from naas_abi_sdk.agent_tools import agent_tools

async def main(agent):
    tool = agent_tools(agent)[0]

    # Async call (recommended)
    result = await tool.ainvoke(
        {"prompt": "Hello"},
        config={"configurable": {"thread_id": "123"}},
    )
    print(result)

# asyncio.run(main(agent))
```

## Caveats
- Creating and using the sync `tool.invoke(...)` requires that `agent_tools(...)` is called while an event loop is already running.
- If you are on the same event loop thread, do not use `tool.invoke(...)`; use `tool.ainvoke(...)` instead.
- If no event loop is running when the tool is created, sync invocation will raise:
  - `"Create remote tools inside the running module; use ainvoke for async callers"`
