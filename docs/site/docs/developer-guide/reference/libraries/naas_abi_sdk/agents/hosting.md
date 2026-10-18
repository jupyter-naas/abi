# hosting

## What it is
Utilities for hosting an SDK `Agent` behind an `agent.invoke.v1`-style handler, with:
- A stable memory/checkpoint scope ID helper.
- Optional document-backed checkpointing setup.
- An `AgentHandler` that scopes each invocation to the caller’s `InvocationContext.thread_id`.

## Public API

- `agent_memory_id(module_id: str, agent_name: str, version: int = 1) -> str`
  - Builds a stable checkpoint/memory scope ID for an agent across replicas/restarts.
  - Format: `"{module_id}.{agent_name}.v{version}"`.

- `document_memory(documents: Any, agent_id: str) -> Any`
  - Creates and sets up a `DocumentCheckpointSaver` using a module’s document service (`documents`) and the given `agent_id`.
  - Returns the configured saver.

- `class AgentHandler`
  - Wraps an `Agent` to provide invocation methods suitable for hosting.
  - Methods:
    - `invoke(prompt: str, context: InvocationContext) -> str`
      - Duplicates the agent scoped to `context.thread_id`, then calls `Agent.invoke`.
    - `stream_invoke(prompt: str, context: InvocationContext) -> AsyncIterator[dict[str, str]]`
      - Duplicates the agent scoped to `context.thread_id`, then yields events from `Agent.stream_invoke`.
      - Stops early if `context.cancelled.is_set()` becomes true.
      - Ensures the underlying async stream is closed (`aclose()`) in a `finally` block.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_sdk.agents.agent.AgentSharedState` (used to scope `thread_id`).
  - `naas_abi_sdk.langgraph.DocumentCheckpointSaver` (imported lazily inside `document_memory`).
- Types referenced:
  - `InvocationContext` must provide:
    - `thread_id`
    - `cancelled` (with `.is_set()`)

## Usage

```python
import asyncio
from naas_abi_sdk.agents.hosting import AgentHandler, agent_memory_id

# agent: an instance of naas_abi_sdk.agents.agent.Agent
# context: an instance of naas_abi_sdk.agent_host.InvocationContext

async def main(agent, context):
    handler = AgentHandler(agent)

    # Stable memory/checkpoint scope ID
    mem_id = agent_memory_id("my_module", "my_agent", version=1)
    print(mem_id)

    # Single response
    text = await handler.invoke("Hello", context)
    print(text)

    # Streaming response/events
    async for event in handler.stream_invoke("Stream hello", context):
        print(event)

# asyncio.run(main(agent, context))
```

## Caveats
- `stream_invoke` will stop yielding if `context.cancelled.is_set()` becomes true.
- `document_memory` performs async setup; it must be awaited before use.
