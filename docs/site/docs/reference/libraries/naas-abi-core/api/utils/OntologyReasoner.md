# OntologyReasoner

## What it is
- Utility class for de-duplicating RDF resources in a Turtle (`ttl`) string.
- Merges subjects that share the same `rdf:type` and `rdfs:label`, preferring a UUID-based IRI as the canonical subject.

## Public API

### Class: `OntologyReasoner`
#### `is_iri_uuid(iri: rdflib.term.URIRef) -> bool`
- Checks whether the last path/fragment segment of an IRI matches a UUID pattern (`8-4-4-4-12` lowercase hex).

#### `dedup_subject(class_label: tuple, graph: rdflib.Graph) -> rdflib.Graph`
- De-duplicates subjects in `graph` for a given `(class_iri, label)` pair.
- Behavior:
  - Runs a SPARQL query to find subjects `?s` with:
    - `?s a <class_iri>`
    - `?s rdfs:label "label"`
    - Excludes nodes that are superclasses of something (`FILTER NOT EXISTS { ?other rdfs:subClassOf ?s }`)
    - Excludes nodes typed as `owl:Class` or `rdfs:Class`
  - Picks the first matching subject whose IRI ends with a UUID; otherwise creates a new subject IRI:  
    `http://ontology.naas.ai/abi/{uuid4}`
  - For each non-canonical duplicate subject found:
    - Copies its non-`rdf:type` outgoing triples to the canonical subject.
    - Rewrites triples that reference the duplicate as an object to instead reference the canonical subject.
  - Rebuilds and returns a new graph excluding triples that mention removed duplicate IRIs.

#### `dedup_ttl(ttl: str) -> tuple[str, rdflib.Graph]`
- Parses a Turtle string into an `rdflib.Graph`, identifies duplicates by `(rdf:type, rdfs:label)`, and applies `dedup_subject` when multiple subjects share the same pair.
- Returns:
  - Serialized Turtle string (with original namespace bindings re-bound)
  - The resulting `rdflib.Graph`

## Configuration/Dependencies
- Python dependencies:
  - `rdflib`
- Standard library:
  - `re`, `uuid`, `typing`

## Usage

```python
from naas_abi_core.utils.OntologyReasoner import OntologyReasoner

ttl = """
@prefix ex: <http://example.com/> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

ex:a a ex:Person ; rdfs:label "Alice" ; ex:age 30 .
ex:b a ex:Person ; rdfs:label "Alice" ; ex:age 31 .
"""

reasoner = OntologyReasoner()
deduped_ttl, deduped_graph = reasoner.dedup_ttl(ttl)

print(deduped_ttl)
```

## Caveats
- `dedup_ttl` asserts that all triple components `(s, p, o)` are `URIRef`; Turtle containing literals (e.g., `rdfs:label "Alice"`) will violate this assertion for the literal object and raise `AssertionError`.
- The SPARQL query in `dedup_subject` references `owl:Class` but does not declare the `owl:` prefix in the query text; this may fail depending on the graph/query environment.
- UUID detection only matches lowercase hex UUIDs (uppercase UUID IRIs will not be treated as UUID-based).
