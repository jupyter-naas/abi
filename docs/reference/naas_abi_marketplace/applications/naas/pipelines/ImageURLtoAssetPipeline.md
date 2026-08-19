# ImageURLtoAssetPipeline

## What it is
A `Pipeline` that:
- Converts an external image URL into a Naas-hosted asset URL by downloading and uploading the image.
- Updates a triple store so `(subject_uri, predicate_uri)` points to the asset URL (as an RDF `Literal`) instead of the original URL.
- Can be triggered by ontology insert events (only for non-Naas URLs).

## Public API

### Classes

- `ImageURLtoAssetPipelineConfiguration(PipelineConfiguration)`
  - Required configuration:
    - `triple_store: ITripleStoreService`
    - `naas_integration_config: NaasIntegrationConfiguration`
    - `workspace_id: str`
    - `storage_name: str`
    - `data_store_path: str = "datastore/naas/assets"`

- `ImageURLtoAssetPipelineParameters(PipelineParameters)`
  - Input parameters:
    - `image_url: str` (validated with pattern `https?:\/\S+`)
    - `subject_uri: str`
    - `predicate_uri: str`

- `ImageURLtoAssetPipeline(Pipeline)`
  - Main pipeline implementation.

### Methods (ImageURLtoAssetPipeline)

- `__init__(configuration: ImageURLtoAssetPipelineConfiguration)`
  - Initializes `NaasIntegration` and `SPARQLUtils` using the configured triple store.

- `trigger(event: OntologyEvent, ontology_name: str, triple: tuple[Any, Any, Any]) -> Graph`
  - If `event` is `OntologyEvent.INSERT` and the object does **not** start with `https://api.naas.ai/`, runs the pipeline using the triple parts as parameters.
  - Otherwise returns an empty `rdflib.Graph`.

- `run(parameters: PipelineParameters) -> Graph`
  - Validates parameter type.
  - Loads the subject graph and checks existing `(subject, predicate, ?o)` objects.
  - If `image_url` is already present, returns the retrieved graph.
  - If `image_url` already starts with `https://api.naas.ai/`:
    - Inserts `(subject, predicate, Literal(image_url))` into graph `http://ontology.naas.ai/graph/default`.
    - Returns the inserted graph.
  - Otherwise:
    - Downloads the image bytes from `image_url`.
    - Uploads to Naas storage as a public asset.
    - Removes `(subject, predicate, Literal(original_url))` and inserts `(subject, predicate, Literal(asset_url))` in graph `http://ontology.naas.ai/graph/default`.
    - Returns the inserted graph.
  - On any exception, logs and returns an empty `Graph()`.

- `as_tools() -> list[BaseTool]`
  - Exposes a LangChain `StructuredTool` named `naas_image_url_to_asset` that calls `run()`.

- `as_api(...) -> None`
  - Signature exists, but no routes are registered (method body ends after tags defaulting).

## Configuration/Dependencies

- Uses:
  - `requests` for HTTP download.
  - `rdflib` (`Graph`, `URIRef`, `Literal`) for RDF handling.
  - `naas_abi_core`:
    - `Pipeline`, `PipelineConfiguration`, `PipelineParameters`
    - `SPARQLUtils`
    - `ITripleStoreService`, `OntologyEvent`
    - `logger`
  - `naas_abi_marketplace`:
    - `NaasIntegration`, `NaasIntegrationConfiguration`
  - `langchain_core.tools` (`StructuredTool`, `BaseTool`)

- Triple store graph name used for insert/remove:
  - `http://ontology.naas.ai/graph/default`

- Storage upload call:
  - `NaasIntegration.upload_asset(..., visibility="public", prefix=data_store_path, object_name=<generated>)`

## Usage

### Run the pipeline
```python
from naas_abi_marketplace.applications.naas.pipelines.ImageURLtoAssetPipeline import (
    ImageURLtoAssetPipeline,
    ImageURLtoAssetPipelineConfiguration,
    ImageURLtoAssetPipelineParameters,
)

config = ImageURLtoAssetPipelineConfiguration(
    triple_store=triple_store_service,  # ITripleStoreService implementation
    naas_integration_config=naas_integration_config,  # NaasIntegrationConfiguration
    workspace_id="workspace-id",
    storage_name="storage-name",
)

pipeline = ImageURLtoAssetPipeline(config)

g = pipeline.run(
    ImageURLtoAssetPipelineParameters(
        image_url="https://example.com/image.png",
        subject_uri="http://example.com/subject",
        predicate_uri="http://example.com/predicate",
    )
)
```

### Use as a LangChain tool
```python
tool = ImageURLtoAssetPipeline(config).as_tools()[0]
result = tool.invoke(
    {
        "image_url": "https://example.com/image.png",
        "subject_uri": "http://example.com/subject",
        "predicate_uri": "http://example.com/predicate",
    }
)
```

## Caveats
- `trigger()` only runs on `OntologyEvent.INSERT` and only when the object does **not** start with `https://api.naas.ai/`.
- `_download_image()` uses `requests.get(url)` with no timeout configured.
- Generated filenames always end with `.png` regardless of the source content type.
- The “already exists” check compares a `str` URL to RDF objects returned by `rdflib`; if existing objects are `Literal(...)`, this comparison may not match and can lead to duplicate inserts.
- `as_api()` does not register any FastAPI routes.
