# NexusPlatformOntology

## What it is
A set of Pydantic models representing Nexus Platform ontology entities that can:
- Generate RDF triples (`rdflib.Graph`) for instances.
- Optionally hydrate instances from a SPARQL endpoint via a configurable query executor.

All domain classes inherit from `RDFEntity`.

## Public API

### `class RDFEntity(pydantic.BaseModel)`
Base class for all ontology entities.

- **Constructor**: `RDFEntity(**kwargs)`
  - Accepts an optional `_uri` kwarg.
  - If `_uri` is not provided, generates one using the class namespace + UUID.
- **Class methods**
  - `set_namespace(namespace: str) -> None`: Sets the base namespace used when auto-generating URIs.
  - `set_query_executor(query_executor: Callable[[str], Iterable[object]] | None) -> None`: Sets the SPARQL query executor used by `from_iri`.
  - `from_iri(iri: str, query_executor: Callable[[str], Iterable[object]] | None = None, graph_name: str | None = None) -> Self`:
    - Runs a SPARQL query to fetch predicate/object pairs for `iri`.
    - Maps predicates to model fields using `_property_uris`.
    - Coerces object-property values to `str` IRIs; data-property literals to Python values when possible.
    - If `label` exists in the model but is missing from results, derives a fallback from the IRI.
    - If validation fails, returns a permissive `model_construct(...)` instance.
- **Instance methods**
  - `rdf(subject_uri: str | None = None, visited: set[str] | None = None) -> rdflib.Graph`:
    - Emits RDF for the instance including:
      - `rdf:type` of `_class_uri` (if present)
      - `rdf:type owl:NamedIndividual`
      - `rdfs:label` if `label` attribute exists
      - All mapped properties in `_property_uris`
    - Supports nested RDF emission for related `RDFEntity` objects and cycle detection via `visited`.

### Domain entity classes (all subclass `RDFEntity`)
Each class defines:
- `_class_uri`: RDF class IRI
- `_property_uris`: mapping from field name → predicate IRI
- `_object_properties`: which fields should be treated as object properties (IRI refs)

Classes:
- `Tenant`
- `Server`
- `DeploymentSite`
- `User`
- `Organization`
- `Workspace`
- `Search`
- `Conversation`
- `Message`
- `Agent`
- `AgentTool`
- `AgentIntent`
- `Ontology`
- `OntologyModule`
- `OntologyClass`
- `OntologyObjectProperty`
- `KnowledgeGraph`
- `GraphView`
- `GraphFilter`
- `Files`
- `FileSystem`
- `MarketplaceApps`
- `WorkspaceRole`
- `SearchRole`
- `ConversationRole`
- `MessageRole`
- `AgentRole`
- `OntologyRole`
- `OntologyModuleRole`
- `OntologyClassRole`
- `OntologyObjectPropertyRole`
- `KnowledgeGraphRole`
- `GraphViewRole`
- `GraphFilterRole`
- `FileRole`
- `FileSystemRole`
- `MarketplaceAppRole`

## Configuration/Dependencies
- **Dependencies**
  - `pydantic` (models/validation)
  - `rdflib` (Graph, URIRef, Literal, namespaces)
- **Environment**
  - Many models default `creator` to `os.environ.get("USER")`.
- **SPARQL hydration**
  - `RDFEntity.from_iri(...)` requires a query executor:
    - Set globally via `RDFEntity.set_query_executor(...)`, or pass per call.

## Usage

### Create an entity and generate RDF
```python
from naas_abi.ontologies.modules.NexusPlatformOntology import Organization, Workspace

org = Organization(label="Acme Inc.")
ws = Workspace(label="Main Workspace", is_workspace_of=[org])

g = ws.rdf()
print(g.serialize(format="turtle"))
```

### Load an entity from an IRI (requires SPARQL executor)
```python
from naas_abi.ontologies.modules.NexusPlatformOntology import Workspace, RDFEntity

def executor(sparql: str):
    # Return an iterable of rows with bindings for ?p and ?o.
    # This is endpoint/client specific.
    return []

RDFEntity.set_query_executor(executor)
ws = Workspace.from_iri("http://example.org/workspaces/1")
print(ws._uri, ws.label)
```

## Caveats
- `from_iri()`:
  - Rejects IRIs (and `graph_name`) containing angle brackets (`<` or `>`).
  - Only populates fields whose predicate IRIs exist in the class `_property_uris` mapping.
  - For object properties, values are coerced to `str` IRIs (not auto-instantiated as other models).
  - If validation fails, it returns a partially-populated instance via `model_construct`.
- Many object-property fields default to `["http://ontology.naas.ai/abi/unknown"]` (a placeholder IRI).
- Default `created` uses `datetime.datetime.now()` at import time as written (model field default), not at instance creation time.
