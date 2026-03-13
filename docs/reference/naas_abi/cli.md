# `naas_abi.cli`

## What it is
A small interactive CLI module that scaffolds ABI modules and components by copying files from `src/core/__templates__`, performing simple string replacements, and (for modules) enabling the new module in YAML config files.

## Public API
- `format_module_name(name: str) -> str`
  - Normalizes a raw module name (lowercase, underscores, removes invalid characters).
- `get_component_selection() -> dict`
  - Prompts for which template component folders to include when creating a module.
- `enable_module_in_config(module_path: str) -> None`
  - Updates `config.yaml` or `config.<ENV>.yaml` (if present) to ensure the given module path is listed under `modules` with `enabled: True`.
- `create_new_module() -> None`
  - Interactive module generator:
    - Prompts for module name and target location (`src/core`, `src/custom`, marketplace paths).
    - Copies selected components from `src/core/__templates__` into the new module directory.
    - Rewrites template references inside `.py`, `.md`, `.ttl` files and renames filenames containing `Template`.
    - Attempts to enable the module in config.
- `create_agent() -> None`
  - Interactive agent generator:
    - Copies `TemplateAgent.py` and `TemplateAgent_test.py` into a chosen target folder as `<Name>Agent.py` and `<Name>Agent_test.py`.
    - Adjusts imports based on target location.
    - Ensures a `models/` folder exists at the module root (creates it from templates if missing).
- `create_component(component_type: str, template_files: list[str], file_suffix: str) -> None`
  - Generic interactive component generator used by the specific helpers below.
- `create_integration() -> None`
  - Creates an integration from template files.
- `create_workflow() -> None`
  - Creates a workflow from template files.
- `create_pipeline() -> None`
  - Creates a pipeline from template files.
- `create_ontology() -> None`
  - Creates ontology `.ttl` files from templates.
- `main() -> None`
  - CLI entry point. Dispatches based on `sys.argv[1]`:
    - `create-module`, `create-agent`, `create-integration`, `create-workflow`, `create-pipeline`, `create-ontology`.

## Configuration/Dependencies
- Filesystem expectations:
  - Templates must exist under `src/core/__templates__/` (e.g., `agents/TemplateAgent.py`, `models/`, etc.).
  - Config files are optional:
    - Reads/writes `config.yaml` and may prefer `config.<ENV>.yaml` depending on environment resolution.
- Environment/config resolution for enabling modules:
  - Uses `ENV` environment variable if set.
  - Otherwise may inspect `config.yaml` to find a dotenv secret adapter and read `ENV` from that dotenv file.
- Python dependencies:
  - `PyYAML` (`yaml.safe_load`, `yaml.dump`)
  - `rich` (`Console`, `Prompt`)
  - Optional at runtime (only when resolving ENV via dotenv adapter):
    - `naas_abi_core.services.secret.adaptors.secondary.dotenv_secret_secondaryadaptor.DotenvSecretSecondaryAdaptor`

## Usage
Run as a module/script and pass a command:

```python
import sys
from naas_abi import cli

sys.argv = ["naas-abi", "create-module"]
cli.main()
```

Or from a shell (equivalent behavior when executed as a script):

```bash
python -m naas_abi.cli create-agent
```

Available commands:
- `create-module`
- `create-agent`
- `create-integration`
- `create-workflow`
- `create-pipeline`
- `create-ontology`

## Caveats
- The CLI is interactive (uses `rich.prompt.Prompt`) and expects to run in a TTY.
- Scaffolding assumes a specific repository layout (`src/core/__templates__`); missing templates will cause errors.
- `enable_module_in_config()` may modify YAML config files in-place and will attempt to sort `modules` by `path`.
- Module name validation in `create_new_module()` allows `-` and `.` by regex, but `format_module_name()` will strip hyphens (keeps only `[a-z0-9_]`).
