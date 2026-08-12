# MergeIndividualsPipeline

## What it is
A pipeline that merges RDF individuals in a triplestore by transferring triples from one URI (`uri_to_merge`) into another (`uri_to_keep`), then removing the original triples associated with `uri_to_merge`. It also persists insert/remove graphs to object storage as Turtle files.

## Public API

- `MergeIndividualsPipelineConfiguration(PipelineConfiguration)`
  - **Fields**
    - `triple_store: ITripleStoreService` — triplestore backend used for `query/insert/remove`.
    - `object_storage: IObjectStorageDomain` — storage backend used to save TTL outputs.
    - `datastore_path: str = "datastore/ontology/merged_individual"` — output directory prefix used by storage.

- `MergeIndividualsPipelineParameters(PipelineParameters)`
  - **Fields**
    - `merge_pairs: list[tuple[str, str]]` — list of `(uri_to_keep, uri_to_merge)` pairs.
  - **Validation**
    - Must be non-empty.
    - Each element must be a tuple of exactly 2 strings.
    - Each URI must match `URI_REGEX`.
    - URIs in a pair must be different.

- `MergeIndividualsPipeline(Pipeline)`
  - `run(parameters: PipelineParameters) -> rdflib.Graph`
    - Executes one or more merge operations from `MergeIndividualsPipelineParameters.merge_pairs`.
    - Returns a combined `rdflib.Graph` containing the resulting subject graphs for each `uri_to_keep`.
  - `as_tools() -> list[langchain_core.tools.BaseTool]`
    - Exposes a LangChain `StructuredTool` named `merge_individuals` using `MergeIndividualsPipelineParameters` as schema.
  - `as_api(...) -> None`
    - Present but does not register any routes (returns `None`).
  - `get_all_triples_for_uri(uri: str)`
    - Queries all triples where `uri` appears as subject or object.

## Configuration/Dependencies

- Requires implementations of:
  - `ITripleStoreService` (used for `query`, `insert`, `remove`)
  - `IObjectStorageDomain` (used via `StorageUtils.save_triples`)
- Uses:
  - `SPARQLUtils.get_subject_graph(uri)` to return the final merged graph per kept URI.
  - `rdflib` for graph construction and serialization.
- Output files written (per merge pair) under `datastore_path`:
  - `"{uri_to_keep_label}_{last_segment}_merged.ttl"` — inserted triples
  - `"{uri_to_merge_label}_{last_segment}_removed.ttl"` — removed triples

## Usage

```python
from naas_abi_core.engine.Engine import Engine
from naas_abi import ABIModule

from naas_abi_marketplace.domains.ontology_engineer.pipelines.MergeIndividualsPipeline import (
    MergeIndividualsPipeline,
    MergeIndividualsPipelineConfiguration,
    MergeIndividualsPipelineParameters,
)

# Boot engine/services (project-specific)
engine = Engine()
engine.load(module_names=["naas_abi_marketplace.domains.ontology_engineer"])
triple_store = ABIModule.get_instance().engine.services.triple_store
object_storage = ABIModule.get_instance().engine.services.object_storage

config = MergeIndividualsPipelineConfiguration(
    triple_store=triple_store,
    object_storage=object_storage,
)

pipeline = MergeIndividualsPipeline(config)

result = pipeline.run(
    MergeIndividualsPipelineParameters(
        merge_pairs=[
            ("http://ontology.naas.ai/abi/KEEP_URI", "http://ontology.naas.ai/abi/MERGE_URI"),
        ]
    )
)

print(len(result))
```

## Caveats

- Merges are done by:
  - Copying non-duplicate triples where `uri_to_merge` is the **subject** into `uri_to_keep` (excluding `rdfs:label` and `abi:universal_name`).
  - Converting `rdfs:label` and `abi:universal_name` from `uri_to_merge` into `skos:altLabel` on `uri_to_keep`.
  - Rewriting triples where `uri_to_merge` is the **object** to point to `uri_to_keep` (if not already present).
  - Removing **all** triples returned for `uri_to_merge` (both subject and object occurrences).
- Output filenames include labels; if labels are missing or contain filesystem-hostile characters, saving may fail depending on the storage implementation.
