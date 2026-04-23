# Triple Store Service

`TripleStoreService` is the RDF and SPARQL core for ontologies and semantic data.

## Core capabilities

- Insert/remove RDF graphs.
- Query with SPARQL (`SELECT`, `CONSTRUCT`, etc.).
- Subject-level graph retrieval.
- Named graph operations (adapter-dependent).
- Schema loading with update detection (`load_schema`, `load_schemas`).
- Event publication to bus on insert/delete (when services are wired).

## Adapter options

- `fs`: filesystem-backed local triple partitioning by subject hash.
- `object_storage`: object-storage-backed partitioning.
- `oxigraph`: HTTP adapter with named graph support.
- `apache_jena_tdb2`: Fuseki/TDB2 HTTP adapter with named graph support.
- `aws_neptune`: direct AWS Neptune adapter.
- `aws_neptune_sshtunnel`: Neptune via SSH tunnel.
- `custom`: pluggable custom adapter.

## Important compatibility notes

- Filesystem and object-storage adapters do **not** support named graphs (`create_graph`, `drop_graph`, etc.).
- Oxigraph/Jena/Neptune adapters support named graph management.
- Triple insert/remove emits bus events using hashed routing keys.

## Minimal usage

```python
from rdflib import Graph

triples = Graph()
# ... add triples

engine.services.triple_store.insert(triples)
result = engine.services.triple_store.query("SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 10")
```

## Schema management behavior

`load_schema(path)` tracks metadata in an internal ontology:

- file path
- file hash
- file modified time
- base64 content

When a schema changes, it computes delta triples and applies insert/remove updates.
