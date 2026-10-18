# `new_pipeline`

## What it is
- A helper (and Click subcommand) that scaffolds a new **pipeline** from the built-in template directory into a target path.
- Normalizes the provided pipeline name to **PascalCase** and passes it into the template renderer/copy step.

## Public API
- `new_pipeline(pipeline_name: str, pipeline_path: str = ".", extra_values: dict | None = None)`
  - Ensures the destination directory exists.
  - Copies pipeline templates into `pipeline_path`.
  - Provides template values:
    - `pipeline_name_pascal` (PascalCase version of `pipeline_name`)
    - plus any `extra_values` merged in.
- CLI command: `new pipeline PIPELINE_NAME [PIPELINE_PATH]`
  - Implemented by `_new_pipeline(...)` (Click command function).
  - Calls `refuse_in_remote_module("pipeline", pipeline_path)` then `new_pipeline(...)`.

## Configuration/Dependencies
- **Dependencies**
  - `click` for CLI wiring.
  - `naas_abi_cli` to locate the packaged templates.
  - `naas_abi_cli.cli.utils.Copier.Copier` to copy/render templates.
  - Local utilities:
    - `to_pascal_case` (name normalization)
    - `refuse_in_remote_module` (guards against running in a “remote module” context)
- **Template location**
  - Resolved at runtime to:
    - `os.path.join(os.path.dirname(naas_abi_cli.__file__), "cli/new/templates/pipeline")`

## Usage

### CLI
```bash
naas-abi-cli new pipeline MyPipeline .
```

### Python
```python
from naas_abi_cli.cli.new.pipeline import new_pipeline

new_pipeline("my_pipeline", ".")
```

## Caveats
- If `pipeline_path == "."`, it is replaced with `os.getcwd()`.
- `extra_values` defaults to `None` (safe); a new dict is created internally when omitted.
- The CLI command calls `refuse_in_remote_module(...)` before scaffolding; behavior depends on that function’s implementation.
