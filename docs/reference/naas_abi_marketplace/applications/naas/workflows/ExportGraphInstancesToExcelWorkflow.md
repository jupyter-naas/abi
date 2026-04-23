# ExportGraphInstancesToExcelWorkflow

## What it is
A `Workflow` that reads an RDF graph from a configured triple store, exports named individuals grouped by class into an Excel workbook (one sheet per class), adds summary sheets (Classes, Object Properties), and uploads the resulting `.xlsx` as a public asset via `NaasIntegration`, returning a download URL.

## Public API

### Classes
- `ExportGraphInstancesToExcelWorkflowConfiguration(WorkflowConfiguration)`
  - Holds dependencies and settings:
    - `triple_store: ITripleStoreService`
    - `naas_integration_config: NaasIntegrationConfiguration`
    - `data_store_path: str = "datastore/triplestore/export/excel"`

- `ExportGraphInstancesToExcelWorkflowParameters(WorkflowParameters)`
  - Workflow parameters:
    - `excel_file_name: str = "graph_instances_export.xlsx"`: output filename (used for upload object name; file on disk is timestamp-prefixed).

- `ExportGraphInstancesToExcelWorkflow(Workflow)`
  - `create_sheet_name(label: str) -> str`
    - Sanitizes a label for an Excel sheet name and truncates to 31 chars.
  - `autofit_columns(writer: pd.ExcelWriter, sheet_name: str) -> pd.ExcelWriter`
    - Adjusts column widths based on cell content; aligns “Sheet Name” column width to “Label” column width.
  - `get_all_triples_by_class(graph: rdflib.Graph) -> rdflib.query.Result`
    - SPARQL query returning distinct classes having `owl:NamedIndividual` instances under the `http://ontology.naas.ai/abi/` namespace.
  - `get_all_object_property_labels(graph: rdflib.Graph) -> dict[str, str]`
    - SPARQL query mapping `owl:ObjectProperty` URIs to their `rdfs:label`.
  - `export_to_excel(parameters: ExportGraphInstancesToExcelWorkflowParameters) -> Optional[str]`
    - Creates the Excel workbook, stores it under `storage/<data_store_path>/`, uploads it as a public asset, and returns `asset_url` (or `None` on upload failure).
  - `as_tools() -> list[BaseTool]`
    - Exposes the workflow as a LangChain `StructuredTool` named `export_graph_instances_to_excel`.
  - `as_api(...) -> None`
    - Present but does not register any API routes (returns `None`).

## Configuration/Dependencies
- Requires a triple store service implementing `ITripleStoreService` with `.get() -> rdflib.Graph`.
- Requires `NaasIntegrationConfiguration` to upload the generated Excel file.
- Uses `ABIModule.get_instance().configuration.workspace_id` and `.storage_name` during upload.
- Writes a local `.xlsx` file under:
  - `storage/<data_store_path>/YYYYMMDDTHHMMSS_<excel_file_name>`
- Runtime dependencies used directly:
  - `pandas` with `openpyxl` engine
  - `rdflib`

## Usage
```python
from naas_abi_marketplace.applications.naas.workflows.ExportGraphInstancesToExcelWorkflow import (
    ExportGraphInstancesToExcelWorkflow,
    ExportGraphInstancesToExcelWorkflowConfiguration,
    ExportGraphInstancesToExcelWorkflowParameters,
)

# Provide concrete implementations/config from your app environment
config = ExportGraphInstancesToExcelWorkflowConfiguration(
    triple_store=triple_store_service,  # ITripleStoreService
    naas_integration_config=naas_integration_config,  # NaasIntegrationConfiguration
)

wf = ExportGraphInstancesToExcelWorkflow(config)

url = wf.export_to_excel(
    ExportGraphInstancesToExcelWorkflowParameters(excel_file_name="export.xlsx")
)
print(url)  # public asset URL (or None)
```

## Caveats
- Only individuals whose URI starts with `http://ontology.naas.ai/abi/` are included (SPARQL filter).
- Object properties are exported to separate per-property sheets; data properties remain in the per-class sheets.
- Excel sheet names are sanitized and truncated to 31 characters; truncation may cause collisions for long/ similar labels.
- Upload is required to obtain a URL; if upload fails, the method returns `None` even though the file is written locally.
