# `chat` (CLI command)

## What it is
A `click`-based CLI command that loads a module via `naas_abi_core`’s `Engine` and runs a named terminal agent from that module.

## Public API
- `chat(module_name: str = "", agent_name: str = "")`
  - Click command named `chat`.
  - Arguments:
    - `module-name` (string, default `""`)
    - `agent-name` (string, default `""`)
  - Behavior:
    - If both arguments are empty, uses `engine.configuration.default_agent` and splits it into `"module agent"`.
    - Loads the module via `engine.load(module_names=[module_name])`.
    - Validates the module exists in `engine.modules`; otherwise raises `ValueError`.
    - Searches `engine.modules[module_name].agents` for a class whose `__name__` matches `agent_name`.
    - Runs the agent via `naas_abi_core.apps.terminal_agent.main.run_agent(agent_class.New())`.

## Configuration/Dependencies
- **Dependencies**
  - `click`
  - `naas_abi_core`:
    - `naas_abi_core.engine.Engine.Engine`
    - `naas_abi_core.apps.terminal_agent.main.run_agent`
    - `naas_abi_core.logger`
- **Configuration**
  - `engine.configuration.default_agent` must be a string formatted like `"module_name agent_name"` if relying on defaults.

## Usage
```python
# Running through Click normally happens via your package's CLI entrypoint.
# If you have a Click group, it typically registers `chat` as a subcommand.
```

Example CLI invocation (assuming your project exposes this command):
```bash
# Use explicit module and agent
naas-abi chat my_module MyAgent

# Use defaults from engine.configuration.default_agent
naas-abi chat
```

## Caveats
- If `module_name` is loaded but **no agent class name matches** `agent_name`, nothing is run and no error is raised.
- `default_agent` is split on a single space (`split(" ")`); unexpected formatting may break default resolution.
- The agent class is expected to provide a `New()` constructor-like method (called dynamically).
