# OrganizationRestructuringProcess

## What it is
- A small set of **Pydantic models** representing organization restructuring concepts (merger, acquisition, subsidiary establishment) that can:
  - Generate **RDF triples** via `rdflib`.
  - Optionally **load instances from an IRI** via a user-provided SPARQL query executor.

## Public API

### Base: `RDFEntity`
- Purpose: common RDF/URI behavior for all models.

**Constructor**
- `RDFEntity(**kwargs)`
  - If `_uri` is provided, uses it.
  - Otherwise generates a URI using the class `_namespace` and a UUID.

**Class methods**
- `set_namespace(namespace: str) -> None`
  - Sets the namespace used for auto-generated URIs.
- `set_query_executor(query_executor: Callable[[str], Iterable[object]] | None) -> None`
  - Sets a callable used by `from_iri()` to execute SPARQL queries.
- `from_iri(iri: str, query_executor: Callable[[str], Iterable[object]] | None = None, graph_name: str | None = None) -> Self`
  - Executes a SPARQL `SELECT ?p ?o` query for the subject `iri`.
  - Maps predicates to model fields using `_property_uris`.
  - Coerces values:
    - object properties → string IRI
    - literals → `toPython()`
  - If `label` exists on the model but is missing in results, a fallback label is derived from the IRI.
  - If validation fails, returns a permissively constructed model via `model_construct`.

**Instance methods**
- `rdf(subject_uri: str | None = None, visited: set[str] | None = None) -> rdflib.Graph`
  - Produces an RDF graph for the instance, including:
    - `rdf:type` of the class (`_class_uri`) when present
    - `owl:NamedIndividual`
    - `rdfs:label` when `label` exists
    - Triples for each field in `_property_uris`
  - Supports nested objects that also implement `rdf()` and have `_uri`.
  - Includes basic cycle detection through `visited`.

### Domain models

#### `ActOfOrganizationalMerger(RDFEntity)`
- Fields:
  - `label: str | None`
  - `created: datetime.datetime | None` (default: `datetime.datetime.now()`)
  - `creator: Any | None` (default: `os.environ.get("USER")`)
  - `has_merging_organization: list[Organization | rdflib.URIRef | str] | None` (object property)

#### `ActOfOrganizationalAcquisition(RDFEntity)`
- Fields:
  - `label: str | None`
  - `created: datetime.datetime | None` (default: `datetime.datetime.now()`)
  - `creator: Any | None` (default: `os.environ.get("USER")`)
  - `has_acquired_organization: list[Organization | rdflib.URIRef | str] | None` (object property)
  - `has_acquiring_organization: list[Organization | rdflib.URIRef | str] | None` (object property)

#### `ActOfSubsidiaryEstablishment(RDFEntity)`
- Fields:
  - `label: str | None`
  - `created: datetime.datetime | None` (default: `datetime.datetime.now()`)
  - `creator: Any | None` (default: `os.environ.get("USER")`)
  - `bFO_0000057: list[Organization | rdflib.URIRef | str] | None` (object property)

#### `OrganizationMerger(RDFEntity)`
- Fields:
  - `label: str | None`
  - `created: datetime.datetime | None` (default: `datetime.datetime.now()`)
  - `creator: Any | None` (default: `os.environ.get("USER")`)

#### `OrganizationAcquisition(RDFEntity)`
- Fields:
  - `label: str | None`
  - `created: datetime.datetime | None` (default: `datetime.datetime.now()`)
  - `creator: Any | None` (default: `os.environ.get("USER")`)

## Configuration/Dependencies
- Dependencies:
  - `pydantic` (`BaseModel`, `Field`, `ValidationError`)
  - `rdflib` (`Graph`, `Literal`, `Namespace`, `URIRef`) and namespaces (`RDF`, `RDFS`, `OWL`, `XSD`)
  - `naas_abi_marketplace...OrganizationOntology.Organization` (used in type hints for object properties)
- Optional runtime configuration:
  - `RDFEntity.set_namespace(...)` to control auto-generated URIs.
  - `RDFEntity.set_query_executor(...)` (or pass `query_executor=` to `from_iri`) to enable loading from SPARQL.

## Usage

### Generate RDF for a merger act
```python
from rdflib import URIRef
from naas_abi_marketplace.domains.intelligence.ontologies.organizations.ontologies.processes.OrganizationRestructuringProcess import (
    ActOfOrganizationalMerger,
)

act = ActOfOrganizationalMerger(
    label="Merger act",
    has_merging_organization=[
        URIRef("http://example.org/org/A"),
        "http://example.org/org/B",
    ],
)

g = act.rdf()
print(g.serialize(format="turtle"))
```

### Load an instance from an IRI (requires a query executor)
```python
from naas_abi_marketplace.domains.intelligence.ontologies.organizations.ontologies.processes.OrganizationRestructuringProcess import (
    OrganizationMerger,
)

def query_executor(sparql: str):
    # Must return iterable rows that provide bindings "p" and "o"
    return []

OrganizationMerger.set_query_executor(query_executor)
obj = OrganizationMerger.from_iri("http://example.org/resource/merger-1")
print(obj._uri, obj.label)
```

## Caveats
- `from_iri()` requires a query executor; otherwise it raises `ValueError`.
- `from_iri()` ignores predicates not declared in `_property_uris`.
- `created` defaults to `datetime.datetime.now()` evaluated at import time (static default value), not at instance creation time.
- Object properties are emitted as `URIRef(...)` when values are `str`/`URIRef`; other values become RDF literals.
