# OntologyReasoner

## What it is
- A small utility for deduplicating RDF resources in a Turtle (TTL) ontology graph using **rdflib**.
- Deduplication is based on having the **same `rdf:type` and `rdfs:label`**, merging triples into a single “main” subject.

## Public API
### Class: `OntologyReasoner`
#### `is_iri_uuid(iri: URIRef) -> bool`
- Checks whether the last path/fragment segment of an IRI matches a UUID pattern (`8-4-4-4-12` lowercase hex).

#### `dedup_subject(class_label: tuple, graph: Graph) -> Graph`
- Deduplicates subjects in `graph` for a given `(class_iri, label)` pair.
- Behavior:
  - Finds subjects `?s` such that:
    - `?s a <class_iri>`
    - `?s rdfs:label "label"`
    - and **excludes** subjects that:
      - are a superclass of another resource (`FILTER NOT EXISTS { ?other rdfs:subClassOf ?s }`)
      - are explicitly typed as `owl:Class` or `rdfs:Class`
  - Picks the first matching subject whose IRI ends with a UUID as the main node; otherwise creates a new node:
    - `http://ontology.naas.ai/abi/<uuid4>`
  - Merges data:
    - Copies non-`rdf:type` triples from duplicate subjects onto the main node
    - Rewrites object references pointing to duplicate subjects to point to the main node
    - Removes excluded duplicate subjects from the output graph

#### `dedup_ttl(ttl: str) -> Tuple[str, Graph]`
- Parses a Turtle string into a graph, finds duplicate subjects with the same `(rdf:type, rdfs:label)`, and deduplicates them.
- Returns:
  - A serialized Turtle string of the deduplicated graph
  - The deduplicated `rdflib.Graph` object
- Preserves existing namespace bindings from the parsed graph.

## Configuration/Dependencies
- Python dependencies:
  - `rdflib`
- Standard library:
  - `re`, `uuid`, `typing`
- Input format:
  - `dedup_ttl` expects Turtle (`format="turtle"`).

## Usage
```python
from naas_abi_core.utils.OntologyReasoner import OntologyReasoner

ttl = """
@prefix ex: <http://example.org/> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

ex:a a ex:Thing ; rdfs:label "X" ; ex:p "v1" .
ex:b a ex:Thing ; rdfs:label "X" ; ex:p "v2" .
"""

reasoner = OntologyReasoner()
deduped_ttl, deduped_graph = reasoner.dedup_ttl(ttl)

print(deduped_ttl)
```

## Caveats
- `dedup_ttl` asserts that all triple components are `URIRef`; graphs containing literals (including `rdfs:label` values) may trigger an `AssertionError` during iteration.
- SPARQL in `dedup_subject` references `owl:Class` but does not declare the `owl:` prefix in the query; whether this works depends on the graph/query namespace handling in rdflib.
- UUID detection in `is_iri_uuid` matches **lowercase** hex only.
