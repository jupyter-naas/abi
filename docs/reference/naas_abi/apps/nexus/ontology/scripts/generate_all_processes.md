# generate_all_processes.py

## What it is
A script that generates a set of Turtle (`.ttl`) ontology files describing NEXUS “processes” in a **BFO 7 Buckets**-style structure. Each generated file is based on a static in-code catalog (`ALL_PROCESSES`) and written into a `processes/` directory grouped by folder.

## Public API
- `ttl_string(s: str) -> str`
  - Escapes a Python string for use as a Turtle literal (escapes backslashes, quotes, newlines).
- `write_process(folder, filename, label, definition, impl, who, where, when, how_know, how_is, why_roles, why_disps, steps, data_props=None, precedes=None, preceded_by=None) -> pathlib.Path`
  - Writes one `.ttl` file describing a process ontology:
    - Adds common RDF/BFO/NEXUS prefixes.
    - Creates an `owl:Ontology` header with `dc:title`, `dc:description`, `dc:created`, and `owl:imports`.
    - Creates an `owl:Class` for the process as a subclass of `bfo:BFO_0000015` with label/definition/comment/example steps.
    - Optionally emits bucket classes for: WHO/WHERE/WHEN/HOW WE KNOW/HOW IT IS/WHY roles/WHY dispositions.
    - Optionally emits a small set of object properties linking the process class to the **first** item in each bucket (if present), plus `preceded_by` if provided.
    - Optionally emits datatype properties from `data_props`.
- `main() -> None`
  - Iterates over `ALL_PROCESSES`, calls `write_process(**proc)` for each, prints a per-file log and a folder summary.

## Configuration/Dependencies
- **Filesystem output location**
  - `OUTPUT_DIR = Path(__file__).parent.parent / "processes"`
  - Files are written to: `OUTPUT_DIR / folder / f"{filename}.ttl"`.
- **Runtime dependencies**
  - Python standard library only (`pathlib.Path`).
- **Input data**
  - `ALL_PROCESSES`: populated at import time via helper `p(**kwargs)` calls in this file.

## Usage
Run as a script:

```python
# from a shell
python libs/naas-abi/naas_abi/apps/nexus/ontology/scripts/generate_all_processes.py
```

Or call programmatically:

```python
from naas_abi.apps.nexus.ontology.scripts.generate_all_processes import main

main()
```

## Caveats
- Relationship generation is minimal:
  - For each bucket (who/where/when/why_roles), only the **first** key in the dict is used to create an object property.
  - `precedes` is accepted by `write_process(...)` but is not used when emitting relationships.
- Identifiers:
  - The process class name is derived from `label` by removing spaces (`cls = label.replace(" ", "")`), not from `filename`.
- Output overwrites:
  - Re-running will overwrite existing `.ttl` files with the same `folder/filename`.
