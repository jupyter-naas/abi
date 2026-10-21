# AddPowerPointPresentationPipeline

## What it is
A pipeline that loads a PowerPoint presentation (from a local `src...` path or object storage), extracts core document properties plus slides/shapes, builds an RDF graph (ABI/PPT namespaces), and inserts the resulting triples into a configured triple store—unless an equivalent presentation already exists (deduplicated via a hash signature).

## Public API

- **`AddPowerPointPresentationPipelineConfiguration` (dataclass, `PipelineConfiguration`)**
  - Purpose: Provides dependencies for the pipeline.
  - Fields:
    - `powerpoint_configuration: PowerPointIntegrationConfiguration`
    - `triple_store: ITripleStoreService`

- **`AddPowerPointPresentationPipelineParameters` (`PipelineParameters`)**
  - Purpose: Validated inputs to `run()`.
  - Fields:
    - `presentation_name: str` — Human name used in signature and label.
    - `storage_path: str` — If starts with `"src"` loads locally; otherwise loaded from object storage.
    - `download_url: str | None` — Optional URL stored as a literal.
    - `template_uri: str | None` — Optional URI (validated against `URI_REGEX`).

- **`AddPowerPointPresentationPipeline` (`Pipeline`)**
  - **`run(parameters: PipelineParameters) -> rdflib.Graph`**
    - Loads the `.pptx`:
      - `storage_path.startswith("src")`: uses `PowerPointIntegration.create_presentation(storage_path)`
      - else: uses `StorageUtils.get_powerpoint_presentation(dir, filename)` and `pptx.Presentation(...)`
    - Reads `presentation.core_properties` (author/created/modified/last_modified_by) and builds a signature:
      - `"_".join([presentation_name, ...available core properties...])`
    - Deduplicates by hashing the signature and querying `SPARQLUtils.get_identifier(...)`.
      - If found: returns `SPARQLUtils.get_subject_graph(existing_uri, depth=2)` and does not insert.
    - Otherwise builds triples for:
      - Presentation individual (label, unique_id hash, storage_path, optional core properties, optional download_url, optional template links)
      - Slide individuals with `ppt:slide_number`
      - Shape individuals with id/type/text/alt-text and geometry/rotation, linked to slides
    - Inserts into triple store with graph name `http://ontology.naas.ai/graph/default` if the graph is non-empty.
  - **`as_tools() -> list[BaseTool]`**
    - Exposes a LangChain `StructuredTool` named `add_powerpoint_presentation` that calls `run()` with `AddPowerPointPresentationPipelineParameters`.
  - **`as_api(...) -> None`**
    - Present but does not register any routes (method ends without implementation).

## Configuration/Dependencies

- **Requires**
  - `PowerPointIntegrationConfiguration` (used to initialize `PowerPointIntegration`)
  - `ITripleStoreService` (used to `insert()` RDF triples)

- **Uses runtime services (via `ABIModule.get_instance().engine.services`)**
  - Triple store service (wrapped by `SPARQLUtils`)
  - Object storage service (wrapped by `StorageUtils`)

- **Key libraries**
  - `python-pptx` (`pptx.Presentation`)
  - `rdflib`
  - `langchain_core.tools` (tool wrapper)

## Usage

```python
from naas_abi_marketplace.applications.powerpoint.pipelines.AddPowerPointPresentationPipeline import (
    AddPowerPointPresentationPipeline,
    AddPowerPointPresentationPipelineConfiguration,
    AddPowerPointPresentationPipelineParameters,
)
from naas_abi_marketplace.applications.powerpoint.integrations.PowerPointIntegration import (
    PowerPointIntegrationConfiguration,
)

ppt_cfg = PowerPointIntegrationConfiguration(...)  # provide integration config
triple_store = ...  # provide an ITripleStoreService implementation

pipeline = AddPowerPointPresentationPipeline(
    AddPowerPointPresentationPipelineConfiguration(
        powerpoint_configuration=ppt_cfg,
        triple_store=triple_store,
    )
)

g = pipeline.run(
    AddPowerPointPresentationPipelineParameters(
        presentation_name="Q2 Review",
        storage_path="src/presentations/q2_review.pptx",  # or object-storage path
        download_url=None,
        template_uri=None,
    )
)

print(len(g))
```

## Caveats

- If `presentation.core_properties` access fails, the pipeline logs an error and returns an **empty** `rdflib.Graph` (no insert occurs).
- Deduplication is based on a hash of `presentation_name` plus any available core properties; different files with identical extracted properties can be treated as the same presentation.
- `as_api()` is effectively a no-op (no FastAPI routes are created).
