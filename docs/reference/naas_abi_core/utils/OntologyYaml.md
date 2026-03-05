# OntologyYaml

## What it is
- Utility for translating an RDFLib `Graph` containing ontology classes, object properties, and individuals into a YAML-friendly Python `dict` structure.
- Designed to extract classes (notably BFO), ABI individuals, and their relations, then normalize common URI prefixes.

## Public API
### `class OntologyYaml`
- `__init__(triple_store_service: ITripleStoreService)`
  - Stores a triple store service dependency (currently not used by the static translation method).
- `@staticmethod rdf_to_yaml(graph, class_colors_mapping: dict = {}, top_level_class: str = "http://purl.obolibrary.org/obo/BFO_0000001", display_relations_names: bool = True, yaml_properties: list = [])`
  - Translates an RDFLib `Graph` into a YAML-ready dictionary with keys:
    - `prefixes`
    - `classes`
    - `entities`

### `class Translator`
- `translate(graph, class_colors_mapping, top_level_class, display_relations_names, yaml_properties)`
  - Orchestrates translation by loading triples/classes/properties/individuals and producing YAML data via `create_yaml(...)`.
- Other methods exist but are internal helpers (no leading underscore consistency, but intended for internal use):
  - `load_triples(g)`
  - `load_classes()`
  - `compute_class_levels(cls_id)`
  - `load_object_properties()`
  - `load_individuals()`
  - `map_oprop_labels()`
  - `create_yaml(class_color, display_relations_names, yaml_properties)`
  - `get_linked_classes(cls_id, rel_type=None)` (used internally for domain/range expression trees)

## Configuration/Dependencies
- Requires:
  - `rdflib` (`Graph`, `URIRef`, `RDF`, `RDFS`, `OWL`)
  - `pydash` as `_`
  - `naas_abi_core.logger`
  - `naas_abi_core.services.triple_store.TripleStorePorts.ITripleStoreService`
- Prefix normalization performed in output:
  - `xsd`, `abi`, `bfo`, `cco`
- Notes on data expectations in the RDF graph:
  - Classes are detected via `rdf:type owl:Class`
  - Object properties via `rdf:type owl:ObjectProperty` (labels used to find relation predicates on individuals)
  - Individuals via `rdf:type owl:NamedIndividual`
  - Individuals are only emitted as YAML `entities` if their URI contains `"/abi/"`

## Usage
```python
from rdflib import Graph
from naas_abi_core.utils.OntologyYaml import OntologyYaml

g = Graph()
# Populate `g` with ontology + individuals data...

yaml_data = OntologyYaml.rdf_to_yaml(g)

print(yaml_data.keys())  # dict_keys(['prefixes', 'classes', 'entities'])
```

## Caveats
- `OntologyYaml.rdf_to_yaml(...)` instantiates `Translator()` with no arguments, but `Translator.__init__` references `self.__triple_store_service.get_schema_graph()` even though `__triple_store_service` is not defined in `Translator`. As written, calling `rdf_to_yaml` will raise an `AttributeError` unless `Translator` is fixed or externally patched to have `__triple_store_service`.
- Default argument `class_colors_mapping: dict = {}` is mutable.
- Only the first `subclassOf` entry is used when emitting a class `is_a` relation (`subclass[0]`).
- Relation extraction for individuals depends on object property labels (`rdfs:label`); it then looks for those label strings as keys in the individual’s predicate-mapped dict (i.e., the label must match the mapped predicate name in `self.mapping` output).
