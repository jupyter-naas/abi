# ActOfConnectionsOnLinkedInExportPipeline

## What it is
- A threaded import pipeline that reads LinkedIn **Connections** data from a LinkedIn export CSV (default `Connections.csv`) and inserts RDF graphs into a triple store.
- Inserts a **shared** RDF graph once (owner person, export file, LinkedIn org, location), then processes each CSV row in parallel and inserts each row’s RDF graph as it completes.

## Public API

### Configuration
- `ActOfConnectionsOnLinkedInExportPipelineConfiguration(PipelineConfiguration)`
  - `triple_store: ITripleStoreService` — target triple store; must support `query()` and `insert()`.
  - `linkedin_export_configuration: LinkedInExportIntegrationConfiguration` — where the export archive/path is located.
  - `linkedin_export_profile_pipeline_configuration: LinkedInExportProfilePipelineConfiguration` — required by config, not otherwise used in this pipeline.
  - `limit: int | None = None` — optional maximum number of rows to process.
  - `workers: int = 20` — number of thread workers for row processing.

### Parameters
- `ActOfConnectionsOnLinkedInExportPipelineParameters(PipelineParameters)`
  - `person_name: str` — used to find (via SPARQL label substring match) or create the “owner” `Person`.
  - `file_name: str = "Connections.csv"` — CSV file name to read from the LinkedIn export.

### Pipeline class
- `ActOfConnectionsOnLinkedInExportPipeline(Pipeline)`
  - `run(parameters: PipelineParameters) -> rdflib.Graph`
    - Inserts shared entities into the triple store.
    - Reads the CSV via `LinkedInExportIntegration.read_csv()`.
    - Processes rows concurrently via `ThreadPoolExecutor`, inserting each row graph into the triple store.
    - Returns the shared graph only (row graphs are not returned).
  - `as_tools() -> list[langchain_core.tools.BaseTool]`
    - Exposes a LangChain `StructuredTool` named `linkedin_export_connections_import_csv`.
  - `as_api(...) -> None`
    - No routes are registered (method is effectively a no-op).
  - `get_person_entity_from_name(person_name: str) -> Person`
    - Queries the triple store for a `cco:ont00001262` Person whose `rdfs:label` contains `person_name` (case-insensitive).
    - If not found, creates a new `Person` with a generated URI (not inserted until `run()`).
  - `generate_graph_date(date: datetime | str, date_format: str = "%d %b %Y", target_date_format: str = "%Y-%m-%dT%H:%M:%S.%fZ") -> ISO8601UTCDateTime`
    - Creates an `ISO8601UTCDateTime` entity from a `datetime` or a parseable string.
  - `_process_row(...) -> rdflib.Graph` (internal)
    - Builds RDF entities and relations for one CSV row.

## Configuration/Dependencies
- **Triple store**
  - Interface: `ITripleStoreService`
    - `query(sparql: str)` (consumed through `SPARQLUtils.results_to_list`)
    - `insert(graph: rdflib.Graph, graph_name: rdflib.term.URIRef)`
  - Insert graph name used: `http://ontology.naas.ai/graph/default`
- **LinkedIn export reader**
  - `LinkedInExportIntegration` driven by `LinkedInExportIntegrationConfiguration.export_file_path`
- **Concurrency**
  - Uses `ThreadPoolExecutor(max_workers=workers)`; inserts occur as futures complete.
- **Ontology entities**
  - Uses classes from `naas_abi_marketplace.applications.linkedin.ontologies.modules.ActOfConnectionsOnLinkedIn` (e.g., `Person`, `ActOfConnection`, `ConnectionsExportFile`, etc.), generating RDF via each entity’s `.rdf()`.

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
from naas_abi_marketplace.applications.linkedin.pipelines.ActOfConnectionsOnLinkedInExportPipeline import (
    ActOfConnectionsOnLinkedInExportPipeline,
    ActOfConnectionsOnLinkedInExportPipelineConfiguration,
    ActOfConnectionsOnLinkedInExportPipelineParameters,
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

pipeline = ActOfConnectionsOnLinkedInExportPipeline(
    ActOfConnectionsOnLinkedInExportPipelineConfiguration(
        triple_store=module.engine.services.triple_store,
        linkedin_export_configuration=export_cfg,
        linkedin_export_profile_pipeline_configuration=profile_cfg,
        limit=100,
        workers=10,
    )
)

shared_graph = pipeline.run(
    ActOfConnectionsOnLinkedInExportPipelineParameters(
        person_name="Jane Doe",
        file_name="Connections.csv",
    )
)
```

## Caveats
- `run()` returns only the **shared** RDF graph; per-row graphs are inserted during execution and not returned.
- Date handling:
  - Tries to parse `Connected On` using `"%d %b %Y"`; if parsing fails, it calls `generate_graph_date()` with the raw string, which will raise if it still cannot be parsed.
- Person lookup:
  - `get_person_entity_from_name()` uses a case-insensitive substring match on `rdfs:label` and returns the **first** match only.
- Logging/output:
  - Uses `print()` in several places, including per-row worker messages, which can be noisy with many rows/workers.
- `as_api()` does not register any routes.
