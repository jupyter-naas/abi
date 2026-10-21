# `generate_process_ontologies.py`

## What it is
A small script that generates one Turtle (`.ttl`) ontology file per predefined NEXUS process definition. Each file includes a BFO “7 Buckets” template structure and a stub example instance.

## Public API
- `@dataclass ProcessDef`
  - Purpose: Holds the metadata used to generate a process ontology file.
  - Fields:
    - `name: str` — class name for the process (e.g., `UserLoginProcess`)
    - `label: str` — human label
    - `definition: str` — textual definition
    - `implementation: str` — pointer to implementation location in codebase
    - `folder: str` — subfolder under the output directory
    - `example: str = ""` — optional example text embedded as `skos:example`

- `PROCESSES: list[ProcessDef]`
  - Purpose: The set of processes that will be generated.

- `generate_process_file(proc: ProcessDef, output_dir: pathlib.Path) -> None`
  - Purpose: Writes a Turtle file for `proc` into `output_dir / proc.folder / <snake_name>.ttl`.
  - Behavior:
    - Converts `proc.name` from CamelCase to `snake_case` for filenames and ontology identifiers.
    - Ensures the target folder exists (`mkdir(parents=True, exist_ok=True)`).
    - Writes a fixed Turtle template including prefixes, ontology header, a class declaration for `nexus:{proc.name}`, optional `skos:example`, and a stub example instance.
    - Prints a “Generated” line with the relative path.

- `main() -> None`
  - Purpose: Script entry point; generates files for all `PROCESSES`.
  - Output directory:
    - `Path(__file__).parent.parent / "processes"`

## Configuration/Dependencies
- Python standard library only:
  - `pathlib.Path`
  - `dataclasses.dataclass`
- No environment variables or external configuration are used.
- Output directory is derived from the script location (see `main()`).

## Usage
Run as a script to generate all process ontology files:

```python
# from a shell, run the module file directly
# python libs/naas-abi/naas_abi/apps/nexus/ontology/scripts/generate_process_ontologies.py
```

Programmatic usage (generate a single file):

```python
from pathlib import Path
from naas_abi.apps.nexus.ontology.scripts.generate_process_ontologies import (
    ProcessDef, generate_process_file
)

out = Path("processes_out")
proc = ProcessDef(
    name="MyProcess",
    label="My Process",
    definition="A test process.",
    implementation="some/module.py:1-10",
    folder="test",
    example="Input → Transform → Output",
)
generate_process_file(proc, out)
```

## Caveats
- Generated ontology timestamps are hard-coded (`dc:created "2026-02-09"` and example instance time).
- The Turtle content is a template; “WHO/WHERE/WHEN/…” sections are placeholders with TODO comments.
- File naming uses a simple CamelCase→snake_case conversion; unusual names (acronyms, digits) may produce unexpected underscores.
- `filepath.write_text(content)` uses platform defaults (no explicit encoding specified).
