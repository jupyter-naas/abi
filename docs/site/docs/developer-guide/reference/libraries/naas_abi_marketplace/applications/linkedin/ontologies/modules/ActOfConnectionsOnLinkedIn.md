# ActOfConnection (LinkedIn ontology module)

## What it is
- A small set of **Pydantic models** representing LinkedIn-related ontology entities (Act of Connection, Person, Organization, etc.).
- Each model can serialize itself (and linked entities) into an **RDFLib `Graph`** via a shared `RDFEntity.rdf()` method.
- URIs are auto-generated per instance unless explicitly provided.

## Public API

### Base
- `class RDFEntity(pydantic.BaseModel)`
  - `set_namespace(namespace: str) -> None`: sets the class-level namespace used for auto-generated URIs.
  - `rdf(subject_uri: str | None = None, visited: set[str] | None = None) -> rdflib.Graph`: emits RDF triples for the instance; recursively includes related entities while avoiding cycles.

### Ontology entity models (all subclass `RDFEntity`)
Each model has:
- an auto-managed instance URI (`_uri`), plus ontology metadata (`_class_uri`, `_property_uris`, `_object_properties`)
- Pydantic fields for data/object properties
- `rdf()` inherited from `RDFEntity`

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
  - `pydantic` (models, validation)
  - `rdflib` (RDF graph creation)
- Environment:
  - Default `creator` field uses `os.environ.get("USER")`.
- Namespace/URI behavior:
  - Default namespace for auto-generated URIs: `http://ontology.naas.ai/abi/`
  - Override via `RDFEntity.set_namespace(...)` (or per-subclass, since it’s a classmethod).

## Usage

```python
from rdflib import URIRef
from naas_abi_marketplace.applications.linkedin.ontologies.modules.ActOfConnectionsOnLinkedIn import (
    ActOfConnection, Person, ISO8601UTCDateTime, RDFEntity
)

# Optional: set a custom namespace for generated instance URIs
RDFEntity.set_namespace("http://example.org/abi/")

alice = Person(label="Alice Doe", first_name="Alice", last_name="Doe")
ts = ISO8601UTCDateTime(label="2026-01-01T00:00:00Z")

act = ActOfConnection(
    label="Alice connected with someone",
    involves_agent=[alice],
    connected_at=ts,
    # object properties can also be URI strings/URIRefs
    occurs_in=[URIRef("http://example.org/location/nyc")]
)

g = act.rdf()
print(g.serialize(format="turtle"))
```

## Caveats
- Many object-property fields default to the placeholder IRI string: `http://ontology.naas.ai/abi/unknown`.
- `created` defaults are evaluated at import time (`datetime.datetime.now()` used as a direct default), so instances created later may share the same default timestamp unless explicitly set.
- `rdf()` treats properties listed in `_object_properties` as object properties when values are `str`/`URIRef`; otherwise values are serialized as literals.
