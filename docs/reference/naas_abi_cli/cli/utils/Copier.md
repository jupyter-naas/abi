# Copier

## What it is
- A small utility to recursively copy a directory of template files into a destination directory.
- Uses Jinja2 rendering on:
  - File contents
  - Destination file paths and directory names
- Prompts interactively (via `rich`) for any missing Jinja2 variables encountered during rendering.

## Public API

### `class ValueProvider(dict)`
- Purpose: Collects Jinja2 undeclared variables from a template string and prompts the user for values not already present in the dict.

Methods:
- `collect_values(template_string: str) -> None`
  - Parses `template_string` with a Jinja2 environment, finds undeclared variables, and for each missing key:
    - prompts: `Enter value for '<name>'`
    - stores the result in the dict.

### `class Copier`
- Purpose: Copies and renders a template directory tree into a destination directory.

Constructor:
- `__init__(templates_path: str, destination_path: str)`
  - Stores absolute paths for both inputs to avoid path issues during recursion.

Methods:
- `copy(values: dict, templates_path: str | None = None)`
  - Recursively walks `templates_path` (defaults to the base `templates_path` passed to the constructor).
  - For each file:
    - renders the destination path (may contain Jinja2 variables)
    - renders the file content as a Jinja2 template
    - writes the result to the rendered destination path
  - For each directory:
    - renders the directory name/path (may contain Jinja2 variables)
    - creates the directory (with `exist_ok=True`)
    - recurses into it
  - Prompts for missing template variables as they are encountered.

## Configuration/Dependencies
- Standard library: `os`, `shutil` (note: `shutil.copy` branch is present but disabled).
- Third-party:
  - `jinja2` (templating)
  - `rich` (`rich.prompt.Prompt` for interactive input)

## Usage

```python
from naas_abi_cli.cli.utils.Copier import Copier

copier = Copier(templates_path="path/to/templates", destination_path="path/to/output")

# Provide any known values up front; missing variables will be prompted.
copier.copy(values={"project_name": "my_app"})
```

## Caveats
- Interactive prompting: Any undeclared Jinja2 variables not provided in `values` will trigger terminal prompts.
- Destination directories are only created when processing subdirectories; if the template root contains files and the destination root does not exist, writing those files may fail (no explicit `os.makedirs` for the root target path).
- Jinja2 rendering is applied to destination paths and directory names; rendering to an invalid filesystem path can cause write/create failures.
- A special-case YAML copy branch exists but is effectively disabled (`if False and ...`).
