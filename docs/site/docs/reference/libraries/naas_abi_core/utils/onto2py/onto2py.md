# onto2py

## What it is

A Turtle (`.ttl`) ontology-to-Python generator that:
- Parses RDF/OWL/SHACL with **rdflib**
- Extracts classes, inheritance, properties, and some constraints
- Generates **Pydantic** models that can:
  - Serialize to RDF triples (`rdf()`)
  - Load from a SPARQL result stream (`from_iri()` via an injected query executor)
- Optionally writes the generated module next to the input `.ttl` and creates per-class “action” stubs under `ontologies/classes/`.

## Public API

### Dataclasses
- `PropertyInfo`
  - Holds extracted property metadata:
    - `name`, `property_type` (`"data"`/`"object"`)
    - `range_classes: Dict[str, Optional[int]]` (object-property target classes with optional cardinality)
    - `datatype` (mapped Python type string for data properties)
    - `required` (from SHACL `minCount`)
    - `description` (from `skos:definition`)
    - `default_value` (used for injected metadata fields)
- `ClassInfo`
  - Holds extracted class metadata:
    - `name`, `uri`, `label`, `description`
    - `parent_classes`
    - `properties: List[PropertyInfo]`
    - `property_uris: Dict[str, str]` (property name → URI)

### Main function
- `onto2py(ttl_file: str | io.TextIOBase, overwrite: bool = False) -> str`
  - Converts a TTL ontology to generated Python code (string).
  - If `ttl_file` is a path:
    - Writes a sibling `.py` file
    - Runs `ruff` (if available)
    - Generates per-class stub files via `create_class_files(...)`
  - If `ttl_file` is a file-like object:
    - Only returns the generated code (no filesystem writes).

### Name extraction helpers
- `extract_class_name_from_label(label: str) -> Optional[str]`
  - Converts an `rdfs:label` to a PascalCase Python identifier.
- `extract_class_name(uri, g: Optional[rdflib.Graph] = None) -> Optional[str]`
  - Prefers `rdfs:label`; otherwise derives from URI fragment/path.
- `extract_property_name_from_label(label: str) -> Optional[str]`
  - Converts an `rdfs:label` to a snake_case Python identifier.
- `extract_property_name(uri, g: Optional[rdflib.Graph] = None) -> Optional[str]`
  - Prefers `rdfs:label`; otherwise derives from URI fragment/path.

### OWL restriction / class-expression helpers
- `extract_classes_from_union(g, union_node, classes) -> List[str]`
- `extract_classes_from_intersection(g, intersection_node, classes, OWL) -> List[str]`
- `extract_cardinality_from_restriction(g, restriction, OWL) -> Optional[int]`
- `extract_classes_with_cardinality_from_intersection(g, intersection_node, classes, OWL) -> Dict[str, Optional[int]]`
- `extract_restriction_properties(g, restriction, class_uri, class_info, classes, OWL) -> None`
  - Adds object properties inferred from `rdfs:subClassOf` OWL `Restriction` nodes using:
    - `owl:onProperty` + `owl:allValuesFrom` / `owl:someValuesFrom` / `owl:onClass`
    - Handles `owl:unionOf` and `owl:intersectionOf`
    - Extracts limited cardinality info from `owl:cardinality` / `minCardinality` / `maxCardinality`

### RDF/SHACL extraction helpers
- `get_label(g, resource) -> Optional[str]` (from `rdfs:label`)
- `get_description(g, resource) -> Optional[str]` (from `rdfs:comment`, fallback `rdfs:label`)
- `get_property_description(g, prop) -> Optional[str]` (from `skos:definition`)
- `get_property_range(g, prop, classes) -> Dict[str, Optional[int]]` (from `rdfs:range`)
- `get_datatype_range(g, prop) -> str`
  - Maps common XSD datatypes to Python type strings (else `"Any"`).
- `extract_shacl_constraints(g, classes, properties, SHACL) -> None`
- `process_property_shape(g, prop_shape, class_info, properties, SHACL) -> None`
  - Applies:
    - `sh:minCount` → `required = True` when `> 0`
    - `sh:maxCount` → sets cardinality for all `range_classes` (1 vs >1)

### Property inheritance / metadata injection
- `inherit_parent_properties(classes: Dict[str, ClassInfo]) -> None`
  - Copies parent properties into children (preserves `required` flag as stored).
- `add_metadata_properties(g, classes: Dict[str, ClassInfo]) -> None`
  - Adds to **all** classes if missing:
    - `rdfs:label` (required, `str`)
    - `dcterms:created` (required, `datetime.datetime`, default `datetime.datetime.now()`)
    - `dcterms:creator` (required; stored as a `"data"` property with `default_value='os.environ.get("USER")'`)

### Code generation
- `generate_python_code(classes, properties) -> str`
  - Emits a module containing:
    - Imports (conditionally includes `datetime`, `os`, `List`, `Union`, etc.)
    - `RDFEntity` base model (Pydantic) with `from_iri()` and `rdf()`
    - One Pydantic model per ontology class
    - `model_rebuild()` calls to resolve forward refs
- `topological_sort_classes(classes) -> List[ClassInfo]`
  - Sorts to emit parents before children (best-effort; tolerates cycles).
- `generate_class_code(class_info, has_any_import=False) -> List[str]`
- `generate_property_code(prop, has_any_import=False) -> List[str]`

### File generation (side effects)
- `create_class_files(ttl_file_path, classes, py_file, overwrite=False) -> None`
  - Creates per-class stub files under: `<module_base>/ontologies/classes/<uri-path>/ClassName.py`
  - Stub imports the generated class from the main generated module and subclasses it.

### Ruff integration utilities
- `apply_linting(code: str) -> str` (formats via temporary file if `ruff` available)
- `_run_ruff(paths: list[str]) -> None`
- `_find_ruff() -> Optional[str]`

## Configuration/Dependencies

- Runtime Python deps:
  - `rdflib`
  - `pydantic`
- Optional tooling:
  - `ruff` (auto-detected as `ruff`, `<venv>/ruff`, or `uvx ruff`) used for:
    - `ruff check --fix --extend-select I`
    - `ruff format`
- Ontology expectations:
  - Uses RDF/OWL terms (`owl:Class`, `rdfs:Class`, `owl:ObjectProperty`, `owl:DatatypeProperty`)
  - Uses SHACL (`sh:NodeShape`, `sh:targetClass`, `sh:property`, `sh:path`, `sh:minCount`, `sh:maxCount`)
  - Uses `skos:definition` for property descriptions

## Usage

### Generate code as a string (no file writes)
```python
from naas_abi_core.utils.onto2py.onto2py import onto2py

with open("example.ttl", "r") as f:
    code = onto2py(f)

print(code[:300])
```

### Generate code and write `example.py` next to `example.ttl`
```python
from naas_abi_core.utils.onto2py.onto2py import onto2py

onto2py("example.ttl")  # writes example.py, runs ruff if available, creates class stub files
```

## Caveats

- `onto2py()` writes output files **only** when `ttl_file` is a string path; file-like input returns code only.
- SHACL constraints applied are limited to:
  - `minCount` (sets `required=True`)
  - `maxCount` (sets a simple cardinality affecting list vs scalar typing)
- OWL restriction parsing focuses on `rdfs:subClassOf` `owl:Restriction` with `onProperty` and common fillers; it does not implement full OWL semantics.
- `create_class_files()` derives package/module import paths from filesystem layout (looks for a folder starting with `naas_abi` and special-cases hyphenated path segments).
