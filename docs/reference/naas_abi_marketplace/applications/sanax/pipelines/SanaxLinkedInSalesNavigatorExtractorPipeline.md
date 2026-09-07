# SanaxLinkedInSalesNavigatorExtractorPipeline

## What it is
A `Pipeline` that reads an Excel export produced by the Sanax LinkedIn Sales Navigator Chrome extension, converts each row into RDF triples (RDFLib `Graph`), stores logs (TTL + Excel) via object storage, and inserts the graph into a configured triple store.

## Public API

### Configuration
- `SanaxLinkedInSalesNavigatorExtractorPipelineConfiguration(PipelineConfiguration)`
  - `triple_store: ITripleStoreService` — target triple store used to `insert()` the generated graph.
  - `data_store_path: str = "datastore/sanax/linkedin_sales_navigator"` — declared but not used by this pipeline.
  - `limit: int | None = None` — optional row limit (`df[:limit]`) before processing.

### Parameters
- `SanaxLinkedInSalesNavigatorExtractorPipelineParameters(PipelineParameters)`
  - `file_path: str` — path to the Excel file. If it starts with `"storage/"`, the prefix is stripped before reading.
  - `sheet_name: str = "LinkedIn Sales Navigator"` — worksheet name.

### Pipeline
- `SanaxLinkedInSalesNavigatorExtractorPipeline(configuration)`
  - `run(parameters: PipelineParameters) -> rdflib.Graph`
    - Reads and validates the Excel sheet (required columns).
    - Builds RDF individuals and relations for:
      - LinkedIn profile pages and company pages (custom `LINKEDIN` namespace)
      - People (`CCO["ont00001262"]`), organizations (`CCO["ont00001180"]`), positions (`BFO["BFO_0000023"]`), locations (`LINKEDIN["Location"]`)
      - A `DataSource` and per-row `DataSourceComponent`
      - Two “Act of Association” individuals per row (`CCO["ont00000433"]`), optionally linked to computed `ABI.startDate` dates
    - Saves TTL and Excel into object storage and inserts the graph into the triple store.
  - `calculate_start_date(duration_str: str, start_datetime: datetime | None = None) -> datetime | None`
    - Parses `"X years Y months"`-style durations and subtracts that number of months from the first day of the provided (or current UTC) month.
  - `generate_graph_date(date: datetime, date_format: str = "%Y-%m-%dT%H:%M:%S.%fZ") -> tuple[URIRef, Graph]`
    - Creates a date individual URI using epoch milliseconds and returns `(date_uri, graph_with_date_triples)`.
  - `as_tools() -> list[langchain_core.tools.BaseTool]`
    - Exposes a LangChain `StructuredTool` named `linkedin_sales_navigator_import_excel` that calls `run()`.
  - `as_api(...) -> None`
    - Stub only; does not register routes.

## Configuration/Dependencies

### Required Excel columns
The sheet must contain all of:
- `Name`
- `Job Title`
- `Company`
- `Company URL`
- `Location`
- `Time in Role`
- `Time in Company`
- `LinkedIn URL`

If missing, the pipeline logs an error and returns an empty `Graph`.

### Services and utilities used
- `ABIModule.get_instance().engine.services.triple_store` — used by `SPARQLUtils` for identifier lookups.
- `ABIModule.get_instance().engine.services.object_storage` — used by `StorageUtils` to:
  - `get_excel(...)`
  - `save_triples(...)`
  - `save_excel(...)`
- `configuration.triple_store.insert(graph, graph_name=URIRef("http://ontology.naas.ai/graph/default"))`

### Identifier/dedup strategy
- Uses `SPARQLUtils.get_identifiers(...)` to fetch existing identifiers for several classes/properties and avoid recreating some entities.
- Rows are deduplicated by hashing the full row tuple and checking the returned global identifier map.

## Usage

### Run the pipeline
```python
from naas_abi_marketplace.applications.sanax.pipelines.SanaxLinkedInSalesNavigatorExtractorPipeline import (
    SanaxLinkedInSalesNavigatorExtractorPipeline,
    SanaxLinkedInSalesNavigatorExtractorPipelineConfiguration,
    SanaxLinkedInSalesNavigatorExtractorPipelineParameters,
)

# Provide an implementation of ITripleStoreService
config = SanaxLinkedInSalesNavigatorExtractorPipelineConfiguration(triple_store=triple_store)

pipeline = SanaxLinkedInSalesNavigatorExtractorPipeline(config)

g = pipeline.run(
    SanaxLinkedInSalesNavigatorExtractorPipelineParameters(
        file_path="storage/datastore/linkedin_sales_navigator/sanax_extractor/Example.xlsx",
        sheet_name="LinkedIn Sales Navigator",
    )
)

print(len(g))
```

### Use as a LangChain tool
```python
tool = SanaxLinkedInSalesNavigatorExtractorPipeline(
    SanaxLinkedInSalesNavigatorExtractorPipelineConfiguration(triple_store=triple_store)
).as_tools()[0]

g = tool.func(
    file_path="storage/path/to/file.xlsx",
    sheet_name="LinkedIn Sales Navigator",
)
```

## Caveats
- `_read_and_validate_excel()` logs storage/local read failures but does not raise; it returns an empty `DataFrame` on validation failure or empty input.
- `_read_and_validate_excel()` may reference `df` after a storage read exception (because `df` is not initialized before the `try`), which can raise an error depending on execution flow.
- `run()` calls `os.path.getmtime(os.path.join("storage", dir_path, file_name))`; a local file must exist at that constructed path even if the Excel was read from object storage.
- The code uses `lk_linkedin_id` even when `"LinkedIn URL"` is empty, which can raise an error.
- `time_in_role_uri` / `time_in_company_uri` are only assigned when a start date is computed; later references can fail if the duration parsing returns `None`.
- Duration parsing only recognizes tokens containing `"year"` and/or `"month"` with a preceding digit; other formats return `None` and omit `ABI.startDate`.
