# AddPowerPointPresentationPipeline

## What it is
A `Pipeline` that reads a PowerPoint presentation (from local `src...` path or object storage), extracts core document properties plus all slides/shapes, builds an RDF graph using the ABI/PPT namespaces, and inserts the triples into a configured triple store (unless the presentation already exists).

## Public API
- **`AddPowerPointPresentationPipelineConfiguration` (dataclass)**
  - Purpose: Configuration container for the pipeline.
  - Fields:
    - `powerpoint_configuration: PowerPointIntegrationConfiguration`
    - `triple_store: ITripleStoreService`

- **`AddPowerPointPresentationPipelineParameters` (PipelineParameters)**
  - Purpose: Validated inputs for `run()`.
  - Fields:
    - `presentation_name: str` — Name of the presentation.
    - `storage_path: str` — Storage path for the presentation.
    - `download_url: Optional[str]` — Optional download URL.
    - `template_uri: Optional[str]` — Optional template URI (must match `URI_REGEX`).

- **`AddPowerPointPresentationPipeline` (Pipeline)**
  - **`run(parameters) -> rdflib.Graph`**
    - Purpose: Build and insert RDF triples for a presentation, its slides, and shapes.
    - Behavior:
      - Loads the presentation:
        - If `storage_path` starts with `"src"`: uses `PowerPointIntegration.create_presentation(storage_path)`.
        - Else: fetches bytes via `StorageUtils.get_powerpoint_presentation(dir, filename)` and loads with `pptx.Presentation(...)`.
      - Extracts core properties (`author`, `created`, `modified`, `last_modified_by`) and combines them with `presentation_name` to form a signature string.
      - Hashes the signature (`create_hash_from_string`) and checks for existing entity via `SPARQLUtils.get_identifier(...)`.
        - If found: returns `SPARQLUtils.get_subject_graph(existing_uri, depth=2)` and does not insert.
      - Otherwise: creates new URIs and adds triples for:
        - Presentation metadata (label, unique_id, storage_path, optional download_url, optional template links).
        - Slides (`slide_number`) and shapes (id/type/text/alt-text/position/size/rotation), plus relationships.
      - Inserts the graph into the triple store under graph name `http://ontology.naas.ai/graph/default` when non-empty.
      - Returns the built `rdflib.Graph` (or an empty `Graph()` if core property extraction fails).
  - **`as_tools() -> list[BaseTool]`**
    - Purpose: Exposes a LangChain `StructuredTool` named `add_powerpoint_presentation` that calls `run()` with `AddPowerPointPresentationPipelineParameters`.
  - **`as_api(...) -> None`**
    - Purpose: Present but not implemented; always returns `None` and does not register routes.

## Configuration/Dependencies
- Requires:
  - `PowerPointIntegrationConfiguration` (passed into pipeline configuration).
  - `ITripleStoreService` (used for `insert()`).
- Uses runtime services from `ABIModule.get_instance().engine.services`:
  - Triple store (wrapped via `SPARQLUtils`).
  - Object storage (wrapped via `StorageUtils`).
- External libraries:
  - `python-pptx` (`pptx.Presentation`)
  - `rdflib`
  - `fastapi` (only for typing in `as_api`)
  - `langchain_core` tools

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

# Provide concrete instances appropriate for your environment:
ppt_cfg = PowerPointIntegrationConfiguration(...)   # integration-specific
triple_store = ...  # must implement ITripleStoreService

pipeline = AddPowerPointPresentationPipeline(
    AddPowerPointPresentationPipelineConfiguration(
        powerpoint_configuration=ppt_cfg,
        triple_store=triple_store,
    )
)

g = pipeline.run(
    AddPowerPointPresentationPipelineParameters(
        presentation_name="Quarterly Review",
        storage_path="src/presentations/review.pptx",  # or a non-src path to load from object storage
        download_url="https://example.com/review.pptx",
        template_uri="http://ontology.naas.ai/abi/some-template-uri",
    )
)

print(len(g))  # number of triples produced/returned
```

## Caveats
- If extracting `presentation.core_properties` fails for any reason, the pipeline logs an error and returns an empty RDF `Graph` without inserting anything.
- `as_api()` is a no-op; it does not expose a FastAPI endpoint.
- Deduplication is based on a hash of `presentation_name` plus available core properties; different files with identical properties may be treated as the same presentation.
