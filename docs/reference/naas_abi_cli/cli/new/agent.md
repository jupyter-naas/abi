# `new_agent` (Agent scaffold generator)

## What it is
- Scaffolds a new agent project into a target directory using a template folder.
- Exposed as a Click subcommand under `new agent`.
- Supports two template sets:
  - Local/in-engine agent templates (`templates/agent`)
  - Remote module SDK agent templates (`templates/remote_agent`)

## Public API
- `new_agent(agent_name: str, agent_path: str = ".", extra_values: dict | None = None, remote: bool = False)`
  - Converts `agent_name` to PascalCase.
  - Resolves `agent_path="."` to the current working directory.
  - Ensures `agent_path` exists (creates directories if needed).
  - Chooses templates based on `remote`:
    - `remote=False` → `cli/new/templates/agent`
    - `remote=True` → `cli/new/templates/remote_agent`
  - Ensures `extra_values["module_name_snake"]` is set (defaults to `"your_module_name"`).
  - Copies templates via `Copier.copy()` with values:
    - `agent_name_pascal` (PascalCase)
    - plus any `extra_values`.

- CLI command: `naas-abi-cli new agent AGENT_NAME [AGENT_PATH]`
  - Implemented by `_new_agent(agent_name, agent_path=".")`.
  - Detects whether the target is a remote module using:
    - `remote = is_remote_module(target_dir(agent_path))`
  - Calls `new_agent(..., remote=remote)`.
  - If `remote=True`, prints post-generation instructions via `click.echo(...)`.

## Configuration/Dependencies
- **Dependencies**
  - `click` (CLI command / arguments / output)
  - `naas_abi_cli` (to locate the installed templates directory)
  - `naas_abi_cli.cli.utils.Copier.Copier` (template copy engine)
  - `.utils.to_pascal_case` (agent name normalization)
  - `.remote_module.is_remote_module`, `.remote_module.target_dir` (remote detection)

- **Template resolution**
  - Template root is resolved from the installed package location:
    - `os.path.join(os.path.dirname(naas_abi_cli.__file__), "cli/new/templates/...")`

## Usage

### From Python
```python
from naas_abi_cli.cli.new.agent import new_agent

new_agent("my agent", agent_path=".", extra_values={"module_name_snake": "my_module"})
```

### From CLI
```bash
naas-abi-cli new agent "My Agent" .
```

## Caveats
- `agent_path="."` is treated specially and replaced with `os.getcwd()`.
- `extra_values` defaults to `None` (safe) and is internally replaced with a new dict.
