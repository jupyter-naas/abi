# DocumentOntology

## What it is
- A small RDF/OWL modeling layer using **Pydantic** models to represent ontology entities and serialize/deserialize them as RDF.
- Defines a base `RDFEntity` plus three domain entities: `File`, `Document`, and `Processor`.
- Supports:
  - Auto-generated URIs (UUID-based) with configurable namespace
  - RDF graph generation via `rdflib`
  - Loading instances from an IRI via SPARQL query results (requires a query executor)

## Public API

### `class RDFEntity(pydantic.BaseModel)`
Base class for RDF-backed entities.

- `set_namespace(namespace: str) -> None`
  - Sets the namespace used to generate new instance URIs.
- `set_query_executor(query_executor: Callable[[str], Iterable[object]] | None) -> None`
  - Sets a callable used by `from_iri()` to execute SPARQL queries.
- `from_iri(iri: str, query_executor: Callable[[str], Iterable[object]] | None = None, graph_name: str | None = None) -> Self`
  - Loads an instance by querying triples `<iri> ?p ?o` (excluding `rdf:type`).
  - Maps predicate URIs to model fields via the class’ `_property_uris`.
  - Coerces literals to Python values; object properties become string IRIs.
  - If `label` is a model field and missing, it is derived from the IRI.
- `rdf(subject_uri: str | None = None, visited: set[str] | None = None) -> rdflib.Graph`
  - Serializes the instance to an RDFLib `Graph`.
  - Adds:
    - `rdf:type` of the class (`_class_uri`) when present
    - `rdf:type owl:NamedIndividual`
    - `rdfs:label` if `label` attribute exists
  - Recursively serializes related `RDFEntity` objects; uses `visited` for cycle detection.

### `class File(RDFEntity)`
Ontology class: `http://ontology.naas.ai/abi/document/File`

- Data fields (Pydantic):
  - `file_path: Optional[str] = "unknown"`
  - `file_name: Optional[str] = "unknown"`
  - `mime_type: Optional[str] = "unknown"`
  - `file_size_bytes: Optional[int]`
  - `created_time: Optional[datetime.datetime]`
  - `modified_time: Optional[datetime.datetime]`
  - `accessed_time: Optional[datetime.datetime]`
  - `permissions: Optional[str] = "unknown"`
  - `encoding: Optional[str] = "unknown"`
  - `sha256: Optional[str] = "unknown"`
  - `label: str` (required)
  - `created: Optional[datetime.datetime] = datetime.datetime.now()`
  - `creator: Optional[Any] = os.environ.get("USER")`
- Object properties (treated as IRIs in RDF):
  - `derivedFrom: Optional[List[Union[File, rdflib.URIRef, str]]] = ["http://ontology.naas.ai/abi/unknown"]`
  - `embodies: Optional[List[Union[Document, rdflib.URIRef, str]]] = ["http://ontology.naas.ai/abi/unknown"]`
  - `processedBy: Optional[List[Union[Processor, rdflib.URIRef, str]]] = ["http://ontology.naas.ai/abi/unknown"]`

### `class Document(RDFEntity)`
Ontology class: `http://ontology.naas.ai/abi/document/Document`

- Data fields:
  - `sha256: Optional[str] = "unknown"`
  - `label: str` (required)
  - `created: Optional[datetime.datetime] = datetime.datetime.now()`
  - `creator: Optional[Any] = os.environ.get("USER")`
- Object properties:
  - `isEmbodiedIn: Optional[List[Union[File, rdflib.URIRef, str]]] = ["http://ontology.naas.ai/abi/unknown"]`

### `class Processor(RDFEntity)`
Ontology class: `http://ontology.naas.ai/abi/document/Processor`

- Data fields:
  - `label: str` (required)
  - `created: Optional[datetime.datetime] = datetime.datetime.now()`
  - `creator: Optional[Any] = os.environ.get("USER")`

## Configuration/Dependencies
- Dependencies:
  - `pydantic.BaseModel`, `pydantic.Field`, `pydantic.ValidationError`
  - `rdflib.Graph`, `rdflib.Literal`, `rdflib.Namespace`, `rdflib.URIRef`
  - `rdflib.namespace` constants: `OWL`, `RDF`, `RDFS`, `XSD`
- Namespace configuration:
  - Default URI namespace for new instances: `RDFEntity._namespace = "http://ontology.naas.ai/abi/"`
  - Override with `RDFEntity.set_namespace("...")`
- SPARQL loading:
  - `RDFEntity.from_iri()` requires a `query_executor` callable (set per-call or via `set_query_executor`).
  - Optional `graph_name` scopes the query to `GRAPH <graph_name> { ... }`.

## Usage

### Create entities and serialize to RDF
```python
from naas_abi_marketplace.domains.document.ontologies.modules.DocumentOntology import (
    File, Document, Processor
)

doc = Document(label="Invoice #123")
proc = Processor(label="OCR Pipeline")
f = File(label="invoice.pdf", embodies=[doc], processedBy=[proc])

g = f.rdf()
print(g.serialize(format="turtle"))
```

### Load an entity from an IRI (requires SPARQL executor)
```python
from naas_abi_marketplace.domains.document.ontologies.modules.DocumentOntology import File

def exec_sparql(query: str):
    # Return an iterable of rows where row["p"] and row["o"] (or attributes p/o) exist.
    # This is a placeholder; integrate with your SPARQL client.
    return []

File.set_query_executor(exec_sparql)
loaded = File.from_iri("http://example.org/resource/file-1")
print(loaded._uri, loaded.label)
```

## Caveats
- `label` is required on `File`, `Document`, and `Processor`; `from_iri()` will synthesize it from the IRI only if missing in query results.
- `from_iri()` rejects IRIs (and `graph_name`) containing angle brackets (`<`, `>`).
- Object properties in `from_iri()` are coerced to **string IRIs** (not automatically instantiated as `RDFEntity` objects).
- Some fields default to values at import/instantiation time:
  - `created` defaults to `datetime.datetime.now()` at model creation time (as written).
  - `creator` defaults to `os.environ.get("USER")`.
