# SPARQLUtils

## What it is
Utility wrapper around an `ITripleStoreService` for common SPARQL operations:
- Convert rdflib query results to Python structures
- Lookup class/type, labels, and identifiers
- Build a subgraph around a subject URI via a dynamic `CONSTRUCT` query

## Public API
### Class: `SPARQLUtils`
- `__init__(triple_store_service: ITripleStoreService)`
  - Stores a triple store service used to execute SPARQL queries.

- `triple_store_service -> ITripleStoreService` (property)
  - Returns the configured triple store service instance.

- `results_to_list(results: rdflib.query.Result) -> Optional[List[Dict]]`
  - Transforms `rdflib` SPARQL result rows into a `list[dict]` keyed by variable labels.
  - Values are converted to `str`; missing values become `None`.
  - Returns `None` if there are no rows.

- `get_class_uri_from_individual_uri(uri: str | URIRef) -> Optional[str]`
  - Queries `rdf:type` for the given individual and returns the first type that is **not** `owl:NamedIndividual`.
  - Returns `None` on no match or on error.

- `get_rdfs_label_from_individual_uri(uri: str | URIRef) -> Optional[str]`
  - Queries `rdfs:label` for the given URI and returns the first label as a string.
  - Returns `None` on no match or on error.

- `get_identifier(identifier: str, type: URIRef = URIRef("http://ontology.naas.ai/abi/unique_id"), graph: Graph = Graph()) -> Optional[URIRef]`
  - Looks up a subject `?s` where `?s <type> "identifier"`.
  - If `graph` is non-empty, runs the query against that `rdflib.Graph`; otherwise queries the triple store.
  - Returns the first matching subject URI, else `None`.

- `get_identifiers(property_uri: URIRef = URIRef("http://ontology.naas.ai/abi/unique_id"), class_uri: Optional[URIRef] = None) -> dict[str, URIRef]`
  - Returns a mapping `{identifier_literal_as_str: subject_uri}` for all triples matching `?s <property_uri> ?id`.
  - If `class_uri` is provided, restricts to `?s a <class_uri>`.
  - Returns `{}` on error.

- `get_subject_graph(uri: str | URIRef, depth: int = 1) -> Graph`
  - Builds a subgraph using a `CONSTRUCT` query:
    - Depth 1: `<uri> ?p0 ?o0`
    - Depth > 1: optionally follows object URIs (`FILTER(isURI(?o{i-1}))`) to include their outgoing triples up to the specified depth.
  - Returns an empty graph if `depth <= 0` or on query error.
  - Binds standard prefixes: `rdfs`, `rdf`, `owl`, `xsd`, `dcterms`, `abi`, `bfo`, `cco`, `test`.

## Configuration/Dependencies
- Requires an implementation of `naas_abi_core.services.triple_store.TripleStorePorts.ITripleStoreService` with a `.query(sparql: str)` method.
- Uses `rdflib` (`Graph`, `URIRef`, namespaces, query result types).
- Uses `naas_abi_core.logger` for error logging.
- Imports namespaces from `naas_abi_core.utils.Graph`: `ABI`, `BFO`, `CCO`, `TEST` (used for prefix binding in `get_subject_graph`).

## Usage
```python
from rdflib import URIRef
from naas_abi_core.utils.SPARQL import SPARQLUtils

# triple_store_service must implement ITripleStoreService (with .query(str) -> rdflib results)
utils = SPARQLUtils(triple_store_service)

person = URIRef("http://example.org/resource/123")

label = utils.get_rdfs_label_from_individual_uri(person)
cls = utils.get_class_uri_from_individual_uri(person)

subgraph = utils.get_subject_graph(person, depth=2)

id_map = utils.get_identifiers()
existing = utils.get_identifier("ABC-123")
```

## Caveats
- `get_subject_graph` only traverses *outgoing* triples starting from the subject, and only follows object nodes that are URIs (not literals/blank nodes).
- Several methods return `None`/`{}` on exceptions and log errors; callers should handle missing results.
- `get_identifier` uses a default argument `graph=Graph()`; if you mutate/pass that default graph implicitly, it may be shared across calls within the process.
