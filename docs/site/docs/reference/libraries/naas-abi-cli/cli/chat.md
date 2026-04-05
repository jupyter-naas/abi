# `chat`

## What it is
- A `click` CLI command that loads a module via `naas_abi_core.Engine` and launches a terminal agent from that module.

## Public API
- `chat(module_name: str = "", agent_name: str = "")`
  - Click command named **`chat`**.
  - Arguments:
    - `module-name` (str, default `""`): Module to load.
    - `agent-name` (str, default `""`): Agent class name to run.
  - Behavior:
    - Instantiates `Engine()`.
    - If both args are empty, uses `engine.configuration.default_agent` split into `"module agent"`.
    - Loads the module (`engine.load(module_names=[module_name])`).
    - Validates module exists in `engine.modules`; otherwise raises `ValueError`.
    - Iterates available agent classes in `engine.modules[module_name].agents`, matches by `__name__`, and runs it via `run_agent(agent_class.New())`.

## Configuration/Dependencies
- **Dependencies**
  - `click` for CLI registration and argument parsing.
  - `naas_abi_core`:
    - `naas_abi_core.engine.Engine.Engine` for configuration and module loading.
    - `naas_abi_core.apps.terminal_agent.main.run_agent` to execute the agent in a terminal loop.
    - `naas_abi_core.logger` for debug logging.
- **Configuration**
  - `engine.configuration.default_agent` is used when no arguments are provided. It must be a string formatted as `"module_name agent_name"` (split on a single space).

## Usage
### CLI
```bash
# Run using explicit module and agent names
naas-abi-cli chat my_module MyAgent

# Use the configured default agent (engine.configuration.default_agent)
naas-abi-cli chat
```

## Caveats
- If the module cannot be found after `engine.load(...)`, the command raises `ValueError: Module <name> not found`.
- If the agent name does not match any agent class `__name__` in the module, nothing is run (no explicit error is raised).
- Default agent parsing relies on `default_agent.split(" ")`; unexpected formatting (e.g., extra spaces or missing parts) may cause errors.
