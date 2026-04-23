# `pipeline` (new pipeline generator)

## What it is
- A small CLI-backed helper that scaffolds a new “pipeline” from a template directory into a target path.
- Normalizes the pipeline name to PascalCase and copies template files using an internal `Copier`.

## Public API
- `new_pipeline(pipeline_name: str, pipeline_path: str = ".", extra_values: dict = {})`
  - Creates the destination directory (if needed) and copies pipeline templates into it.
  - Injects template values including `pipeline_name_pascal`.
- CLI command: `new pipeline PIPELINE_NAME [PIPELINE_PATH]`
  - Entry point registered via Click (`@new.command("pipeline")`), calls `new_pipeline(...)`.

## Configuration/Dependencies
- **Dependencies**
  - `click` for CLI command/arguments.
  - `naas_abi_cli` to locate the built-in template directory.
  - `naas_abi_cli.cli.utils.Copier.Copier` to perform the copy.
  - `to_pascal_case` (local utility) for name normalization.
- **Template location**
  - Resolved at runtime to:  
    `os.path.join(os.path.dirname(naas_abi_cli.__file__), "cli/new/templates/pipeline")`

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
- `extra_values` has a mutable default (`{}`); avoid mutating it outside the function. Prefer passing a new dict explicitly.
- If `pipeline_path` is `"."`, it resolves to the current working directory (`os.getcwd()`), and files will be copied there.
