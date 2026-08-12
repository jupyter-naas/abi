# graph.py

## What it is
Utilities for parsing Turtle (TTL) ontologies with `rdflib`, extracting:
- OWL classes (`owl:Class`)
- Object-property-style relationships expressed via `rdfs:subClassOf` + `owl:Restriction`
- Human-readable labels (`rdfs:label`), optionally sourced from imported ontologies

## Public API
- `URI_TO_GROUP: dict[str, str]`
  - Static mapping from specific BFO class URIs to high-level groups (e.g., `WHAT`, `WHO`).

- `get_imported_graph(graph: rdflib.Graph) -> rdflib.Graph`
  - Loads ontologies referenced via `owl:imports` into a separate graph (intended for label lookup only).
  - Tries multiple RDF formats (`xml`, `turtle`, `rdf`, `owl`) per import.

- `get_short_name(uri: rdflib.URIRef) -> str`
  - Returns the fragment after `#` or the last path segment after `/`.

- `get_rdfs_label(uri: rdflib.URIRef, graph: rdflib.Graph, imported_graph: Optional[rdflib.Graph] = None) -> str`
  - Resolves `rdfs:label` for `uri`, checking:
    1) `graph`
    2) `imported_graph` (if provided)
    3) a merged view (`graph + imported_graph`)
  - Falls back to `get_short_name(uri)` if no label is found.
  - If the label string contains `"@"`, keeps only the part before `"@"`.

- `extract_classes_from_union(graph: rdflib.Graph, union_node: rdflib.BNode) -> set[rdflib.URIRef]`
  - Extracts named classes (`URIRef`) from an `owl:unionOf` RDF list.
  - Handles nested unions and has a manual RDF-list traversal fallback.

- `extract_restriction_targets(graph: rdflib.Graph, restriction: rdflib.BNode) -> set[rdflib.URIRef]`
  - From an `owl:Restriction`, extracts named target classes from:
    - `owl:allValuesFrom`
    - `owl:someValuesFrom`
  - If the value is a union/list, extracts all member named classes.

- `extract_relationships(graph: rdflib.Graph, class_uri: rdflib.URIRef) -> list[tuple[rdflib.URIRef, rdflib.URIRef, rdflib.URIRef]]`
  - Reads `rdfs:subClassOf` blank nodes that are `owl:Restriction` and returns triples:
    - `(source_class, target_class, property_uri)`
  - Only considers targets found via `extract_restriction_targets`.

- `get_class_id_prefix(uri: rdflib.URIRef, graph: rdflib.Graph) -> str`
  - Attempts to match `uri` to a namespace prefix registered in `graph.namespaces()`.
  - Fallback heuristics:
    - returns `"bfo"` if URI contains `bfo`/`BFO`
    - returns `"abi"` if URI contains `abi`
    - else returns `"class"`

- `get_inverse_property(property_uri: rdflib.URIRef, graph: rdflib.Graph) -> Optional[rdflib.URIRef]`
  - Finds an inverse property via `owl:inverseOf` in either direction.

- `get_group_from_class_hierarchy(class_uri: rdflib.URIRef, graph: rdflib.Graph, visited: Optional[set[rdflib.URIRef]] = None) -> Optional[str]`
  - Walks up `rdfs:subClassOf` links (URI parents only) to find the first class whose URI appears in `URI_TO_GROUP`.
  - Uses `visited` to prevent cycles.

- `parse_turtle_ontology(turtle_path: str, imported_ontologies: Optional[list[str]] = None) -> tuple[rdflib.Graph, rdflib.Graph, set[rdflib.URIRef], set[tuple[rdflib.URIRef, rdflib.URIRef, rdflib.URIRef]]]`
  - Parses a TTL file into a main graph.
  - Loads `owl:imports` into a separate imported graph (and optionally additional imports passed in).
  - Collects:
    - explicitly declared classes (`rdf:type owl:Class`)
    - additional named classes referenced by restrictions in the main graph
  - Extracts restriction-based relationships and de-duplicates “inverse” pairs by treating `(source, target)` and `(target, source)` as duplicates (property URI is not considered in this inverse check).

## Configuration/Dependencies
- **Dependencies**
  - `rdflib` (`Graph`, `URIRef`, `BNode`, `RDF`, `RDFS`, `OWL`, `Collection`)
  - `naas_abi_core.logger` for logging
- **Network access**
  - `get_imported_graph()` may fetch `owl:imports` URLs over the network if present.

## Usage
```python
from naas_abi_marketplace.domains.ontology_engineer.utils.graph import (
    parse_turtle_ontology,
    get_rdfs_label,
)

main_g, imported_g, classes, rels = parse_turtle_ontology("ontology.ttl")

print(f"Classes: {len(classes)}")
print(f"Relationships: {len(rels)}")

# Print a few labeled relationships
for s, t, p in list(rels)[:5]:
    s_lbl = get_rdfs_label(s, main_g, imported_g)
    p_lbl = get_rdfs_label(p, main_g, imported_g)
    t_lbl = get_rdfs_label(t, main_g, imported_g)
    print(f"{s_lbl} --{p_lbl}--> {t_lbl}")
```

## Caveats
- `parse_turtle_ontology()` returns **4 items** `(graph, imported_graph, classes, unique_relationships)`; the docstring mentions additional items that are not returned.
- Relationship de-duplication treats `(source, target)` and `(target, source)` as inverses **without checking** `owl:inverseOf` and **without considering** the property URI; this can drop distinct predicates between the same two classes in opposite directions.
- Only restrictions expressed as `rdfs:subClassOf` **blank nodes** typed `owl:Restriction` are processed; direct `rdfs:subClassOf` URI parent links are not emitted as relationships.
- `get_rdfs_label()` strips anything after `"@"` in the label string; this is a simplistic language-tag handling.
