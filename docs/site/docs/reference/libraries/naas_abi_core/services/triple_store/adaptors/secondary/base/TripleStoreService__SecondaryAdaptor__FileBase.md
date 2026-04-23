# TripleStoreService__SecondaryAdaptor__FileBase

## What it is
A small utility base class for triple-store secondary adaptors that:
- Computes a stable SHA-256 hash for an RDF IRI.
- Groups RDF triples by subject for easier downstream processing.

## Public API
- `class TripleStoreService__SecondaryAdaptor__FileBase`
  - `iri_hash(iri: URIRef) -> str`
    - Returns the SHA-256 hex digest of the given IRI string.
  - `triples_by_subject(triples: Graph) -> Dict[Node, List[Tuple[Node, Node]]]`
    - Iterates over all triples in an `rdflib.Graph` and groups them into a mapping:
      - key: subject (`Node`)
      - value: list of `(predicate, object)` pairs (`List[Tuple[Node, Node]]`)

## Configuration/Dependencies
- Standard library: `hashlib`
- Third-party: `rdflib` (`Graph`, `Node`, `URIRef`)
- Typing: `Dict`, `List`, `Tuple`

## Usage
```python
from rdflib import Graph, URIRef
from naas_abi_core.services.triple_store.adaptors.secondary.base.TripleStoreService__SecondaryAdaptor__FileBase import (
    TripleStoreService__SecondaryAdaptor__FileBase,
)

g = Graph()
s = URIRef("https://example.org/s")
p = URIRef("https://example.org/p")
o = URIRef("https://example.org/o")
g.add((s, p, o))

base = TripleStoreService__SecondaryAdaptor__FileBase()

print(base.iri_hash(s))  # sha256 hex of the IRI string

grouped = base.triples_by_subject(g)
print(grouped[s])        # [(p, o)]
```

## Caveats
- `iri_hash` expects a value that supports `.encode("utf-8")` (typically an `rdflib.term.URIRef`); passing non-string-like nodes may raise an error.
- `triples_by_subject` processes all triples in the graph (`(None, None, None)` pattern), which may be expensive for very large graphs.
