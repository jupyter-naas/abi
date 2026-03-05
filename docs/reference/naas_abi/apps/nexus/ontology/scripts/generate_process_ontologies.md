# `generate_process_ontologies.py`

## What it is
A small script that generates **one Turtle (`.ttl`) ontology file per NEXUS process**. Each file includes:
- Standard RDF/OWL/BFO prefixes
- An `owl:Ontology` header importing `BFO7Buckets` and a shared common entities ontology
- An OWL class for the process (subclass of `bfo:BFO_0000015` “process”)
- An optional `skos:example`
- A placeholder template for “BFO 7 Buckets” content and a sample instance

## Public API
- `@dataclass ProcessDef`
  - Holds a process definition used to generate a `.ttl` file.
  - Fields:
    - `name: str` (e.g., `UserLoginProcess`)
    - `label: str`
    - `definition: str`
    - `implementation: str` (free-text pointer to code locations)
    - `folder: str` (subfolder under output directory)
    - `example: str = ""` (optional)
- `PROCESSES: list[ProcessDef]`
  - The set of processes to generate files for.
- `generate_process_file(proc: ProcessDef, output_dir: pathlib.Path)`
  - Writes a Turtle file for `proc` into `output_dir / proc.folder / <snake_case_name>.ttl`.
  - Creates directories as needed.
  - Prints a “Generated” line per file.
- `main()`
  - Computes the output directory as: `Path(__file__).parent.parent / "processes"`.
  - Generates all files for entries in `PROCESSES`.
  - Prints a summary and folder counts.

## Configuration/Dependencies
- Python standard library only:
  - `pathlib.Path`
  - `dataclasses.dataclass`
- Output location (fixed in `main()`):
  - `<script_dir>/../processes/`
- Turtle content includes ontology imports (strings in the generated files):
  - `<http://ontology.naas.ai/abi/BFO7Buckets>`
  - `<http://nexus.platform/ontology/_shared/common_entities>`

## Usage
Run as a script to generate all process ontology files:

```python
# run from shell:
# python libs/naas-abi/naas_abi/apps/nexus/ontology/scripts/generate_process_ontologies.py
```

Programmatic use (e.g., generate a single process file):

```python
from pathlib import Path
from naas_abi.apps.nexus.ontology.scripts.generate_process_ontologies import (
    ProcessDef, generate_process_file
)

out = Path("processes_out")
proc = ProcessDef(
    name="ExampleProcess",
    label="Example Process",
    definition="An example definition.",
    implementation="some/module.py lines 1-10",
    folder="examples",
    example="Step A → Step B → Step C",
)
generate_process_file(proc, out)
```

## Caveats
- The generated Turtle includes fixed timestamps (`dc:created` dates are hardcoded to `2026-02-09` and `2026-02-09T15:00:00Z`).
- The “BFO 7 Buckets” sections beyond the process class are placeholders with TODO comments; no real bucket entities are generated.
- Filename is derived by a simple CamelCase-to-snake_case conversion; acronyms may produce unexpected underscores (e.g., `JWTToken` → `j_w_t_token`).
