# `new_agent` (Agent Generator CLI)

## What it is
- A small CLI-backed utility that scaffolds a new “agent” project/module from a template.
- Exposed as a `click` subcommand: `new agent <agent_name> [agent_path]`.

## Public API
- `new_agent(agent_name: str, agent_path: str = ".", extra_values: dict = {})`
  - Converts `agent_name` to PascalCase.
  - Resolves/creates the destination directory (`agent_path`).
  - Copies template files from the package’s `cli/new/templates/agent` into the destination using `Copier`.
  - Ensures `extra_values["module_name_snake"]` defaults to `"your_module_name"` if not provided.
  - Passes template values including:
    - `agent_name_pascal`: PascalCase agent name
    - any additional `extra_values`

CLI entrypoint:
- `_new_agent(agent_name: str, agent_path: str = ".")`
  - Registered via `@new.command("agent")`.
  - Delegates to `new_agent(...)`.

## Configuration/Dependencies
- **Dependencies**
  - `click` for CLI command/argument parsing.
  - `naas_abi_cli` to locate the installed package path for templates.
  - `Copier` (`naas_abi_cli.cli.utils.Copier.Copier`) to perform template copying.
  - `to_pascal_case` (`naas_abi_cli.cli.new.utils`) for name normalization.
- **Filesystem**
  - If `agent_path == "."`, it uses `os.getcwd()`.
  - Creates `agent_path` directory if it does not exist.

## Usage
### From Python
```python
from naas_abi_cli.cli.new.agent import new_agent

new_agent(
    "my_agent",
    agent_path=".",
    extra_values={"module_name_snake": "my_module"},
)
```

### From CLI
```bash
naas-abi-cli new agent my_agent .
```

## Caveats
- `extra_values` has a mutable default (`{}`); repeated calls in the same process may share and mutate the same dict instance.
