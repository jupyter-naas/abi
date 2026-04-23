# ActOfConnectionsOnLinkedInExportPipeline

## What it is
- A pipeline that imports LinkedIn **Connections** data from a LinkedIn export CSV (default: `Connections.csv`) into a triple store as RDF.
- Creates a set of shared entities (the “owner” person, export file, LinkedIn org, location), then processes each CSV row in parallel, generating RDF entities/relations and inserting each row graph into the triple store.

## Public API

### Configuration

- `ActOfConnectionsOnLinkedInExportPipelineConfiguration(PipelineConfiguration)`
  - `triple_store: ITripleStoreService` — target triple store service (must support `query()` and `insert()`).
  - `linkedin_export_configuration: LinkedInExportIntegrationConfiguration` — where the export ZIP/path is located.
  - `linkedin_export_profile_pipeline_configuration: LinkedInExportProfilePipelineConfiguration` — present but not used in this pipeline’s code.
  - `limit: int | None = None` — optional max number of CSV rows to process.
  - `workers: int = 20` — thread pool size for row processing.

### Parameters

- `ActOfConnectionsOnLinkedInExportPipelineParameters(PipelineParameters)`
  - `person_name: str` — used to find an existing `Person` by label substring match (case-insensitive) or create a new one.
  - `file_name: str = "Connections.csv"` — CSV name to read from the LinkedIn export.

### Pipeline

- `ActOfConnectionsOnLinkedInExportPipeline(Pipeline)`
  - `run(parameters: PipelineParameters) -> rdflib.Graph`
    - Inserts shared entities once.
    - Reads the CSV via `LinkedInExportIntegration.read_csv()`.
    - Processes each row concurrently, inserting each row’s RDF graph into the triple store as tasks complete.
    - Returns only the **shared** RDF graph (row graphs are inserted during processing).
  - `as_tools() -> list[langchain_core.tools.BaseTool]`
    - Exposes the pipeline as a LangChain `StructuredTool` named `linkedin_export_connections_import_csv`.
  - `as_api(...) -> None`
    - Declared but does not register any routes (returns `None`).
  - `get_person_entity_from_name(person_name: str) -> Person`
    - Queries the triple store for a `cco:ont00001262` (Person) whose `rdfs:label` contains `person_name`.
    - If not found, creates a new `Person` with a generated URI (not inserted until `run()` inserts shared graph).
  - `generate_graph_date(date: datetime | str, ...) -> ISO8601UTCDateTime`
    - Builds an `ISO8601UTCDateTime` entity URI/label from a `datetime` or a parsable string.
  - `_process_row(...) -> rdflib.Graph` (internal)
    - Converts one CSV row into RDF entities and relationships.

## Configuration/Dependencies
- **Triple store**: `ITripleStoreService`
  - Must support:
    - `query(sparql: str)` returning results consumable by `SPARQLUtils.results_to_list()`
    - `insert(graph: rdflib.Graph, graph_name: rdflib.term.URIRef)`
  - Inserts are written to graph name: `http://ontology.naas.ai/graph/default`.
- **LinkedIn export input**
  - `LinkedInExportIntegrationConfiguration.export_file_path` must point to the LinkedIn export archive/path expected by `LinkedInExportIntegration`.
- **Concurrency**
  - Uses `ThreadPoolExecutor` with configurable `workers`.
- **Ontology entities**
  - Uses classes from `naas_abi_marketplace.applications.linkedin.ontologies.modules.ActOfConnectionsOnLinkedIn` (e.g., `Person`, `ActOfConnection`, `ConnectionsExportFile`, etc.) and their `.rdf()` graph generation.

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

linkedin_export_configuration = LinkedInExportIntegrationConfiguration(
    export_file_path="path/to/Complete_LinkedInDataExport.zip"
)
profile_cfg = LinkedInExportProfilePipelineConfiguration(
    triple_store=module.engine.services.triple_store,
    linkedin_export_configuration=linkedin_export_configuration,
)

pipeline = ActOfConnectionsOnLinkedInExportPipeline(
    ActOfConnectionsOnLinkedInExportPipelineConfiguration(
        triple_store=module.engine.services.triple_store,
        linkedin_export_configuration=linkedin_export_configuration,
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
- **Return value**: `run()` returns only the graph for shared entities; per-row graphs are inserted during processing and not returned.
- **Date parsing**: expects `Connected On` formatted like `%d %b %Y` (e.g., `11 Jun 2025`). If parsing fails, it attempts `generate_graph_date()` with the raw string, which may raise if the string does not match the default `date_format`.
- **Person lookup heuristic**: `get_person_entity_from_name()` uses a substring match on `rdfs:label` and picks the first result only.
- **Console output**: uses `print()` in multiple places (including per-row worker messages), which can be noisy with many rows/workers.
- **`as_api()`**: does not expose any HTTP endpoints (no routes are registered).
