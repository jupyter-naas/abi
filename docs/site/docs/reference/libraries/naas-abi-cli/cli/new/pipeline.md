# `pipeline` (new pipeline generator)

## What it is
Creates a new pipeline scaffold by copying a predefined template into a destination directory, using a PascalCase pipeline name.

## Public API
- `new_pipeline(pipeline_name: str, pipeline_path: str = ".", extra_values: dict = {})`
  - Normalizes `pipeline_name` to PascalCase.
  - Resolves `pipeline_path` (`"."` → current working directory).
  - Ensures the destination directory exists.
  - Copies the pipeline template from the package templates into the destination via `Copier`, passing template variables.
- CLI command: `new pipeline PIPELINE_NAME [PIPELINE_PATH]`
  - Implemented by `_new_pipeline(pipeline_name, pipeline_path)` (Click command handler) which calls `new_pipeline`.

## Configuration/Dependencies
- **Filesystem**
  - Creates `pipeline_path` if it does not exist (`os.makedirs(..., exist_ok=True)`).
- **Template source**
  - Templates are loaded from:
    - `<naas_abi_cli package dir>/cli/new/templates/pipeline`
- **Python dependencies**
  - `click` for CLI integration.
  - `naas_abi_cli.cli.utils.Copier.Copier` for template copying.
  - `.utils.to_pascal_case` for name normalization.

## Usage
### As a function
```python
from naas_abi_cli.cli.new.pipeline import new_pipeline

new_pipeline("my_pipeline", "./out")
```

### Via CLI
```bash
naas-abi-cli new pipeline my_pipeline ./out
```

## Caveats
- `extra_values` has a mutable default (`{}`); avoid mutating it inside callers.
- The template variable `pipeline_name_pascal` is always provided; any key in `extra_values` with the same name will be overwritten by the built-in value.
