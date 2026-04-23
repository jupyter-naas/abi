# SPARQLUtils

## What it is
Utility class for running SPARQL queries via an injected triple-store service and for converting/common lookups around individuals, identifiers, and extracting a subject-centric subgraph.

## Public API
- `class SPARQLUtils(triple_store_service: ITripleStoreService)`
  - Wraps an `ITripleStoreService` to execute SPARQL queries and provides helper methods.

### Properties
- `triple_store_service -> ITripleStoreService`
  - Returns the injected triple store service.

### Methods
- `results_to_list(results: rdflib.query.Result) -> Optional[List[Dict]]`
  - Converts `rdflib` SPARQL results into a list of dicts keyed by variable labels; returns `None` if empty.

- `get_class_uri_from_individual_uri(uri: str | URIRef) -> Optional[str]`
  - Queries the triple store for the first `rdf:type` of the given individual excluding `owl:NamedIndividual`.
  - Returns the type as a `URIRef` (despite the annotation saying `Optional[str]`), or `None` on no match/error.

- `get_rdfs_label_from_individual_uri(uri: str | URIRef) -> Optional[str]`
  - Queries the triple store for the first `rdfs:label` of the given individual.

- `get_identifier(identifier: str, type: URIRef = URIRef("http://ontology.naas.ai/abi/unique_id"), graph: Graph = Graph()) -> Optional[URIRef]`
  - Looks up a subject `?s` with predicate `type` and literal value `identifier`.
  - If `graph` is non-empty, queries that graph; otherwise queries the triple store.

- `get_identifiers(property_uri: URIRef = URIRef("http://ontology.naas.ai/abi/unique_id"), class_uri: Optional[URIRef] = None) -> dict[str, URIRef]`
  - Returns a mapping `{identifier_literal: subject_uri}` for all triples matching `?s property_uri ?id`.
  - Optionally filters to subjects of `rdf:type class_uri`.

- `get_subject_graph(uri: str | URIRef, depth: int = 1, graph_names: list[str] = []) -> Graph`
  - Runs a `CONSTRUCT` query across the provided named graphs to build a subgraph rooted at `uri`.
  - Depth controls chained traversal: depth 1 includes `<uri> ?p0 ?o0`; higher depths optionally follow object URIs.
  - Binds common namespaces (`rdfs`, `rdf`, `owl`, `xsd`, `dcterms`, `abi`, `bfo`, `cco`) on the returned graph.

## Configuration/Dependencies
- Requires an implementation of `naas_abi_core.services.triple_store.TripleStorePorts.ITripleStoreService` with a `query(sparql: str)` method.
- Uses `rdflib` (`Graph`, `URIRef`, query results).
- Uses `naas_abi_core.logger` for error logging.
- Uses namespace constants from `naas_abi_core.utils.Graph`: `ABI`, `BFO`, `CCO`.

## Usage
```python
from rdflib import URIRef
from naas_abi_core.utils.SPARQL import SPARQLUtils

# triple_store_service must implement ITripleStoreService
sparql = SPARQLUtils(triple_store_service)

person = URIRef("http://example.org/individual/123")

label = sparql.get_rdfs_label_from_individual_uri(person)
cls = sparql.get_class_uri_from_individual_uri(person)

id_uri = sparql.get_identifier("ABC-123")

subgraph = sparql.get_subject_graph(
    person,
    depth=2,
    graph_names=["http://example.org/graph/main"],
)
print(len(subgraph))
```

## Caveats
- `get_class_uri_from_individual_uri` is annotated to return `Optional[str]` but returns a `URIRef` on success.
- `get_subject_graph` always includes `VALUES ?g { ... }`; if `graph_names` is empty, the query may fail depending on the triple store.
- `get_identifier` defaults `graph` to an empty `Graph()` created at function definition time; it is only used when it contains triples (`len(graph) > 0`).
