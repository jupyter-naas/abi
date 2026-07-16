# Locations Workflows

## LocationsWorkflow

Embeds every `abi:Country`/`abi:State`/`abi:Region`/`abi:City`/`abi:PostalCode` individual from the triple store into a single vector store collection, and exposes semantic search over it -- so a free-text location description can be matched to the closest indexed location by similarity rather than exact string/SPARQL matching.

### How it works

1. **Fetch** -- runs a SPARQL query against `triple_store`, walking the `bfo:BFO_0000171` ("located in") chain up to 4 levels (covers `PostalCode -> City -> Region -> State -> Country`) to build each individual's full hierarchy of labels, plus its `country_code`/`state_code`/`region_code` and lat/lon where present.
2. **Build text** -- joins the individual's own label with its parents' labels, e.g. `"Paris, Paris 01, Paris, Île-de-France, FR"` for a `PostalCode`, or just `"FR"` for a bare `Country`.
3. **Embed & store** -- embeds each text with `OpenAIEmbeddings` (`text-embedding-3-small`, 1536 dims by default) and calls `vector_store.add_documents(...)`, using the individual's **URI as the vector ID** (so a search hit maps straight back to the graph node) and storing the built text plus all fetched fields as metadata.

### Configuration

- `triple_store`, `vector_store`, `secret`: live services (see [`domains/locations/__init__.py`](../__init__.py) `ABIModule` -- `Secret`, `TripleStoreService`, `VectorStoreService` are enabled there).
- `collection_name` (default `"locations"`), `model_id` (default `"text-embedding-3-small"`), `dimension` (default `1536`), `batch_size` (default `100`).
- `secret.get("OPENAI_API_KEY")` is fetched at call time -- no API key is stored in configuration.

### Usage

```python
workflow = LocationsWorkflow(LocationsWorkflowConfiguration(
    triple_store=engine.services.triple_store,
    vector_store=engine.services.vector_store,
    secret=engine.services.secret,
))

workflow.run(LocationsWorkflowParameters())            # -> {"collection_name": "locations", "count": N}
workflow.search(LocationsSearchParameters(query="Paris France", k=5))  # -> closest matches, most similar first
```

Exposed as two tools via `as_tools()`, wired into `LocationsAgent`: `vectorize_locations` and `search_locations`.

### Note

This workflow only reads what is already in the triple store -- it does not itself insert `LocationsPipeline` output there. Run `LocationsPipeline` and persist its returned graph (`triple_store.insert(graph, graph_name=...)`) before calling `vectorize_locations`.
