# XSearchRecentTweetsPipeline

## What it is
- A pipeline that:
  - Calls `XIntegration.search_recent_tweets` (X/Twitter API v2 recent search) **or** loads a previously saved JSON envelope from object storage.
  - Transforms the response into an RDF `rdflib.Graph` using the X ontology/process models.
  - Optionally persists the generated triples into a configured triple store named graph.
- Separates:
  - **Matched tweets** (`results.data`) → `Tweet`
  - **Referenced/context tweets** (`results.includes.tweets` not in `data`) → `ReferencedTweet`

## Public API

### Classes

- `XSearchRecentTweetsPipelineConfiguration(PipelineConfiguration)`
  - Holds runtime dependencies and defaults.
  - Fields:
    - `x_integration: XIntegration` — used to call X API.
    - `triple_store: TripleStoreService` — used for label-based existence checks and insertion.
    - `object_storage: ObjectStorageService` — used to read saved search envelopes.
    - `graph_name: URIRef` — named graph target (default from `ABIModule` config).
    - `datastore_path: str` — default from `ABIModule` config.

- `XSearchRecentTweetsPipelineParameters(PipelineParameters)`
  - Inputs to `run()` / tool invocation.
  - Fields:
    - `query: str | None` — X v2 query string (required if `file_path` not provided).
    - `options: dict | None` — forwarded to `XIntegration.search_recent_tweets` (only recognized keys; ignored when `file_path` provided).
    - `file_path: str | None` — object-storage path to a JSON envelope previously saved by the integration.
    - `persist: bool` — insert into triple store when `True` (default `True`).
  - Validation:
    - Requires **either** `query` **or** `file_path`.

- `XSearchRecentTweetsPipeline(Pipeline)`
  - Main pipeline implementation.

### Methods (XSearchRecentTweetsPipeline)

- `run(parameters: XSearchRecentTweetsPipelineParameters) -> rdflib.Graph`
  - Executes the search (API call or file load), builds an RDF graph, and optionally persists it.

- `as_tools() -> list[langchain_core.tools.BaseTool]`
  - Exposes a `StructuredTool` named `x_add_recent_tweets_to_graph` that returns the produced graph serialized as Turtle.

- `as_api(...) -> None`
  - API exposure hook (present but not implemented in the provided snippet).

### Utilities (internal/static)

- `_params_hash(query: str, options: dict) -> str`
  - Deterministic 8-char md5 hash used to stabilize identifiers across reruns.

- `_join(value: Any) -> str | None`
  - Converts list values to comma-joined strings (wire-format style) for storing query fields.

## Configuration/Dependencies
- Requires services/integration instances:
  - `XIntegration` (must implement `search_recent_tweets(query, **options)` returning an envelope dict).
  - `TripleStoreService` (must support label existence checks via `XTweetGraphBuilder` and insertion via `.insert(graph, graph_name)`).
  - `ObjectStorageService` (used via `StorageUtils.get_json(dir_path, file_name)`).
- Uses ABI module configuration:
  - `ABIModule.get_instance().configuration.ontology_namespace`
  - `ABIModule.get_instance().configuration.graph_name`
  - `ABIModule.get_instance().configuration.datastore_path`

## Usage

### Run via API call (query + options)
```python
from naas_abi_marketplace.applications.x.pipelines.XSearchRecentTweetsPipeline import (
    XSearchRecentTweetsPipeline,
    XSearchRecentTweetsPipelineConfiguration,
    XSearchRecentTweetsPipelineParameters,
)

# These must be provided by your application wiring:
x_integration = ...
triple_store = ...
object_storage = ...

pipeline = XSearchRecentTweetsPipeline(
    XSearchRecentTweetsPipelineConfiguration(
        x_integration=x_integration,
        triple_store=triple_store,
        object_storage=object_storage,
    )
)

g = pipeline.run(
    XSearchRecentTweetsPipelineParameters(
        query="(from:TwitterDev OR from:TwitterAPI) has:media -is:retweet",
        options={"max_results": 10, "max_pages": 1, "sort_order": "recency"},
        persist=False,
    )
)

print(g.serialize(format="turtle"))
```

### Run from a saved envelope (object storage path)
```python
g = pipeline.run(
    XSearchRecentTweetsPipelineParameters(
        file_path="x/search_recent/2026-06-02/envelope.json",
        persist=True,
    )
)
```

### Use as a LangChain tool
```python
tool = pipeline.as_tools()[0]
ttl = tool.run({
    "query": "from:TwitterDev -is:retweet",
    "options": {"max_results": 5, "max_pages": 1},
    "persist": False,
})
print(ttl)
```

## Caveats
- `options` validation is strict:
  - Unknown keys raise `ValueError`.
  - Accepted keys: `start_time`, `end_time`, `since_id`, `until_id`, `max_results`, `sort_order`, `tweet_fields`, `expansions`, `media_fields`, `poll_fields`, `user_fields`, `place_fields`, `max_pages`.
- When `file_path` is provided:
  - The pipeline reads `query/options/results/started_at/ended_at` from the file envelope.
  - If the JSON cannot be read, it raises `FileNotFoundError` (empty `{}` from storage is treated as failure).
- Matched vs referenced tweets:
  - `includes.tweets` may contain tweets that also appear in `data`; only ids **absent** from `data` are treated as referenced/context tweets.
- Persistence is controlled only by `persist`; when `False`, the triple store is not written.
