# XCountRecentTweetsProcess

## What it is
- A small ontology/model layer for representing **X (Twitter) recent tweet count** artifacts as RDF-backed Pydantic models.
- Provides:
  - A base `RDFEntity` with URI management, SPARQL loading (`from_iri`), and RDF serialization (`rdf`).
  - Domain models for count processes and results:
    - `CountRecentTweets` (process)
    - `TweetCountResultSet` (result set)
    - `TweetCountBucket` (per-bucket counts)
    - `CountInterval` (temporal bucket interval)

## Public API

### Classes

- `RDFEntity(BaseModel)`
  - Base class for RDF entities.
  - Responsibilities:
    - Generate/manage `_uri` values (UUID-based in a configurable namespace).
    - Load instances from SPARQL results: `from_iri(...)`.
    - Serialize instances (and linked objects) to RDFLib `Graph`: `rdf(...)`.
    - Manage a shared SPARQL executor: `set_query_executor(...)`.

- `TweetCountResultSet(GenericallyDependentContinuant, RDFEntity)`
  - Represents the complete count response for a query (including buckets and metadata).
  - Key fields (all optional unless enforced by other mixins):
    - Data: `query_string`, `granularity`, `start_time`, `end_time`, `total_tweet_count`, `file_path`, `label`, `created`, `creator`
    - Links: `contains_count_bucket`, `is_count_result_produced_by`, `generically_depends_on`, `is_concretized_by`

- `TweetCountBucket(GenericallyDependentContinuant, RDFEntity)`
  - Represents a single time bucket’s tweet count.
  - Key fields:
    - Data: `bucket_tweet_count`, `label`, `created`, `creator`
    - Links: `has_count_interval`, `is_count_bucket_of`, `generically_depends_on`, `is_concretized_by`

- `CountRecentTweets(Process, RDFEntity)`
  - Represents the counting process that produces a `TweetCountResultSet`.
  - Key fields:
    - Data: `label`, `created`, `creator`
    - Links: `produces_count_result`, `has_participant`, `occupies_temporal_region`, `occurs_in`, `realizes`, `concretizes`

- `CountInterval(TemporalRegion, RDFEntity)`
  - Represents the temporal interval for a count bucket.
  - Key fields:
    - Data: `bucket_start`, `bucket_end`, `label`, `created`, `creator`
    - Links: `is_count_interval_of`, `has_first_instant`, `has_last_instant`

### Methods (selected)

- `RDFEntity.set_namespace(namespace: str) -> None`
  - Sets the base namespace used when auto-generating `_uri`.

- `RDFEntity.set_query_executor(query_executor: Callable[[str], Iterable[object]] | None) -> None`
  - Sets the callable used by `from_iri` to execute SPARQL queries.

- `RDFEntity.from_iri(iri: str, query_executor: Callable | None = None, graph_name: str | None = None)`
  - Builds an instance by querying for triples `<iri> ?p ?o` (excluding `rdf:type`) and mapping predicates to model fields via `_property_uris`.
  - If `label` exists as a field but is missing from RDF results, it is derived from the IRI.

- `RDFEntity.rdf(subject_uri: str | None = None, visited: set[str] | None = None) -> rdflib.Graph`
  - Emits RDF triples for the instance:
    - Adds `rdf:type` of the class (`_class_uri`) and `owl:NamedIndividual`.
    - Adds `rdfs:label` when `label` is present.
    - Serializes object properties recursively when values are RDFEntity-like objects.

## Configuration/Dependencies
- Dependencies:
  - `pydantic` (`BaseModel`, `Field`, `ValidationError`)
  - `rdflib` (`Graph`, `Literal`, `Namespace`, `URIRef` and namespaces `RDF`, `RDFS`, `OWL`, `XSD`)
  - `naas_abi.ontologies.modules.ABIOntology` (ontology base classes like `Process`, `TemporalRegion`, etc.)
- Configuration points:
  - `RDFEntity._namespace` (default: `http://ontology.naas.ai/abi/`)
    - Configure via `RDFEntity.set_namespace(...)`.
  - `RDFEntity._query_executor`
    - Configure via `RDFEntity.set_query_executor(...)` or pass `query_executor=` to `from_iri`.

## Usage

### Create models and serialize to RDF
```python
import datetime
from naas_abi_marketplace.applications.x.ontologies.processes.XCountRecentTweetsProcess import (
    CountInterval, TweetCountBucket, TweetCountResultSet, CountRecentTweets
)

interval = CountInterval(
    bucket_start=datetime.datetime(2026, 1, 1, 0, 0, 0),
    bucket_end=datetime.datetime(2026, 1, 1, 1, 0, 0),
)

bucket = TweetCountBucket(
    bucket_tweet_count=42,
    has_count_interval=[interval],
)

result = TweetCountResultSet(
    query_string="from:demo",
    granularity="hour",
    total_tweet_count=42,
    contains_count_bucket=[bucket],
)

process = CountRecentTweets(
    label="Count recent tweets for from:demo",
    produces_count_result=[result],
)

g = process.rdf()
print(g.serialize(format="turtle").decode() if hasattr(bytes, "decode") else g.serialize(format="turtle"))
```

### Load an instance from an IRI via SPARQL
```python
from naas_abi_marketplace.applications.x.ontologies.processes.XCountRecentTweetsProcess import TweetCountResultSet

def executor(sparql: str):
    # Must return iterable rows with bindings for ?p and ?o
    # (implementation depends on your SPARQL client)
    raise NotImplementedError

TweetCountResultSet.set_query_executor(executor)
rs = TweetCountResultSet.from_iri("http://example.org/resource/resultset-1")
```

## Caveats
- `from_iri` requires a SPARQL executor; otherwise it raises `ValueError`.
- `from_iri` only maps predicates listed in the class’s `_property_uris`; unknown predicates are ignored.
- `rdf()` performs cycle detection using a `visited` set and will not recursively expand already-visited entities (but it will still emit linking triples).
