# `new_agent` (Agent scaffold generator)

## What it is
- A small helper used by the `naas-abi-cli` Click CLI to generate (“scaffold”) a new agent project from a template directory into a target path.

## Public API
- `new_agent(agent_name: str, agent_path: str = ".", extra_values: dict = {})`
  - Normalizes `agent_name` to PascalCase.
  - Ensures `agent_path` exists (defaults to current working directory when `"."`).
  - Copies templates from `naas_abi_cli/cli/new/templates/agent` into `agent_path` using `Copier`.
  - Provides template values:
    - `agent_name_pascal`: PascalCase agent name.
    - `module_name_snake`: defaults to `"your_module_name"` if not provided in `extra_values`.
- CLI command: `new agent`
  - Implemented as Click command function `_new_agent(agent_name, agent_path=".")`.
  - Delegates to `new_agent(...)`.

## Configuration/Dependencies
- **Dependencies**
  - `click` (CLI command registration and argument parsing)
  - `naas_abi_cli` (used to locate the templates directory)
  - `naas_abi_cli.cli.utils.Copier.Copier` (performs template copying)
  - `.utils.to_pascal_case` (name normalization)
- **Templates location**
  - Resolved at runtime via:
    - `os.path.join(os.path.dirname(naas_abi_cli.__file__), "cli/new/templates/agent")`

## Usage
### From Python
```python
from naas_abi_cli.cli.new.agent import new_agent

new_agent("my agent", agent_path=".", extra_values={"module_name_snake": "my_module"})
```

### From CLI
```bash
naas-abi-cli new agent MyAgent .
```

## Caveats
- `extra_values` has a mutable default (`{}`); repeated calls may share state across invocations if the dict is mutated.
- Passing `"."` as `agent_path` is treated specially and replaced with the current working directory.
