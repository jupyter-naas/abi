# ImageURLtoAssetPipeline

## What it is
A pipeline that converts an external image URL into a Naas-hosted asset URL and updates an RDF triple store so the subject/predicate points to the asset URL instead of the original URL.

It can also be triggered from ontology insert events.

## Public API

### Classes

- `ImageURLtoAssetPipelineConfiguration(PipelineConfiguration)`
  - Holds required services and settings:
    - `triple_store: ITripleStoreService`
    - `naas_integration_config: NaasIntegrationConfiguration`
    - `workspace_id: str`
    - `storage_name: str`
    - `data_store_path: str = "datastore/naas/assets"`

- `ImageURLtoAssetPipelineParameters(PipelineParameters)`
  - Input parameters:
    - `image_url: str` (must match `https?:\/\S+`)
    - `subject_uri: str`
    - `predicate_uri: str`

- `ImageURLtoAssetPipeline(Pipeline)`
  - Main pipeline implementation.

### Methods (ImageURLtoAssetPipeline)

- `__init__(configuration: ImageURLtoAssetPipelineConfiguration)`
  - Initializes triple-store SPARQL utilities and Naas integration.

- `trigger(event: OntologyEvent, ontology_name: str, triple: tuple[Any, Any, Any]) -> Graph`
  - On `OntologyEvent.INSERT`, runs the pipeline when the object is **not** already a Naas asset URL (`https://api.naas.ai/...`).
  - Otherwise returns an empty `rdflib.Graph`.

- `run(parameters: PipelineParameters) -> Graph`
  - Validates `parameters` type.
  - Reads existing triples for `subject_uri` and checks whether the URL is already present.
  - If `image_url` is already a Naas asset URL (`https://api.naas.ai/...`), inserts it as a literal for `(subject, predicate, image_url)` into graph `http://ontology.naas.ai/graph/default`.
  - Otherwise:
    - Downloads the image.
    - Uploads it to Naas storage as a public asset.
    - Removes `(subject, predicate, old_url)` and inserts `(subject, predicate, asset_url)` in the triple store.
  - Returns the inserted graph (or empty graph on error).

- `as_tools() -> list[BaseTool]`
  - Exposes the pipeline as a LangChain `StructuredTool` named `naas_image_url_to_asset`.

- `as_api(...) -> None`
  - Present but does nothing (returns `None`).

## Configuration/Dependencies

### External dependencies
- `requests` for downloading images.
- `rdflib` for RDF graphs (`Graph`, `URIRef`, `Literal`).
- `naas_abi_core`:
  - `Pipeline`, `PipelineConfiguration`, `PipelineParameters`
  - `logger`
  - `SPARQLUtils`
  - `ITripleStoreService`, `OntologyEvent`
- `naas_abi_marketplace`:
  - `NaasIntegration`, `NaasIntegrationConfiguration`
- `langchain_core.tools` for tool wrapping.

### Triple store graph name
- Inserts/removals are performed in: `http://ontology.naas.ai/graph/default`

### Storage upload
- Uses `NaasIntegration.upload_asset(...)` with:
  - `visibility="public"`
  - `prefix=config.data_store_path`
  - `object_name=<generated file name>`

## Usage

### Run directly
```python
from naas_abi_marketplace.applications.naas.pipelines.ImageURLtoAssetPipeline import (
    ImageURLtoAssetPipeline,
    ImageURLtoAssetPipelineConfiguration,
    ImageURLtoAssetPipelineParameters,
)

# You must provide concrete implementations/config values:
config = ImageURLtoAssetPipelineConfiguration(
    triple_store=triple_store_service,  # ITripleStoreService
    naas_integration_config=naas_integration_config,  # NaasIntegrationConfiguration
    workspace_id="your-workspace-id",
    storage_name="your-storage-name",
)

pipeline = ImageURLtoAssetPipeline(config)

result_graph = pipeline.run(
    ImageURLtoAssetPipelineParameters(
        image_url="https://example.com/image.png",
        subject_uri="http://example.com/subject",
        predicate_uri="http://example.com/predicate",
    )
)
```

### As a LangChain tool
```python
tools = pipeline.as_tools()
tool = tools[0]
# tool expects kwargs matching ImageURLtoAssetPipelineParameters
tool.invoke({
    "image_url": "https://example.com/image.png",
    "subject_uri": "http://example.com/subject",
    "predicate_uri": "http://example.com/predicate",
})
```

## Caveats
- Only triggers on `OntologyEvent.INSERT` and only when the object does **not** start with `https://api.naas.ai/`.
- Image download uses `requests.get(url)` without timeouts.
- File naming always uses `.png` extension regardless of source content type.
- The “already exists” check compares `parameters.image_url` (a `str`) against RDF objects; depending on how values are stored (e.g., `Literal`), this may not detect duplicates reliably.
- `as_api()` is a no-op (does not register routes).
