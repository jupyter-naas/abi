# PersonnelOntology

## What it is
- A personnel-focused ontology module implemented as Pydantic models.
- Provides a common RDF-backed base (`RDFEntity`) with:
  - automatic URI generation and namespace management
  - RDF serialization to `rdflib.Graph` (`rdf()`)
  - best-effort hydration from SPARQL `SELECT ?p ?o` results (`from_iri()`)

## Public API

### `class RDFEntity(pydantic.BaseModel)`
Base class for RDF-backed entities.

- `set_namespace(namespace: str) -> None`
  - Sets the base namespace used to generate new instance URIs (`_namespace`).

- `set_query_executor(query_executor: Callable[[str], Iterable[object]] | None) -> None`
  - Sets the SPARQL query executor used by `from_iri()`.

- `from_iri(iri: str, query_executor: Callable[[str], Iterable[object]] | None = None, graph_name: str | None = None) -> Self`
  - Loads an instance by querying predicate/object pairs for the given subject IRI (filters out `rdf:type`).
  - Maps predicates using the class’ `_property_uris` and coerces values:
    - object properties → `str(value)`
    - literals → `Literal.toPython()`
    - other RDF terms → `str(value)`
  - If a `label` field exists but was not returned, derives it from the IRI suffix.
  - For required fields missing from results, fills `None` (or `[]` for list-typed required fields).
  - If validation fails, returns a permissive `model_construct(...)` instance.

- `rdf(subject_uri: str | None = None, visited: set[str] | None = None) -> rdflib.Graph`
  - Serializes the instance to RDF:
    - `rdf:type` of `_class_uri` (if present)
    - `rdf:type owl:NamedIndividual`
    - `rdfs:label` if `label` attribute exists
    - field triples based on `_property_uris`
  - Handles object properties as:
    - nested entities (objects with `.rdf()` and `._uri`) with cycle detection via `visited`
    - IRI values (`str`/`URIRef`) when the field is in `_object_properties`
    - otherwise as literals

### Ontology entity models
Each model inherits an ABI ontology base class and `RDFEntity`, and defines:
- `_class_uri`, `_name`
- `_property_uris`: field → predicate IRI mapping
- `_object_properties`: fields treated as object properties

#### `class EmploymentRecord(GenericallyDependentContinuant, RDFEntity)`
- Data fields: `employee_id`, `hire_date`, `termination_date`, `label`, `created`, `creator`
- Object fields: `generically_depends_on`, `is_concretized_by`, `is_employment_record_of`

#### `class EmployeeRole(Role, RDFEntity)`
- Data fields: `label`, `created`, `creator`
- Object fields: `concretizes`, `has_job_position`, `has_realization`, `inheres_in`, `is_employee_role_of`

#### `class JobPosition(GenericallyDependentContinuant, RDFEntity)`
- Data fields: `job_title`, `job_family`, `label`, `created`, `creator`
- Object fields: `generically_depends_on`, `has_job_description`, `is_concretized_by`, `is_job_position_of`

#### `class EmploymentStatus(Quality, RDFEntity)`
- Data fields: `status_value`, `label`, `created`, `creator`
- Object fields: `concretizes`, `inheres_in`, `is_employment_status_of`, `participates_in`

#### `class JobDescription(DocumentContentEntity, RDFEntity)`
- Data fields: `label`, `created`, `creator`
- Object fields: `generically_depends_on`, `is_concretized_by`, `is_job_description_of`

## Configuration/Dependencies
- Dependencies:
  - `pydantic` for model definition/validation
  - `rdflib` for RDF graph construction and terms
  - `naas_abi.ontologies.modules.ABIOntology` for ontology base classes (e.g., `Role`, `Person`, `Quality`, etc.)
- Optional configuration:
  - `RDFEntity.set_namespace(...)` to control auto-generated URIs.
  - `RDFEntity.set_query_executor(...)` (or pass `query_executor=` to `from_iri`) to enable SPARQL-based hydration.

## Usage

### Create an entity and export RDF
```python
from naas_abi_marketplace.domains.personnel.ontologies.modules.PersonnelOntology import JobPosition

jp = JobPosition(job_title="Data Engineer", job_family="Engineering", label="DE I")
g = jp.rdf()
print(g.serialize(format="turtle"))
```

### Load an entity from an IRI (requires a query executor)
```python
from naas_abi_marketplace.domains.personnel.ontologies.modules.PersonnelOntology import EmploymentRecord

def executor(sparql: str):
    # Return an iterable of rows that provide bindings "p" and "o".
    # Rows may be attribute-based (row.p/row.o), dict-like (row["p"]), or tuple/list (p, o).
    return []

EmploymentRecord.set_query_executor(executor)
rec = EmploymentRecord.from_iri("http://example.org/resource/employment-record/123")
print(rec._uri, rec.label)
```

## Caveats
- `from_iri()` raises `ValueError` if no query executor is configured (via argument or `set_query_executor()`).
- `from_iri()` does not instantiate nested models for object properties; it coerces object values to `str`.
- `rdf()` uses cycle detection (`visited`) and will not re-serialize already visited entities (but still adds linking triples).
- Pydantic config forbids unknown fields (`extra="forbid"`).
