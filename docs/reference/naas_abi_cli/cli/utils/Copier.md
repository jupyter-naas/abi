# Copier

## What it is
A small utility for copying a directory tree of template files into a destination directory, rendering both **file contents** and **path names** using **Jinja2** variables. Missing template variables are interactively requested from the user via `rich.prompt.Prompt`.

## Public API

- `class ValueProvider(dict)`
  - `collect_values(template_string: str) -> None`
    - Parses a Jinja2 template string to find undeclared variables and prompts the user for any values not already present in the dict.

- `class Copier`
  - `__init__(templates_path: str, destination_path: str)`
    - Initializes a copier with absolute base paths for templates and destination.
  - `copy(values: dict, templates_path: str | None = None)`
    - Recursively copies files/directories from `templates_path` (defaults to the base templates path) to the destination, rendering:
      - directory names
      - file names
      - file contents
    - Prompts for any missing Jinja2 variables encountered during rendering.

## Configuration/Dependencies

- **Filesystem**
  - Reads from `templates_path` directory.
  - Writes to `destination_path` (creates subdirectories as needed).

- **Dependencies**
  - `jinja2` (template parsing and rendering)
  - `rich` (interactive prompting via `Prompt.ask`)

## Usage

```python
from naas_abi_cli.cli.utils.Copier import Copier

copier = Copier(templates_path="path/to/templates", destination_path="path/to/output")

# Provide initial values; any missing variables in templates will be prompted.
copier.copy(values={"project_name": "demo"})
```

Template variables can appear in:
- file contents: `Hello {{ project_name }}`
- file names or folder names: `{{ project_name }}.txt`, `{{ project_name }}/...`

## Caveats

- **Interactive prompts**: If templates reference variables not in `values`, the process will block and prompt the user.
- **Destination directories for files**: The code creates directories when it encounters a template directory, but it does not explicitly create the parent directory for a file right before writing it. Ensure directory templates exist (or are created earlier) for nested files.
- **Overwrite behavior**: Files are opened with `"w"` and will be overwritten if they already exist.
- **Special-case YAML copy is disabled**: There is a dead branch (`if False and ...`) that never runs; YAML files are treated like any other templated file.
