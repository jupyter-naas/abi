# onto2py

## What it is
A utility module that parses an RDF Turtle (`.ttl`) ontology (OWL/RDFS + optional SHACL) and generates Pydantic-based Python models that can emit RDF graphs. It can also write the generated module to disk and optionally scaffold per-class “action” stubs.

## Public API

### Data structures
- `@dataclass PropertyInfo`
  - Holds extracted property metadata:
    - `name`, `property_type` (`"data"` or `"object"`)
    - `range_classes: Dict[str, Optional[int]]` (object property targets + cardinality; `None` = unspecified, `>1` = list)
    - `datatype` (data property Python type string), `required`, `description`, `default_value`
- `@dataclass ClassInfo`
  - Holds extracted class metadata:
    - `name`, `uri`, `parent_classes`, `properties`
    - `description`, `label`
    - `property_uris: Dict[str, str]` (property name → predicate URI)

### Primary function
- `onto2py(ttl_file: str | io.TextIOBase, overwrite: bool = False) -> str`
  - Parses TTL content into an `rdflib.Graph`, extracts:
    - OWL/RDFS classes
    - inheritance (`rdfs:subClassOf`)
    - OWL restrictions (`owl:Restriction`) under `rdfs:subClassOf` (as object properties)
    - OWL object/datatype properties, domains/ranges
    - SHACL constraints (`sh:NodeShape`, `sh:property`, `sh:minCount`, `sh:maxCount`)
  - Adds standard metadata properties to *all* classes:
    - `rdfs:label` (required, `str`)
    - `dcterms:created` (required, `datetime.datetime`, default `datetime.datetime.now()`)
    - `dcterms:creator` (required, default `os.environ.get('USER')`; see caveats about its typing)
  - Generates a single Python code string and, when given a file path:
    - writes a sibling `.py` file next to the `.ttl`
    - creates per-class stub files under `.../ontologies/classes/...` (controlled by `overwrite`)

### Name extraction helpers
- `extract_class_name_from_label(label: str) -> Optional[str]`
  - Converts a label into a PascalCase Python identifier.
- `extract_class_name(uri, g: Optional[rdflib.Graph] = None) -> Optional[str]`
  - Prefer `rdfs:label` (if graph provided), else URI fragment/path; returns a Python identifier.
- `extract_property_name_from_label(label: str) -> Optional[str]`
  - Converts a label into a `snake_case` Python identifier.
- `extract_property_name(uri, g: Optional[rdflib.Graph] = None) -> Optional[str]`
  - Prefer `rdfs:label` (if graph provided), else URI fragment/path; returns a Python identifier.

### RDF/OWL parsing helpers (used internally but callable)
- `extract_classes_from_union(g, union_node, classes) -> List[str]`
  - Extracts class names from `owl:unionOf` lists.
- `extract_classes_from_intersection(g, intersection_node, classes, OWL) -> List[str]`
  - Extracts class names from `owl:intersectionOf` lists (supports nested restrictions).
- `extract_cardinality_from_restriction(g, restriction, OWL) -> Optional[int]`
  - Reads `owl:cardinality` / `owl:minCardinality` / `owl:maxCardinality`.
- `extract_classes_with_cardinality_from_intersection(g, intersection_node, classes, OWL) -> Dict[str, Optional[int]]`
  - Extracts class names plus cardinalities from `owl:intersectionOf` nested restrictions.
- `extract_restriction_properties(g, restriction, class_uri, class_info, classes, OWL)`
  - Converts `owl:Restriction` nodes under `rdfs:subClassOf` into `PropertyInfo` entries.

### Graph accessors
- `get_label(g, resource) -> Optional[str]` (reads `rdfs:label`)
- `get_description(g, resource) -> Optional[str]` (reads `rdfs:comment`, else `rdfs:label`)
- `get_property_description(g, prop) -> Optional[str]` (reads `skos:definition`)
- `get_property_range(g, prop, classes) -> Dict[str, Optional[int]]` (reads `rdfs:range` for object properties)
- `get_datatype_range(g, prop) -> Optional[str]` (maps `rdfs:range` XSD datatype → Python type string)

### SHACL support
- `extract_shacl_constraints(g, classes, properties, SHACL)`
  - Applies SHACL `minCount`/`maxCount` to properties for target classes.
- `process_property_shape(g, prop_shape, class_info, properties, SHACL)`
  - Implements the per-property constraint extraction.

### Code generation / file generation
- `inherit_parent_properties(classes)`
  - Copies parent properties into children (preserving `required` flag as stored on the parent properties).
- `add_metadata_properties(g, classes)`
  - Adds `label/created/creator` properties to all classes if missing.
- `create_class_files(ttl_file_path, classes, py_file, overwrite=False)`
  - Writes per-class Python files that subclass the generated model class.
- `apply_linting(code: str) -> str`
  - Attempts to run `ruff format` and `ruff check --fix` on generated code (falls back to original code on errors).
- `generate_python_code(classes, properties) -> str`
  - Creates a complete Python module including an `RDFEntity` base class and all ontology classes.
- `topological_sort_classes(classes) -> List[ClassInfo]`
  - Sorts classes to emit parent classes before children (best-effort; handles cycles).
- `generate_class_code(class_info, has_any_import=False) -> List[str]`
  - Emits one class definition (deduplicates properties by name).
- `generate_property_code(prop, has_any_import=False) -> str`
  - Emits one Pydantic field line using `typing.Annotated` and `Field(...)`.

## Configuration/Dependencies
- Runtime dependencies:
  - `rdflib` (parsing TTL, RDF terms, RDF lists via `rdflib.collection.Collection`)
  - `pydantic` (generated code uses `BaseModel`, `Field`)
- Optional external tool:
  - `ruff` (used by `apply_linting`; if missing/fails, code is returned unformatted)
- File system behavior:
  - If `ttl_file` is a path string, a sibling `.py` file is written.
  - Per-class stubs are written under a derived `ontologies/classes/...` directory layout.

## Usage

### Generate code from a TTL file path
```python
from naas_abi_core.utils.onto2py.onto2py import onto2py

code = onto2py("path/to/ontology.ttl")
print(code[:500])
```

### Generate code from an in-memory TTL string
```python
import io
from naas_abi_core.utils.onto2py.onto2py import onto2py

ttl = """
@prefix ex: <http://example.com/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

ex:Person a owl:Class ; rdfs:label "Person" .
"""
code = onto2py(io.StringIO(ttl))
print(code)
```

## Caveats
- Writing to disk happens automatically when `ttl_file` is a string path (it writes `Path(ttl_file).with_suffix(".py")` and prints status).
- `dcterms:creator` metadata property is added with `property_type="data"` but uses `range_classes={"str": 1}` (not `datatype="str"`), which influences how it is typed/emitted.
- Optional properties default to sentinel values in generated models:
  - object properties: `'http://ontology.naas.ai/abi/unknown'` (or a list containing it)
  - data properties: `'unknown'`
- SHACL `maxCount` is applied to all range classes of a property; `minCount > 0` marks the property as required.
- OWL restriction-derived properties are treated as object properties and explicitly marked `required=False` (restrictions do not automatically imply required in this generator).
