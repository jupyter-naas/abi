# orchestration (naas_abi_cli.cli.new.orchestration)

## What it is
- A CLI subcommand and helper function to scaffold a new “orchestration” project from bundled templates into a target directory.

## Public API
- `new_orchestration(orchestration_name: str, orchestration_path: str = ".", extra_values: dict = {})`
  - Creates the destination directory (if missing) and copies orchestration templates into it.
  - Normalizes `orchestration_name` to PascalCase and passes it to templates as `orchestration_name_pascal`.
- CLI command: `new orchestration <orchestration_name> [orchestration_path]`
  - Registered as a `click` command via `@new.command("orchestration")`.
  - Delegates to `new_orchestration(...)`.

## Configuration/Dependencies
- **Dependencies**
  - `click` for CLI command registration.
  - `naas_abi_cli` to locate packaged templates.
  - `Copier` (`naas_abi_cli.cli.utils.Copier.Copier`) to copy template files.
  - `to_pascal_case` (`naas_abi_cli.cli.new.utils.to_pascal_case`) for name normalization.
  - `os` for filesystem operations.
- **Templates source path**
  - Computed as: `<naas_abi_cli package dir>/cli/new/templates/orchestration`

## Usage

### CLI
```bash
naas-abi-cli new orchestration MyOrchestration .
```

### Python
```python
from naas_abi_cli.cli.new.orchestration import new_orchestration

new_orchestration("my_orchestration", orchestration_path=".")
```

## Caveats
- If `orchestration_path="."`, the current working directory (`os.getcwd()`) is used.
- The default `extra_values` argument is a mutable dict (`{}`); avoid mutating it across calls.
