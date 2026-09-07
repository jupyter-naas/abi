# ActOfConnection (ActOfConnectionsOnLinkedIn ontology module)

## What it is
- A set of **Pydantic models** representing LinkedIn-related ontology entities (e.g., Act of Connection, Person, Organization).
- Each model can serialize itself (and linked entities) into an **RDFLib `Graph`** via `RDFEntity.rdf()`.
- Instance URIs are auto-generated under a configurable namespace unless `_uri` is provided.

## Public API

### Base model
- `class RDFEntity(pydantic.BaseModel)`
  - Purpose: shared base for all ontology entities with URI generation and RDF serialization.
  - `set_namespace(namespace: str) -> None`: sets the class-level namespace used for auto-generated instance URIs.
  - `rdf(subject_uri: str | None = None, visited: set[str] | None = None) -> rdflib.Graph`: emits RDF triples for the instance; recursively serializes related `RDFEntity` objects while preventing cycles.

### Ontology entity models (all subclass `RDFEntity`)
Each of the following provides:
- a `_class_uri` RDF type,
- `_property_uris` mapping from field name to predicate URI,
- `_object_properties` set indicating which fields should be emitted as object properties when given `str`/`URIRef`,
- Pydantic fields for data/object properties (see source for full field list and descriptions).

Public classes:
- `ActOfConnection`
- `ISO8601UTCDateTime`
- `Person`
- `Organization`
- `Location`
- `ProfilePage`
- `ConnectionsExportFile`
- `CurrentJobPosition`
- `CurrentOrganization`
- `CurrentPublicURL`
- `EmailAddress`
- `ConnectionRole`

## Configuration/Dependencies
- Dependencies:
  - `pydantic` (model validation)
  - `rdflib` (graph and RDF terms)
- Environment:
  - `creator` defaults to `os.environ.get("USER")` in all models where present.
- URI/namespace behavior:
  - Default namespace: `http://ontology.naas.ai/abi/`
  - Override with `RDFEntity.set_namespace("...")`
  - Provide `_uri="..."` at construction to force a specific subject URI.
- RDF namespaces bound in `rdf()`:
  - `cco`, `bfo`, `abi`, `rdfs`, `rdf`, `owl`, `xsd`

## Usage

```python
from naas_abi_marketplace.applications.linkedin.ontologies.modules.ActOfConnectionsOnLinkedIn import (
    RDFEntity, ActOfConnection, Person, ISO8601UTCDateTime
)

# Optional: change namespace used for auto-generated instance URIs
RDFEntity.set_namespace("http://example.org/abi/")

alice = Person(label="Alice Doe", first_name="Alice", last_name="Doe")
when = ISO8601UTCDateTime(label="2026-01-01T00:00:00Z")

act = ActOfConnection(
    label="Alice connected with someone",
    involves_agent=[alice],
    connected_at=when,
)

g = act.rdf()
print(g.serialize(format="turtle"))
```

## Caveats
- Many object-property fields default to the placeholder IRI string: `http://ontology.naas.ai/abi/unknown`.
- `created` defaults use `datetime.datetime.now()` as a direct default value; it is evaluated at import time, not at instance creation time.
- In `rdf()`, fields listed in `_object_properties` are treated as object properties **only** when values are `str`/`URIRef` (or lists of them); otherwise values are serialized as RDF literals.
