# `chat` (CLI command)

## What it is
A `click` CLI command that binds a local identity for event publishing, loads a module via `naas_abi_core`’s `Engine`, and runs a named terminal agent from that module.

## Public API
- `chat(module_name: str = "", agent_name: str = "")`
  - Click command name: `chat`
  - CLI args:
    - `module-name` (str, default `""`)
    - `agent-name` (str, default `""`)
  - Behavior:
    - Wraps execution in `bind_local_identity()` context.
    - Delegates to internal `_chat(module_name, agent_name)`.

- `_chat(module_name: str, agent_name: str) -> None` (internal helper)
  - Behavior:
    - Calls `use_auto_engine_role()` then creates `Engine()`.
    - If both args are empty, derives them from `engine.configuration.default_agent` by `split(" ")`.
    - Loads the module: `engine.load(module_names=[module_name])`.
    - Validates `module_name in engine.modules`; otherwise raises `ValueError`.
    - Iterates `engine.modules[module_name].agents` and runs the first class whose `__name__` matches `agent_name`:
      - `run_agent(agent_class.New())`

## Configuration/Dependencies
- Dependencies:
  - `click`
  - `naas_abi_core`:
    - `naas_abi_core.services.event.local_identity.bind_local_identity`
    - `naas_abi_core.engine.Engine.Engine`
    - `naas_abi_core.apps.terminal_agent.main.run_agent`
    - `naas_abi_core.logger`
  - `naas_abi_cli.cli.engine_role.use_auto_engine_role`
- Configuration:
  - `engine.configuration.default_agent` must be formatted like `"module_name agent_name"` when relying on defaults.

## Usage
Minimal CLI usage (via your package entrypoint that registers this command):

```bash
# Run a specific agent
naas-abi chat my_module MyAgent

# Use engine.configuration.default_agent (formatted "module agent")
naas-abi chat
```

## Caveats
- If no agent class name matches `agent_name`, nothing is run and no error is raised.
- Default resolution uses `engine.configuration.default_agent.split(" ")`; unexpected spacing/format can break parsing.
- The selected agent class is expected to provide a `New()` method; it is invoked dynamically.
