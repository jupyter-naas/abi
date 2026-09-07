# XSearchRecentTweetsProcess

## What it is
A set of Pydantic models representing an RDF/OWL ontology for “Search Recent Tweets” on X (Twitter), including search queries, result sets, roles, and search intervals. Models can:
- Generate RDF triples (`rdflib.Graph`) for instances.
- Load instances from an RDF store via SPARQL (`from_iri`) when a query executor is configured.

## Public API

### Base
- `class RDFEntity(BaseModel)`
  - Purpose: Base class adding RDF identity (URI), namespace management, SPARQL loading, and RDF graph serialization.
  - Key methods:
    - `set_namespace(namespace: str) -> None`: Set default namespace used to auto-generate `_uri`.
    - `set_query_executor(query_executor: Callable[[str], Iterable[object]] | None) -> None`: Configure SPARQL executor used by `from_iri`.
    - `from_iri(iri: str, query_executor: Callable[[str], Iterable[object]] | None = None, graph_name: str | None = None) -> Self`: Hydrate a model from RDF triples returned by SPARQL.
    - `rdf(subject_uri: str | None = None, visited: set[str] | None = None) -> rdflib.Graph`: Serialize the instance (and nested RDFEntity objects) to RDF, with cycle detection.

### Ontology models
- `class SearchQuery(GenericallyDependentContinuant, RDFEntity)`
  - Purpose: Represents an X v2 recent-tweet search query artifact and its parameters (e.g., `query_string`, `start_time`, `max_results`, field selections).
  - Links via object properties to:
    - `SearchQueryRole` (`has_search_query_role`)
    - `SearchRecentTweets` (`is_search_query_of`)
    - Other ABI ontology relations (`generically_depends_on`, `is_concretized_by`)

- `class SearchResultSet(GenericallyDependentContinuant, RDFEntity)`
  - Purpose: Represents a persisted set of search results, including counts and paging (`result_count`, `referenced_count`, `next_token`, etc.).
  - Links via object properties to:
    - Matched tweets (`contains_tweet`: `Tweet`)
    - Referenced tweets for context (`contains_referenced_tweet`: `ReferencedTweet`)
    - Producer process (`is_produced_by`: `SearchRecentTweets`)

- `class SearchQueryRole(Role, RDFEntity)`
  - Purpose: Role that a search query artifact bears when realized in a search process.
  - Links to:
    - `SearchQuery` (`is_search_query_role_of`)
    - Realizing processes (`has_realization`)

- `class SearchRecentTweets(Process, RDFEntity)`
  - Purpose: The process of calling X v2 recent search and retrieving matches and expansions.
  - Links to:
    - Query used (`uses_search_query`: `SearchQuery`)
    - Produced results (`produces_search_result`: `SearchResultSet`)
    - Retrieved entities (`retrieves_tweet`, `retrieves_referenced_tweet`, `retrieves_user`, `retrieves_media`)
    - Execution context (`executed_at`, `executed_by`, `has_search_interval`, etc.)

- `class SearchInterval(TemporalRegion, RDFEntity)`
  - Purpose: Temporal interval bounding a search run (started/ended instants).
  - Links to:
    - Instants (`search_started_at`, `search_ended_at`, `has_first_instant`, `has_last_instant`)

## Configuration/Dependencies
- Runtime dependencies:
  - `pydantic` (models/validation)
  - `rdflib` (RDF graph creation and terms)
- External ontology types imported from:
  - `naas_abi.ontologies.modules.ABIOntology`
  - `naas_abi_marketplace.applications.x.ontologies.modules.XOntology`
- Optional configuration for SPARQL loading:
  - Provide a SPARQL executor function to `RDFEntity.set_query_executor(...)` or pass it to `from_iri(...)`.
  - `from_iri(..., graph_name="...")` supports querying within a named graph.

## Usage

### Create instances and generate RDF
```python
from rdflib import Graph
from naas_abi_marketplace.applications.x.ontologies.processes.XSearchRecentTweetsProcess import (
    SearchQuery, SearchRecentTweets, SearchResultSet
)

q = SearchQuery(
    query_string="from:demo -is:retweet",
    max_results=10,
    label="Recent tweets query",
)

p = SearchRecentTweets(
    label="Search run",
    uses_search_query=[q],
)

rs = SearchResultSet(
    label="Result set",
    result_count=0,
    is_produced_by=[p],
)

g: Graph = rs.rdf()
print(len(g))  # number of triples
```

### Load an instance from an RDF store (SPARQL)
```python
from naas_abi_marketplace.applications.x.ontologies.processes.XSearchRecentTweetsProcess import SearchQuery

def executor(sparql: str):
    # Must return an iterable of rows with bindings for variables `p` and `o`.
    # Integrate your RDF store client here.
    return []

SearchQuery.set_query_executor(executor)
obj = SearchQuery.from_iri("http://ontology.naas.ai/abi/some-resource")
print(obj._uri, obj.label)
```

## Caveats
- `from_iri` requires a configured query executor; otherwise it raises `ValueError`.
- `from_iri` only maps predicates defined in the model’s `_property_uris`; unknown predicates are ignored.
- For required fields missing from RDF results, `from_iri` fills `None` or `[]` (for list-typed fields) to keep loading permissive.
- `rdf()` performs cycle detection using a `visited` URI set; already-visited related entities are not re-serialized, but relationship triples are still emitted.
