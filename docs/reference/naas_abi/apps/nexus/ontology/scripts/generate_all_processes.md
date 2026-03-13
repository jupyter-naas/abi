# generate_all_processes

## What it is
A standalone script that generates a set of Turtle (`.ttl`) ontology files describing “processes” (BFO 7 Buckets compliant) from a hardcoded catalog (`ALL_PROCESSES`). Each process is written as a separate `.ttl` file under a category folder.

## Public API
- `ttl_string(s: str) -> str`
  - Escapes Python strings for safe inclusion in Turtle literals (backslashes, quotes, newlines).
- `write_process(folder, filename, label, definition, impl, who, where, when, how_know, how_is, why_roles, why_disps, steps, data_props=None, precedes=None, preceded_by=None) -> pathlib.Path`
  - Writes one process ontology file to `<OUTPUT_DIR>/<folder>/<filename>.ttl`.
  - Returns the written file path.
- `p(**kwargs) -> None`
  - Appends a process definition dict into the global `ALL_PROCESSES` list.
- `main() -> None`
  - Generates all `.ttl` files for the processes accumulated in `ALL_PROCESSES` and prints a summary.

## Configuration/Dependencies
- **Python standard library only**
  - `pathlib.Path`
- **Output location**
  - `OUTPUT_DIR = Path(__file__).parent.parent / "processes"`
- **Hardcoded Turtle prefixes**
  - Stored in `PREFIXES` string and prepended to every output file.
- **Input data**
  - All process definitions are hardcoded in `ALL_PROCESSES` via repeated calls to `p(...)`.

## Usage
Run the script directly to generate all process `.ttl` files:

```python
# from a shell
python libs/naas-abi/naas_abi/apps/nexus/ontology/scripts/generate_all_processes.py
```

Or invoke programmatically:

```python
from naas_abi.apps.nexus.ontology.scripts.generate_all_processes import main

main()
```

## Caveats
- `precedes` parameter exists in `write_process(...)` but is not used to emit any Turtle content.
- Only the **first** item in each of `who`, `where`, `when`, and `why_roles` is used to generate object-property relationships for the process; additional entries are still emitted as classes but not linked via generated relationships.
- Output uses a fixed `dc:created` date (`"2026-02-09"^^xsd:date`) for all generated ontologies.
