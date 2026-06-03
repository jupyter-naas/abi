# Search Service — AGENTS.md

> Scope: `libs/naas-abi-core/naas_abi_core/services/search/`. Canonical reference for agents.

## Purpose

Federated multi-source search facade. Holds a registry of `ISearchSource`s (graph, object storage, web, vector, …), federates one query across them in parallel, and streams `SearchEvent`s back so callers can render hits as each source produces them rather than waiting on the slowest.

Indexable sources maintain their own indexes by subscribing to upstream domain events (`TriplesInserted`, object-storage events, …). The `SearchService` itself never indexes — keeps the dependency arrow clean: `search → events → bus`; nothing imports `search`.

## Files

| File | Role |
|---|---|
| `SearchPorts.py` | `ISearchSource`, `ISearchService`, `Document`, `SearchHit`, `SearchEvent` types, exceptions |
| `SearchService.py` | Federator: source registry, streaming `search()`, per-source timeout + error isolation, TTL cache, `reindex()` |
| `SearchFactory.py` | Pre-wired service builders |
| `adaptors/secondary/GraphSearchSource.py` | Triple-store-backed source (SPARQL `CONTAINS`; vector path TODO) |
| `adaptors/secondary/ObjectStorageSearchSource.py` | File search stub (text extraction + vector index TODO) |
| `adaptors/secondary/DuckDuckGoSearchSource.py` | Live web search stub (HTTP TODO) |
| `ontologies/modules/SearchEventOntology.py` | `SearchIndexFailed`, `DocumentIndexed`, `DocumentRemoved`, `IndexRebuilt` |

## Result shape

```python
SearchHit:
    id: str            # unique within source; (source, id) is the global dedup key
    source: str        # "graph" | "object_storage" | "duckduckgo" | ...
    kind: str          # "entity" | "document" | "webpage" | ...
    title: str         # rdfs:label / filename / page title
    snippet: str       # matched literal / file excerpt / DDG abstract
    score: float       # PER-SOURCE — do not compare across sources
    url: str | None    # where the frontend navigates to open it
    highlights: list[str]
    metadata: dict     # source-specific extras (graph, mime, domain, ...)
```

`metadata` is intentionally open: the frontend renders title/snippet/url by default and reaches into `metadata` only when it recognizes the source. `kind` lets the UI pick an icon/layout without hardcoding source names.

## Streaming

`SearchService.search(...)` yields a sequence:

```
SearchStarted   → once
SourceStarted   → once per source
Hit             → 0..N per source, as they arrive
SourceFinished  → once per source (count, duration_ms)
SourceError     → instead of Finished if the source failed
SearchFinished  → once
```

Each source runs in its own thread and feeds a shared queue; one slow/failed source does NOT block the others. Per-source timeout bounds the "unreachable" case without truncating slow-but-streaming sources.

Caching is per-source TTL (default 30s) keyed by `(source, query, filters, limit)`. Short TTL because results must reflect recent index updates within seconds.

## Indexing path

Indexable sources implement `index`, `remove`, `reindex` and typically subscribe to upstream events:

- A `GraphSearchSource` with a vector backend subscribes to `TripleStoreService.subscribe((None, None, None), cb, "*")` for per-triple updates AND to `EventService` for `TriplesInserted` / `GraphDropped` / `GraphCleared` (graph-scope ops + monitoring cross-checks).
- An `ObjectStorageSearchSource` subscribes to object-storage created/deleted events.

On failure, the source publishes `SearchIndexFailed` via `EventService.publish` and moves on — does NOT retry. Retry, if needed later, is a separate consumer.

**Every indexable source MUST implement `reindex()`.** Events only cover mutations after subscribe-time; without a reindex path the index drifts permanently on every restart-before-subscribe, schema change, or adapter swap.

## Events (monitoring)

Published through `EventService` like every other domain event — durable in the SQLite log, broadcast on the bus.

| Event | When | Purpose |
|---|---|---|
| `SearchIndexFailed` | Index/remove/reindex op raised | Failure dashboards, alerters |
| `DocumentIndexed` | One document written | Pairs with `SearchIndexFailed` for failure-rate metrics |
| `DocumentRemoved` | One document removed | Audit |
| `IndexRebuilt` | `reindex()` completed | Heartbeat — "recovery path actually works" |

Search owns these classes (vs. the upstream service) because the failure semantics — "I tried to index this and could not" — belong to the consumer that did the work. The upstream event was fine.

## Factory

```python
SearchFactory.SearchServiceWithGraph(triple_store)
SearchFactory.SearchServiceFederated(
    triple_store=..., object_storage=..., include_duckduckgo=False,
)
```

## Adding a new source

1. Subclass `ISearchSource` in `adaptors/secondary/<Name>SearchSource.py`.
2. Implement `name` and `search(query, *, filters, limit) -> Iterator[SearchHit]`. **Yield lazily** so the federator can start streaming before you've fetched everything.
3. If the source maintains an index, override `supports_indexing() -> True` and implement `index` / `remove` / `reindex`. Subscribe to whichever upstream events keep the index current — in the source's own constructor / setup, never by changing the upstream service.
4. On indexing failure, publish `SearchIndexFailed` and continue. Do not retry inline.
5. Add a factory builder if the source has a typical zero-config setup.
6. Run the generic source contract tests (see `tests/`).
