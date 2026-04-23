# OntologyYaml

## What it is
Utilities to translate an RDFLib `Graph` (ontology + individuals) into a YAML-ready Python `dict` containing:
- namespace `prefixes`
- a set of selected `classes` (BFO by default + classes referenced by ABI individuals)
- `entities` (individuals under the `/abi/` namespace) with relations and selected data properties

## Public API

### `class OntologyYaml`
- `__init__(triple_store_service: ITripleStoreService)`
  - Stores a triple store service (note: currently not used by the static conversion entrypoint).
- `@staticmethod rdf_to_yaml(graph, class_colors_mapping: dict = {}, top_level_class: str = "http://purl.obolibrary.org/obo/BFO_0000001", display_relations_names: bool = True, yaml_properties: list = []) -> dict`
  - Converts an RDF graph to a YAML-like dictionary using an internal `Translator`.

### `class Translator`
Intended internal implementation used by `OntologyYaml.rdf_to_yaml`.
- `translate(graph, class_colors_mapping, top_level_class, display_relations_names, yaml_properties) -> dict`
  - Orchestrates parsing and YAML structure creation.
- Other methods are internal helpers (not prefixed with `_` consistently, but effectively internal to the workflow):
  - `load_triples(g)`, `load_classes()`, `compute_class_levels(cls_id)`, `load_object_properties()`, `load_individuals()`, `map_oprop_labels()`, `create_yaml(...)`
  - `get_linked_classes(cls_id, rel_type=None)` for resolving OWL list constructs used in domain/range expressions (`unionOf`, `intersectionOf`, `complementOf`).

## Configuration/Dependencies
- **Python packages**
  - `rdflib` (`Graph`, `URIRef`, and vocab terms `RDF`, `RDFS`, `OWL`)
  - `pydash` (imported as `_`)
- **Project dependencies**
  - `naas_abi_core.logger`
  - `naas_abi_core.services.triple_store.TripleStorePorts.ITripleStoreService`

## Usage

```python
from rdflib import Graph
from naas_abi_core.utils.OntologyYaml import OntologyYaml

g = Graph()
# Populate `g` with ontology triples and individuals...

yaml_data = OntologyYaml.rdf_to_yaml(g)

print(yaml_data.keys())  # dict_keys(['prefixes', 'classes', 'entities'])
```

## Caveats
- `OntologyYaml.rdf_to_yaml()` instantiates `Translator()` with no arguments, but `Translator.__init__` references `self.__triple_store_service.get_schema_graph()` even though `__triple_store_service` is not defined in `Translator`. As written, calling `rdf_to_yaml()` will raise an exception unless `Translator` is modified or `__triple_store_service` is injected some other way.
- Only predicates present in an internal URI-to-name mapping are kept when loading triples; all other predicates are ignored.
- Only individuals whose URI contains `"/abi/"` are emitted as `entities`.
- Class inclusion in output:
  - all BFO classes (`"BFO_"` in URI) are included by default
  - additional classes are pulled in only if they are on the type chain of emitted ABI individuals (walking `is_a` via the first `subclassOf`).
- The function mutates the provided `class_colors_mapping` by adding random colors for newly encountered classes.
