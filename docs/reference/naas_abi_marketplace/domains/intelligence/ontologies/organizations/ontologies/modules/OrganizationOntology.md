# OrganizationOntology

## What it is
- A set of Pydantic models representing organization-related ontology entities.
- Provides:
  - URI/namespace management for RDF resources.
  - RDF serialization to an `rdflib.Graph`.
  - Optional loading of model instances from SPARQL query results (`from_iri`).

## Public API

### Class: `RDFEntity` (base model)
- Purpose: Base class for RDF-backed entities with automatic URI handling and RDF serialization.

**Class methods**
- `set_namespace(namespace: str) -> None`
  - Sets the namespace used to generate new `_uri` values.
- `set_query_executor(query_executor: Callable[[str], Iterable[object]] | None) -> None`
  - Sets the SPARQL query executor used by `from_iri()` when no executor is passed.
- `from_iri(iri: str, query_executor: Callable[[str], Iterable[object]] | None = None, graph_name: str | None = None) -> Self`
  - Loads an instance from RDF via SPARQL `SELECT ?p ?o` results.
  - Maps predicates using the subclass’ `_property_uris`.
  - Coerces values:
    - Object properties → string IRI
    - Literals → Python values via `Literal.toPython()`

**Instance methods**
- `rdf(subject_uri: str | None = None, visited: set[str] | None = None) -> rdflib.Graph`
  - Serializes the instance (and nested `RDFEntity` objects) into RDF triples.
  - Adds:
    - `rdf:type` of the entity’s `_class_uri` (if defined)
    - `rdf:type owl:NamedIndividual`
    - `rdfs:label` if `label` is present
  - Performs cycle detection via `visited`.

### Ontology entity classes (all inherit `RDFEntity`)
- `Organization`
- `Website`
- `Ticker`
- `Industry`
- `Brand`
- `TechnologicalCapabilities`
- `HumanCapabilities`
- `GlobalHeadquarters`
- `RegionalHeadquarters`
- `IncorporatedOrganization` (specialized `Organization`)
- `GeopoliticalOrganization` (specialized `Organization`)
- `GovernmentOrganization` (specialized `Organization`)
- `CommercialOrganization` (specialized `Organization`)
- `EducationalOrganization` (specialized `Organization`)
- `CivilOrganization` (specialized `Organization`)
- `Government` (specialized `Organization`)

Each class defines:
- `_class_uri`: RDF class IRI.
- `_property_uris`: mapping of model field names → predicate IRIs.
- `_object_properties`: set of fields treated as object properties (serialized as URIs; in `from_iri`, coerced to strings).

## Configuration/Dependencies
- Dependencies:
  - `pydantic.BaseModel` (model validation/serialization)
  - `rdflib` (`Graph`, `URIRef`, `Literal`, namespaces)
- Environment:
  - Several models default `creator` to `os.environ.get("USER")`.
- SPARQL loading:
  - `RDFEntity.from_iri()` requires a query executor:
    - Either pass `query_executor` per call, or set globally with `set_query_executor()`.

## Usage

### Create entities and serialize to RDF
```python
from rdflib import URIRef
from naas_abi_marketplace.domains.intelligence.ontologies.organizations.ontologies.modules.OrganizationOntology import (
    Organization, Website
)

org = Organization(
    label="Acme Corp",
    organization_id="acme-001",
    has_website=[Website(label="Acme Website", website_url="https://acme.example")]
)

g = org.rdf()
print(g.serialize(format="turtle"))
```

### Load an entity from an IRI using a SPARQL executor
```python
from naas_abi_marketplace.domains.intelligence.ontologies.organizations.ontologies.modules.OrganizationOntology import Organization

def exec_sparql(query: str):
    # Return iterable rows with bindings for "p" and "o"
    # (Implementation depends on your SPARQL client)
    return []

Organization.set_query_executor(exec_sparql)
org = Organization.from_iri("http://ontology.naas.ai/abi/some-org-iri")
```

## Caveats
- `from_iri()`:
  - Rejects IRIs containing angle brackets (`<` or `>`).
  - Requires a configured query executor; otherwise raises `ValueError`.
  - Ignores predicates not present in `_property_uris`.
  - If validation fails, it falls back to `model_construct(...)` (permissive partial loading).
- RDF serialization:
  - Cycle detection prevents infinite recursion; already-visited nodes return an empty subgraph but relationship triples are still emitted by the caller.
- Defaults:
  - `created` defaults to `datetime.datetime.now()` at instance creation time.
  - `creator` defaults from `USER` environment variable (may be `None`).
