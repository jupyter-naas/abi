# BirthRegistrationProcess

## What it is
- A Pydantic-based ontology/model module for representing a birth domain as RDF.
- Provides:
  - RDF serialization to `rdflib.Graph` via `rdf()`
  - Optional loading from an RDF store via SPARQL with `from_iri()` when a query executor is configured

## Public API

### Base class: `RDFEntity` (inherits `pydantic.BaseModel`)
- `set_namespace(namespace: str) -> None`
  - Sets the base namespace used to auto-generate `_uri` values for new instances.
- `set_query_executor(query_executor: Callable[[str], Iterable[object]] | None) -> None`
  - Configures the SPARQL query executor used by `from_iri()`.
- `from_iri(iri: str, query_executor: Callable[[str], Iterable[object]] | None = None, graph_name: str | None = None) -> RDFEntity`
  - Loads an instance by querying predicates/objects for `iri` and mapping known predicates (declared in `_property_uris`) to model fields.
- `rdf(subject_uri: str | None = None, visited: set[str] | None = None) -> rdflib.Graph`
  - Serializes the instance to RDF triples.
  - Recursively serializes related objects that implement `rdf()` and have `_uri`, using `visited` for cycle detection.

### Domain models (all inherit `RDFEntity`)
Each model:
- Auto-assigns a `_uri` if not provided.
- Defines `_class_uri`, `_property_uris`, and (optionally) `_object_properties`.

Models:
- `Birth`
  - Object properties: `bFO_0000055`, `bFO_0000057`, `bFO_0000059`, `bFO_0000066`, `bFO_0000199`
- `TemporalRegion`
- `Animal`
  - Object properties: `bFO_0000196`
- `Site`
- `BirthRecord`
- `Weight`
  - Object property: `bFO_0000197`
- `Length`
  - Object property: `bFO_0000197`
- `GestationalAge`
  - Object property: `bFO_0000197`
- `BiologicalSex`
  - Object property: `bFO_0000197`
- `BirthFunction`
  - Object property: `bFO_0000197`
- `NewbornDisposition`
  - Object property: `bFO_0000197`

## Configuration/Dependencies
- Dependencies:
  - `pydantic` (modeling/validation)
  - `rdflib` (RDF graph and node types)
- Defaults:
  - Many models set `created` to `datetime.datetime.now()` at instantiation.
  - Many models set `creator` to `os.environ.get("USER")` at instantiation.
- SPARQL loading:
  - `from_iri()` requires a query executor (`Callable[[str], Iterable[object]]`) passed in or set via `set_query_executor()`.
  - Optional `graph_name` targets a named graph in the SPARQL query.

## Usage

### Create entities and serialize to RDF
```python
from naas_abi_marketplace.domains.personnel.ontologies.processes.BirthRegistrationProcess import (
    Birth, BirthRecord, Site
)

birth = Birth(
    label="Birth event",
    bFO_0000059=[BirthRecord(label="Record #1")],
    bFO_0000066=[Site(label="Hospital A")],
)

g = birth.rdf()
print(g.serialize(format="turtle"))
```

### Load an entity from an IRI (requires a query executor)
```python
from naas_abi_marketplace.domains.personnel.ontologies.processes.BirthRegistrationProcess import Birth

def executor(sparql: str):
    # Must return iterable rows with bindings for "p" and "o"
    return []

Birth.set_query_executor(executor)
birth = Birth.from_iri("http://example.org/birth/123")
```

## Caveats
- `from_iri()`:
  - Rejects `iri` (and `graph_name`) containing angle brackets (`<` or `>`).
  - Only maps predicates present in the class `_property_uris`; other triples are ignored.
  - If `label` is missing and the model has a `label` field, a fallback label is derived from the IRI.
  - On validation errors, it falls back to `model_construct(...)`, so instances may be partially populated.
- `rdf()`:
  - Always adds `rdf:type owl:NamedIndividual`.
  - Adds `rdf:type` of `_class_uri` when present.
  - Uses `visited` to prevent infinite recursion; already-visited related entities are not re-serialized, but relationship triples are still emitted.
