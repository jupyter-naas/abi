# MergeIndividualsPipeline

## What it is
A `Pipeline` that merges two RDF individuals in a triplestore by:
- Copying non-duplicate triples from `uri_to_merge` to `uri_to_keep` (with special handling for labels)
- Rewriting references to `uri_to_merge` so they point to `uri_to_keep`
- Removing all triples involving `uri_to_merge` (both as subject and object)
- Returning the resulting subject graph for `uri_to_keep`

## Public API

### Classes

- `MergeIndividualsPipelineConfiguration(PipelineConfiguration)`
  - **Purpose:** Provide dependencies and output settings.
  - **Fields:**
    - `triple_store: ITripleStoreService` — triplestore used for query/insert/remove
    - `datastore_path: str = "datastore/ontology/merged_individual"` — where TTL snapshots are saved

- `MergeIndividualsPipelineParameters(PipelineParameters)`
  - **Purpose:** Input parameters for the merge.
  - **Fields:**
    - `uri_to_keep: str` — URI that remains (validated by `URI_REGEX`)
    - `uri_to_merge: str` — URI to merge into `uri_to_keep` then remove (validated by `URI_REGEX`)

- `MergeIndividualsPipeline(Pipeline)`
  - **Purpose:** Executes the merge in the triplestore.

### Methods (MergeIndividualsPipeline)

- `get_all_triples_for_uri(uri: str)`
  - **Purpose:** SPARQL query for all triples where `uri` appears as subject **or** object.
  - **Returns:** triplestore query result rows of `(?s, ?p, ?o)`.

- `run(parameters: PipelineParameters) -> rdflib.Graph`
  - **Purpose:** Performs the merge transaction:
    - Inserts:
      - For triples where `uri_to_merge` is **subject**:
        - Copies predicates/objects to `uri_to_keep` **unless** predicate is `rdfs:label` or `abi:universal_name`
        - Skips if `(uri_to_keep, p, o)` already exists
        - Preserves `Literal` datatype and language tags
      - For `rdfs:label` and `abi:universal_name` on `uri_to_merge`:
        - Adds them to `uri_to_keep` as `skos:altLabel`
      - For triples where `uri_to_merge` is **object**:
        - Rewrites to use `uri_to_keep` as object
        - Skips if `(s, p, uri_to_keep)` already exists
    - Removes:
      - Removes **all** triples where `uri_to_merge` was subject or object
    - Persists TTL snapshots via `StorageUtils.save_triples(...)`
    - Applies changes using `triple_store.insert(...)` and `triple_store.remove(...)`
  - **Returns:** `SPARQLUtils.get_subject_graph(uri_to_keep)`

- `as_tools() -> list[langchain_core.tools.BaseTool]`
  - **Purpose:** Exposes the pipeline as a LangChain `StructuredTool` named `merge_individuals`.

- `as_api(...) -> None`
  - **Purpose:** API exposure hook; currently does nothing and returns `None`.

## Configuration/Dependencies
- Requires an `ITripleStoreService` implementation with:
  - `query(sparql: str)`
  - `insert(graph: rdflib.Graph)`
  - `remove(graph: rdflib.Graph)`
- Uses `ABIModule.get_instance().engine.services` for:
  - `triple_store` (indirectly via `SPARQLUtils`)
  - `object_storage` (via `StorageUtils`)
- Writes snapshot TTL files under `MergeIndividualsPipelineConfiguration.datastore_path`.

## Usage

### Minimal example (script-style)
```python
from naas_abi import ABIModule
from naas_abi_core.engine.Engine import Engine
from naas_abi.pipelines.MergeIndividualsPipeline import (
    MergeIndividualsPipeline,
    MergeIndividualsPipelineConfiguration,
    MergeIndividualsPipelineParameters,
)

engine = Engine()
engine.load(module_names=["naas_abi"])

triple_store = ABIModule.get_instance().engine.services.triple_store

pipeline = MergeIndividualsPipeline(
    MergeIndividualsPipelineConfiguration(triple_store=triple_store)
)

result_graph = pipeline.run(
    MergeIndividualsPipelineParameters(
        uri_to_keep="http://ontology.naas.ai/abi/<keep-id>",
        uri_to_merge="http://ontology.naas.ai/abi/<merge-id>",
    )
)

print(result_graph.serialize(format="turtle"))
```

### As a LangChain tool
```python
tool = pipeline.as_tools()[0]
tool.invoke({
    "uri_to_keep": "http://ontology.naas.ai/abi/<keep-id>",
    "uri_to_merge": "http://ontology.naas.ai/abi/<merge-id>",
})
```

## Caveats
- `run()` requires `MergeIndividualsPipelineParameters`; otherwise it raises `ValueError`.
- All triples involving `uri_to_merge` are removed (both where it is subject and where it is object).
- `rdfs:label` and `abi:universal_name` from `uri_to_merge` are not copied as-is; they are added as `skos:altLabel` on `uri_to_keep`.
- Duplicate checks are performed against the pre-merge snapshot of `uri_to_keep` triples (i.e., duplicates created by earlier inserts in the same run are not re-checked against `graph_insert`).
