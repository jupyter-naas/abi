# BFO7BucketsProcessOntology

## What it is
- A small set of Pydantic models representing BFO (Basic Formal Ontology) “process” bucket entities.
- Each entity can serialize itself (and linked entities) into an `rdflib.Graph` via an `rdf()` method.
- Includes minimal URI/namespace management and basic cycle detection during RDF generation.

## Public API

### Classes

- `RDFEntity(BaseModel)`
  - Base class for RDF-backed entities.
  - Responsibilities:
    - Generate a unique `_uri` for each instance (unless provided).
    - Manage a class-level namespace for URI generation.
    - Serialize instances to RDF (`rdflib.Graph`) using declared `_class_uri`, `_property_uris`, and `_object_properties`.

#### `RDFEntity` methods
- `set_namespace(namespace: str) -> None` (class method)
  - Sets the class-level namespace used when auto-generating `_uri`.
- `rdf(subject_uri: str | None = None, visited: set[str] | None = None) -> rdflib.Graph`
  - Builds RDF triples for the instance.
  - Recursively includes RDF for linked `RDFEntity` objects.
  - Uses `visited` to avoid infinite recursion on cycles.

---

- `Process(RDFEntity)`
  - BFO Process (`BFO_0000015`).
  - Fields:
    - Data: `label: str`, `created: datetime`, `creator: Any`
    - Object properties (lists): `concretizes`, `has_participant`, `occupies_temporal_region`, `occurs_in`, `realizes`

- `TemporalRegion(RDFEntity)`
  - BFO Temporal Region (`BFO_0000008`).
  - Fields: `label`, `created`, `creator`

- `MaterialEntity(RDFEntity)`
  - BFO Material Entity (`BFO_0000040`).
  - Fields:
    - Data: `label`, `created`, `creator`
    - Object properties (lists): `bearer_of`, `has_member_part`, `is_carrier_of`, `located_in`, `material_basis_of`, `participates_in`

- `Site(RDFEntity)`
  - BFO Site (`BFO_0000029`).
  - Fields: `label`, `created`, `creator`

- `GenericallyDependentContinuant(RDFEntity)`
  - BFO GDC (`BFO_0000031`).
  - Fields:
    - Data: `label`, `created`, `creator`
    - Object properties (lists): `generically_depends_on`, `is_concretized_by`

- `Quality(RDFEntity)`
  - BFO Quality (`BFO_0000019`).
  - Fields:
    - Data: `label`, `created`, `creator`
    - Object properties (lists): `concretizes`, `inheres_in`, `participates_in`

- `Role(RDFEntity)`
  - BFO Role (`BFO_0000023`).
  - Fields:
    - Data: `label`, `created`, `creator`
    - Object properties (lists): `concretizes`, `has_realization`, `inheres_in`

- `Disposition(RDFEntity)`
  - BFO Disposition (`BFO_0000016`).
  - Fields:
    - Data: `label`, `created`, `creator`
    - Object properties (lists): `concretizes`, `has_material_basis`, `has_realization`

## Configuration/Dependencies
- Dependencies:
  - `pydantic` (models, validation)
  - `rdflib` (RDF graph construction)
- Environment:
  - Default `creator` is taken from `os.environ.get("USER")`.
- Namespace handling:
  - Default auto-generated instance URIs use `RDFEntity._namespace` (default: `http://ontology.naas.ai/abi/`).
  - You can override via `RDFEntity.set_namespace(...)`.
- RDF namespaces bound in `rdf()`:
  - `cco`, `bfo`, `abi`, `rdfs`, `rdf`, `owl`, `xsd`

## Usage

```python
from rdflib import URIRef
from naas_abi_marketplace.domains.ontology_engineer.ontologies.BFO7BucketsProcessOntology import (
    RDFEntity, Process, MaterialEntity
)

# Optional: set a custom namespace for generated instance URIs
RDFEntity.set_namespace("http://example.org/my-ontology/")

agent = MaterialEntity(label="Operator")
p = Process(
    label="Data ingestion",
    has_participant=[agent, URIRef("http://example.org/external/participant")]
)

g = p.rdf()
print(g.serialize(format="turtle"))
```

## Caveats
- Many object-property fields default to `["http://ontology.naas.ai/abi/unknown"]` (a string treated as an object URI for object properties); override these defaults if you don’t want “unknown” links in output.
- Cycle detection:
  - `rdf()` uses a `visited` set keyed by subject URI to prevent infinite recursion; already-visited linked entities won’t be re-serialized, but relationship triples are still emitted.
- Strict Pydantic models:
  - `extra="forbid"`: passing undeclared fields raises validation errors.
