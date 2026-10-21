# OrganizationAllianceProcess

## What it is
A small ontology/model layer (Pydantic + RDFLib) for representing organizational alliance “acts” and their related agreement documents as RDF individuals. It also provides a base `RDFEntity` utility to:
- Generate RDF graphs (`rdf()`) from model instances
- Load instances from an RDF store via SPARQL (`from_iri()`), using a user-supplied query executor

## Public API

### `class RDFEntity(pydantic.BaseModel)`
Base class for RDF-backed entities with automatic URI management.

- `__init__(**kwargs)`
  - Accepts optional `_uri` to set the subject IRI; otherwise auto-generates one using the configured namespace + `uuid4`.
- `set_namespace(namespace: str) -> None`
  - Sets the base namespace used for auto-generated URIs.
- `set_query_executor(query_executor: Callable[[str], Iterable[object]] | None) -> None`
  - Sets a class-level SPARQL query executor used by `from_iri()`.
- `from_iri(iri: str, query_executor: Callable[[str], Iterable[object]] | None = None, graph_name: str | None = None) -> RDFEntity`
  - Loads field values from SPARQL results (`SELECT ?p ?o`) and returns an instance of the class.
  - If `label` exists as a model field but is missing from RDF, it is derived from the IRI tail.
  - If required fields are missing, they are set to `None` (or `[]` for list-typed fields) to keep loading permissive.
- `rdf(subject_uri: str | None = None, visited: set[str] | None = None) -> rdflib.Graph`
  - Serializes the entity (and nested related entities) into an RDFLib `Graph`.
  - Adds `rdf:type owl:NamedIndividual` and `rdf:type` of `_class_uri` (if defined), plus `rdfs:label` when present.
  - Performs basic cycle detection via `visited`.

### Alliance “act” classes (participants)
Each of these extends `RDFEntity` and exposes the same fields:
- `label: str | None`
- `created: datetime.datetime | None` (defaults to `datetime.datetime.now()` at import time)
- `creator: Any | None` (defaults to `os.environ.get("USER")` at import time)
- `has_alliance_participant: list[Organization | rdflib.URIRef | str] | None` (object property)

Classes:
- `class ActOfPartnership`
- `class ActOfJointVenture`
- `class ActOfMarketingAlliance`
- `class ActOfResearchCollaboration`
- `class ActOfTechnologyLicensing`
- `class ActOfDistributionAgreement`

### Alliance agreement/document classes (link to the act)
These extend `RDFEntity` (and, for subclasses, also `StrategicAlliance`) and expose:
- `label: str | None`
- `created: datetime.datetime | None` (defaults to `datetime.datetime.now()` at import time)
- `creator: Any | None` (defaults to `os.environ.get("USER")` at import time)
- `is_alliance_agreement_of: rdflib.URIRef | str | None` (object property)

Classes:
- `class StrategicAlliance`
- `class Partnership`
- `class JointVenture`
- `class MarketingAlliance`
- `class ResearchCollaboration`
- `class TechnologyLicensing`
- `class DistributionAgreement`

## Configuration/Dependencies
- **Pydantic**: models are `BaseModel` with `extra="forbid"` and `arbitrary_types_allowed=True`.
- **RDFLib**: serialization uses `rdflib.Graph`, `URIRef`, `Literal`, and namespaces (`RDF`, `RDFS`, `OWL`, `XSD`).
- **Organization dependency**: `has_alliance_participant` may contain `Organization` objects from `...OrganizationOntology`.
- **SPARQL loading**:
  - `RDFEntity.from_iri()` requires a query executor: `Callable[[str], Iterable[object]]`.
  - Set globally with `RDFEntity.set_query_executor(...)` (or pass per call).

## Usage

### Create an alliance act and serialize to RDF
```python
from rdflib import URIRef
from naas_abi_marketplace.domains.intelligence.ontologies.organizations.ontologies.processes.OrganizationAllianceProcess import (
    ActOfPartnership,
)

act = ActOfPartnership(
    label="Partnering act",
    has_alliance_participant=[
        URIRef("http://example.org/org/A"),
        "http://example.org/org/B",
    ],
)

g = act.rdf()
print(g.serialize(format="turtle"))
```

### Load an entity from an IRI (requires SPARQL executor)
```python
from naas_abi_marketplace.domains.intelligence.ontologies.organizations.ontologies.processes.OrganizationAllianceProcess import (
    StrategicAlliance,
)

def executor(sparql: str):
    # Must return iterable rows with bindings for "p" and "o"
    # (e.g., rdflib.query.ResultRow). This is a stub.
    return []

StrategicAlliance.set_query_executor(executor)
obj = StrategicAlliance.from_iri("http://example.org/resource/AllianceDoc1")
print(obj._uri, obj.label)
```

## Caveats
- `created` and `creator` defaults are evaluated at **import time**, not at instance creation time (because `datetime.datetime.now()` and `os.environ.get("USER")` are used as direct defaults).
- `from_iri()`:
  - Requires `iri` without angle brackets; same for `graph_name`.
  - Ignores predicates not present in the class `_property_uris` mapping.
  - Object properties are coerced to `str` IRIs when loaded.
- `rdf()` cycle detection prevents infinite recursion, but still emits relationship triples even when the related entity was already visited.
