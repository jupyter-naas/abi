# `default_tools`

## What it is
A factory function that builds a standard set of LangChain tools (`Tool`/`BaseTool`) for an agent-like object (`self`). The returned tools provide basic introspection (available tools, sub-agents, intents) and optionally agent/supervisor context.

## Public API
- `default_tools(self) -> list[Tool | BaseTool]`
  - Returns a list of LangChain tools created with `langchain_core.tools.tool`.
  - Tools included:
    - `get_time_date(timezone: str = "Europe/Paris") -> str` (`return_direct=False`)
      - Returns current time/date formatted as `"%H:%M:%S %Y-%m-%d"` in the given timezone.
    - `list_tools_available() -> str` (`return_direct=True`)
      - Lists tools from `self._structured_tools`, excluding those whose name starts with `"transfer_to"`.
    - `list_subagents_available() -> str` (`return_direct=True`)
      - Lists sub-agents from `self._agents` (name and description).
    - `list_intents_available() -> str` (`return_direct=True`)
      - Groups and renders intents from `self._intents` into markdown sections/tables.
    - Conditionally included (only if `self.state.supervisor_agent is not None` **or** `len(self._agents) > 0`):
      - `get_current_active_agent() -> str` (`return_direct=True`)
        - Returns `self._state.current_active_agent` or falls back to `self.name`.
      - `get_supervisor_agent() -> str` (`return_direct=True`)
        - Returns supervisor agent name if present; otherwise a “no supervisor” message.

## Configuration/Dependencies
- Depends on `langchain_core.tools`:
  - `tool` decorator to define tools.
  - `Tool` / `BaseTool` types for return annotation.
- `get_time_date` uses:
  - `datetime.datetime.now`
  - `zoneinfo.ZoneInfo` (Python 3.9+)
- `list_intents_available` imports from `..beta.IntentMapper`:
  - `Intent`, `IntentScope`, `IntentType`
- Expected attributes on `self` (agent object):
  - `self._structured_tools`: iterable of tools with `.name` and `.description`
  - `self._agents`: iterable of agents with `.name` and `.description`
  - `self._intents`: iterable of intents with `intent_scope`, `intent_type`, `intent_value`, `intent_target`
  - `self._state.current_active_agent`, `self._state.supervisor_agent`
  - `self.state.supervisor_agent` (note: both `self._state` and `self.state` are referenced)
  - `self.name`

## Usage
```python
from naas_abi_core.services.agent.tools.default_tools import default_tools

# `agent` must provide the attributes used by the tools (see Dependencies).
tools = default_tools(agent)

# Example: find and call the time tool (LangChain tools are callable)
time_tool = next(t for t in tools if t.name == "get_time_date")
print(time_tool.invoke({"timezone": "Europe/Paris"}))
```

## Caveats
- The conditional inclusion of agent/supervisor tools checks `self.state.supervisor_agent`, but the tool implementations read from `self._state...`. If `self.state` and `self._state` are not consistent/present, behavior may be incorrect or raise attribute errors.
- `list_intents_available` contains a comparison `if intent.intent_scope == IntentType.RAW:`; this compares a scope value to an intent type enum, which may be unintended depending on the actual enum definitions.
- If `self._agents` is missing, the final conditional `len(self._agents) > 0` will raise (there is no guard there), even though some individual tool functions guard with `hasattr`.
