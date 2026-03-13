# TripleStoreService__SecondaryAdaptor__FileBase

## What it is
A small helper/base class for file-based triple store secondary adaptors. It provides:
- A deterministic SHA-256 hash of an IRI.
- Grouping of RDF triples by subject.

## Public API
- `class TripleStoreService__SecondaryAdaptor__FileBase`
  - `iri_hash(iri: rdflib.term.URIRef) -> str`
    - Returns the SHA-256 hex digest of the IRI string (UTF-8 encoded).
  - `triples_by_subject(triples: rdflib.Graph) -> Dict[rdflib.term.Node, List[Tuple[rdflib.term.Node, rdflib.term.Node]]]`
    - Iterates all triples in the graph and returns a mapping:
      - key: subject node
      - value: list of `(predicate, object)` pairs for that subject

## Configuration/Dependencies
- Python standard library: `hashlib`
- Third-party:
  - `rdflib` (`Graph`, `Node`, `URIRef`)
- Typing: `Dict`, `List`, `Tuple`

## Usage
```python
from rdflib import Graph, URIRef

from naas_abi_core.services.triple_store.adaptors.secondary.base.TripleStoreService__SecondaryAdaptor__FileBase import (
    TripleStoreService__SecondaryAdaptor__FileBase,
)

base = TripleStoreService__SecondaryAdaptor__FileBase()

g = Graph()
s = URIRef("https://example.org/s")
p = URIRef("https://example.org/p")
o = URIRef("https://example.org/o")
g.add((s, p, o))

print(base.iri_hash(s))  # sha256 hex digest
print(base.triples_by_subject(g))  # {s: [(p, o)]}
```

## Caveats
- `triples_by_subject()` groups only by subject and returns `(predicate, object)` pairs; it does not deduplicate or sort results.
- `iri_hash()` assumes `iri` is an `rdflib.URIRef` (or compatible type providing `.encode("utf-8")`).
