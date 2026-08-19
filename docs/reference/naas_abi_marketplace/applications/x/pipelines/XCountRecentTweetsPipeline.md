# XCountRecentTweetsPipeline

## What it is
- A pipeline that maps an **X (Twitter) v2 recent tweet count** “envelope” into an RDF knowledge graph.
- Produces ontology individuals for:
  - `CountRecentTweets` (process)
  - `TweetCountResultSet` (snapshot/result set)
  - `TweetCountBucket` + `CountInterval` (one per time bucket)
- Supports two input modes:
  - **Direct query**: calls `XIntegration.count_recent_tweets(...)`
  - **From file**: reads a previously saved JSON envelope from object storage

## Public API

### Classes

- `XCountRecentTweetsPipelineConfiguration(PipelineConfiguration)`
  - Holds runtime services and settings:
    - `x_integration: XIntegration`
    - `triple_store: TripleStoreService`
    - `object_storage: ObjectStorageService`
    - `graph_name: URIRef` (defaults to `http://ontology.naas.ai/graph/x_recent_posts_count`)
    - `datastore_path: str` (from `ABIModule` configuration)

- `XCountRecentTweetsPipelineParameters(PipelineParameters)`
  - Input parameters:
    - `query: str | None` — X v2 search query (required if `file_path` not provided)
    - `options: dict | None` — forwarded to `XIntegration.count_recent_tweets`; allowed keys:
      - `start_time`, `end_time`, `since_id`, `until_id`, `granularity`, `search_count_fields`, `max_pages`
    - `file_path: str | None` — JSON envelope path in object storage; when set, `options` is ignored
    - `persist: bool` — insert generated RDF into triple store (default `True`)
    - `partial: bool` — write buckets into a single overwriteable “partial slot” per query (default `False`)
    - `partial_end: str | None` — exclusive upper bound for partial windows (ISO-8601); used as bucket end when `partial=True`

- `XCountRecentTweetsPipeline(Pipeline)`
  - Core pipeline that builds an RDF graph and optionally persists it.

### Methods

- `XCountRecentTweetsPipeline.run(parameters: XCountRecentTweetsPipelineParameters) -> rdflib.Graph`
  - Loads or fetches a counts envelope, converts it to RDF individuals, and:
    - Skips already-ingested complete buckets using a label-based existence check in the target named graph.
    - For `partial=True`, clears and overwrites a per-query “partial” slot to avoid freezing partial counts.

- `XCountRecentTweetsPipeline.as_tools() -> list[langchain_core.tools.BaseTool]`
  - Exposes a LangChain `StructuredTool` named `x_add_recent_tweet_counts_to_graph` that returns Turtle serialization.

- `XCountRecentTweetsPipeline.as_api(...) -> None`
  - Declared but not implemented in the provided snippet (method body not present here).

## Configuration/Dependencies
- Requires services at construction time (via `XCountRecentTweetsPipelineConfiguration`):
  - `XIntegration` for calling the X counts endpoint (direct-query mode)
  - `TripleStoreService` for existence checks, inserts, and deletions (partial-slot clearing)
  - `ObjectStorageService` for reading JSON envelopes by `file_path`
- Uses a dedicated named graph by default:
  - `http://ontology.naas.ai/graph/x_recent_posts_count`
- Uses ontology/model classes from:
  - `naas_abi_marketplace.applications.x.ontologies.processes.XCountRecentTweetsProcess`
  - `naas_abi_marketplace.applications.x.ontologies.modules.XOntology`

## Usage

### Minimal example (direct query)
```python
from naas_abi_marketplace.applications.x.pipelines.XCountRecentTweetsPipeline import (
    XCountRecentTweetsPipeline,
    XCountRecentTweetsPipelineConfiguration,
    XCountRecentTweetsPipelineParameters,
)

# Provide concrete service instances from your runtime:
cfg = XCountRecentTweetsPipelineConfiguration(
    x_integration=x_integration,
    triple_store=triple_store,
    object_storage=object_storage,
)

pipeline = XCountRecentTweetsPipeline(cfg)

g = pipeline.run(
    XCountRecentTweetsPipelineParameters(
        query="(drone OR drones) lang:en -is:retweet",
        options={"granularity": "hour"},
        persist=False,
    )
)

print(g.serialize(format="turtle"))
```

### Using a saved envelope (object storage path)
```python
g = pipeline.run(
    XCountRecentTweetsPipelineParameters(
        file_path="x/counts/envelopes/my-envelope.json",
        persist=False,
    )
)
```

## Caveats
- `options` validation is strict: unknown keys raise `ValueError`.
- `partial=True` overwrites a single per-query “partial” slot and **removes prior partial triples** from the configured named graph.
- Complete (non-partial) buckets are **idempotent by label**: if an individual with the same `rdfs:label` already exists in the named graph, it is skipped.
- When `file_path` is used, the pipeline expects an envelope containing keys like:
  - `query`, `options`, `results` (with `results.data` buckets), `total_tweet_count`, `started_at`, `ended_at` (as described in parameter docstring).
