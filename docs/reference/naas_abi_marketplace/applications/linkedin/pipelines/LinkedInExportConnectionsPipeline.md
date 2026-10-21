# LinkedInExportConnectionsPipeline

## What it is
- A pipeline that imports **LinkedIn Connections** from a LinkedIn export CSV (default `Connections.csv`) into an RDF graph and inserts it into a configured triple store.
- It first runs `LinkedInExportProfilePipeline` to ensure the “initial person” (profile owner) exists and can be linked to connection events.

## Public API

### Classes

- `LinkedInExportConnectionsPipelineConfiguration(PipelineConfiguration)`
  - Runtime configuration:
    - `triple_store: ITripleStoreService` — SPARQL query + graph insert target.
    - `linkedin_export_configuration: LinkedInExportIntegrationConfiguration` — points to the LinkedIn export ZIP.
    - `linkedin_export_profile_pipeline_configuration: LinkedInExportProfilePipelineConfiguration` — used to build profile/person primitives and backing datasource.
    - `limit: int | None = None` — optional number of CSV rows to process.
    - `num_workers: int = 20` — thread pool size for row processing.

- `LinkedInExportConnectionsPipelineParameters(PipelineParameters)`
  - Parameters:
    - `linkedin_public_url: str` — profile owner LinkedIn public URL.
    - `file_name: str = "Connections.csv"` — CSV file name inside the export.

- `LinkedInExportConnectionsPipeline(Pipeline, BasePipeline)`
  - `run(parameters: PipelineParameters) -> rdflib.Graph`
    - Runs the profile pipeline, reads the connections CSV, builds RDF triples per row (parallelized), saves artifacts, and inserts the graph into the triple store.
  - `as_tools() -> list[langchain_core.tools.BaseTool]`
    - Exposes a LangChain `StructuredTool` named `linkedin_export_connections_import_csv` that calls `run()`.
  - `as_api(...) -> None`
    - Defined but does not register routes.

### Other methods
- `get_person_uri_and_name_from_linkedin_profile_page_public_url(public_url: str) -> tuple[URIRef, str] | (None, None)`
  - Queries the triple store for a `linkedin:ProfilePage` with `linkedin:public_url` and returns the linked person URI + label.
- `generate_graph_date(date: datetime | str, date_format: str = "%Y-%m-%dT%H:%M:%S.%fZ") -> tuple[URIRef, Graph]`
  - Builds a date individual and returns `(date_uri, graph_with_date_triples)`.

## Configuration/Dependencies
- **Triple store (`ITripleStoreService`)**
  - Must support:
    - `query(sparql: str)` (used to resolve the initial person)
    - `insert(graph: rdflib.Graph, graph_name: rdflib.URIRef)` (used to persist results)

- **LinkedIn export integration**
  - `LinkedInExportIntegrationConfiguration(export_file_path=...)` used by `LinkedInExportIntegration`:
    - `read_csv(file_name)` to load the CSV into a DataFrame.
    - `unzip_export()` to get `extracted_directory`, `file_modified_at`, `file_created_at`.

- **BasePipeline utilities (inherited)**
  - Uses:
    - `self.sparql_utils.get_identifiers(...)` and `self.sparql_utils.results_to_list(...)`
    - `self.storage_utils.save_triples(...)` and `self.storage_utils.save_csv(...)`

- **Concurrency**
  - Uses `ThreadPoolExecutor(max_workers=num_workers)` to process rows.
  - Shared identifier caches protected with `threading.Lock` and a double-check pattern.

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
        linkedin_public_url="https://demo.example/profiles/demo",
        file_name="Connections.csv",
    )
)

print(len(graph))
```

## Caveats
- If the initial person cannot be resolved from the triple store after running the profile pipeline, `run()` raises `ValueError`.
- If a row has an unparseable `"Connected On"` value (expected format `"%d %b %Y"`), that row is imported **without** the “act of connection” triples (the method logs a warning and returns early for that part).
- `as_api()` is effectively a no-op (no routes registered).
- The pipeline inserts into graph name: `http://ontology.naas.ai/graph/default`.
