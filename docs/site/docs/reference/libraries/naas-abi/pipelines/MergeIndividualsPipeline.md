# MergeIndividualsPipeline

## What it is
A `Pipeline` that merges two RDF individuals in a triplestore by:
- Copying selected triples from `uri_to_merge` to `uri_to_keep` (avoiding duplicates).
- Rewriting references where `uri_to_merge` appears as an object to instead point to `uri_to_keep`.
- Removing all original triples involving `uri_to_merge` (as subject or object).
- Returning the resulting subject graph for `uri_to_keep`.

It also writes the inserted/removed triples to Turtle files under a configured datastore path.

## Public API

### Classes

- `MergeIndividualsPipelineConfiguration(PipelineConfiguration)`
  - Fields:
    - `triple_store: ITripleStoreService` - triplestore port used for querying/inserting/removing.
    - `datastore_path: str = "datastore/ontology/merged_individual"` - folder used to store `.ttl` audit files.

- `MergeIndividualsPipelineParameters(PipelineParameters)`
  - Fields (validated against `URI_REGEX`):
    - `uri_to_keep: str` - URI that remains.
    - `uri_to_merge: str` - URI that is merged into `uri_to_keep` and then removed.

- `MergeIndividualsPipeline(Pipeline)`
  - `get_all_triples_for_uri(uri: str)`
    - Queries the triplestore for all triples where `uri` appears as subject or object.
  - `run(parameters: PipelineParameters) -> rdflib.Graph`
    - Executes the merge and returns the subject graph for `uri_to_keep`.
  - `as_tools() -> list[langchain_core.tools.BaseTool]`
    - Exposes the pipeline as a LangChain `StructuredTool` named `merge_individuals`.
  - `as_api(...) -> None`
    - Present but does not register any routes (returns `None`).

## Configuration/Dependencies
- Requires an `ITripleStoreService` implementation provided via `MergeIndividualsPipelineConfiguration.triple_store`.
- Uses `ABIModule.get_instance().engine.services.triple_store` and `.object_storage` internally to initialize:
  - `SPARQLUtils` (for `get_subject_graph`).
  - `StorageUtils` (to save inserted/removed graphs as Turtle files).
- RDF processing uses `rdflib` (`Graph`, `URIRef`, `Literal`, and vocabularies like `RDFS`, `SKOS`).
- Special handling:
  - `rdfs:label` and `abi:universal_name` from the merged URI become `skos:altLabel` on the kept URI.

## Usage

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

triple_store_service = ABIModule.get_instance().engine.services.triple_store

pipeline = MergeIndividualsPipeline(
    MergeIndividualsPipelineConfiguration(triple_store=triple_store_service)
)

result_graph = pipeline.run(
    MergeIndividualsPipelineParameters(
        uri_to_keep="http://ontology.naas.ai/abi/<kept-id>",
        uri_to_merge="http://ontology.naas.ai/abi/<merged-id>",
    )
)

print(result_graph.serialize(format="turtle"))
```

## Caveats
- `run()` requires `MergeIndividualsPipelineParameters`; any other `PipelineParameters` type raises `ValueError`.
- The pipeline removes **all** triples where `uri_to_merge` is subject or object (after inserting replacements where applicable).
- Only triples where the merged URI is the **subject** are considered for copying to the kept URI; duplicates (same predicate/object) are skipped.
- `as_api()` is a no-op (no HTTP endpoints are exposed by this class).
