# LinkedInExportConnectionsPipeline

## What it is
- A pipeline that imports **LinkedIn Connections** from a LinkedIn export CSV (default `Connections.csv`) into an RDF graph and inserts it into a configured triple store.
- It also runs `LinkedInExportProfilePipeline` first to ensure the “initial person” (the profile owner) exists and can be linked to connection events.

## Public API

### Classes

- `LinkedInExportConnectionsPipelineConfiguration(PipelineConfiguration)`
  - Holds dependencies and runtime settings:
    - `triple_store: ITripleStoreService`
    - `linkedin_export_configuration: LinkedInExportIntegrationConfiguration`
    - `linkedin_export_profile_pipeline_configuration: LinkedInExportProfilePipelineConfiguration`
    - `limit: int | None = None` (optional row limit)
    - `num_workers: int = 20` (thread pool size)

- `LinkedInExportConnectionsPipelineParameters(PipelineParameters)`
  - Runtime parameters:
    - `linkedin_public_url: str` (LinkedIn public URL for the profile owner)
    - `file_name: str = "Connections.csv"` (CSV file from the export)

- `LinkedInExportConnectionsPipeline(Pipeline, BasePipeline)`
  - `run(parameters: PipelineParameters) -> rdflib.Graph`
    - Reads the connections CSV, generates RDF triples per row (in parallel), saves artifacts, and inserts the resulting graph into the triple store.
  - `as_tools() -> list[BaseTool]`
    - Exposes a LangChain `StructuredTool` named `linkedin_export_connections_import_csv`.
  - `as_api(...) -> None`
    - Present but currently returns `None` (no API routes are registered).

### Methods (notable internal helpers)
- `get_person_uri_and_name_from_linkedin_profile_page_public_url(public_url: str) -> tuple[URIRef, str] | (None, None)`
  - Queries the triple store to resolve a `Person` URI and label via a `linkedin:ProfilePage` with `linkedin:public_url`.
- `generate_graph_date(date: datetime | str, date_format: str = "%Y-%m-%dT%H:%M:%S.%fZ") -> tuple[URIRef, Graph]`
  - Builds an RDF individual representing a datetime (or string) and returns its URI plus a graph of date triples.

## Configuration/Dependencies
- **Triple store**
  - `ITripleStoreService` must support:
    - `query(sparql: str)` (used to resolve the initial person)
    - `insert(graph: rdflib.Graph, graph_name: URIRef)` (used to persist results)
- **LinkedIn export integration**
  - `LinkedInExportIntegrationConfiguration(export_file_path=...)` is used by `LinkedInExportIntegration` for:
    - `unzip_export()` (used for file metadata and export directory)
    - `read_csv(file_name)`
- **BasePipeline utilities**
  - Uses `self.sparql_utils.get_identifiers(...)`, `self.sparql_utils.results_to_list(...)`
  - Uses `self.storage_utils.save_triples(...)` and `self.storage_utils.save_csv(...)`
- **Concurrency**
  - Processes rows with `ThreadPoolExecutor(max_workers=num_workers)` and uses locks for shared caches.

## Usage

```python
from naas_abi_core.engine.Engine import Engine
from naas_abi_marketplace.applications.linkedin import ABIModule
from naas_abi_marketplace.applications.linkedin.integrations.LinkedInExportIntegration import (
    LinkedInExportIntegrationConfiguration,
)
from naas_abi_marketplace.applications.linkedin.pipelines.LinkedInExportProfilePipeline import (
    LinkedInExportProfilePipelineConfiguration,
)
from naas_abi_marketplace.applications.linkedin.pipelines.LinkedInExportConnectionsPipeline import (
    LinkedInExportConnectionsPipeline,
    LinkedInExportConnectionsPipelineConfiguration,
    LinkedInExportConnectionsPipelineParameters,
)

engine = Engine()
engine.load(module_names=["naas_abi_marketplace.applications.linkedin"])
module: ABIModule = ABIModule.get_instance()

export_cfg = LinkedInExportIntegrationConfiguration(
    export_file_path="path/to/Complete_LinkedInDataExport.zip"
)
profile_cfg = LinkedInExportProfilePipelineConfiguration(
    triple_store=module.engine.services.triple_store,
    linkedin_export_configuration=export_cfg,
)

pipeline = LinkedInExportConnectionsPipeline(
    LinkedInExportConnectionsPipelineConfiguration(
        triple_store=module.engine.services.triple_store,
        linkedin_export_configuration=export_cfg,
        linkedin_export_profile_pipeline_configuration=profile_cfg,
        limit=None,
        num_workers=20,
    )
)

graph = pipeline.run(
    LinkedInExportConnectionsPipelineParameters(
        linkedin_public_url="https://www.linkedin.com/in/someone/",
        file_name="Connections.csv",
    )
)
print(len(graph))
```

## Caveats
- If the initial person cannot be resolved from the triple store after running the profile pipeline, `run()` raises `ValueError`.
- Rows with an unparseable `"Connected On"` field (expected format: `"%d %b %Y"`, e.g. `06 Jun 2025`) are partially processed:
  - The method logs a warning and **returns without creating the “act of connection” triples** for that row.
- `as_api()` is effectively a no-op (does not register routes).
- The pipeline preloads identifiers from the triple store into in-memory caches; correctness depends on `sparql_utils.get_identifiers(...)` semantics provided by `BasePipeline`.
