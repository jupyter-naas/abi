# ExportGraphInstancesToExcelWorkflow

## What it is
A workflow that:
- Reads an RDF graph from a configured triple store.
- Exports named individuals grouped by class into an Excel workbook (one sheet per class).
- Adds summary sheets for **Classes** and **Object Properties** (with hyperlinks to sheets).
- Uploads the generated `.xlsx` as a **public** asset via `NaasIntegration` and returns a download URL (or `None` if upload fails).

## Public API

### Classes

- `ExportGraphInstancesToExcelWorkflowConfiguration(WorkflowConfiguration)`
  - Configuration fields:
    - `triple_store: ITripleStoreService` — source RDF graph provider (`.get() -> rdflib.Graph`).
    - `naas_integration_config: NaasIntegrationConfiguration` — used to upload the Excel file as an asset.
    - `data_store_path: str = "datastore/triplestore/export/excel"` — relative storage path under `storage/`.

- `ExportGraphInstancesToExcelWorkflowParameters(WorkflowParameters)`
  - Parameters:
    - `excel_file_name: str = "graph_instances_export.xlsx"` — name used for the uploaded asset object name.

- `ExportGraphInstancesToExcelWorkflow(Workflow)`
  - `create_sheet_name(label: str) -> str`
    - Sanitizes a label for an Excel sheet name (replaces invalid characters, truncates to 31 chars).
  - `autofit_columns(writer: pd.ExcelWriter, sheet_name: str) -> pd.ExcelWriter`
    - Adjusts worksheet column widths based on content; sets `"Sheet Name"` column width to match `"Label"` column width if present.
  - `get_all_triples_by_class(graph: rdflib.Graph) -> rdflib.query.Result`
    - Returns distinct classes that have `owl:NamedIndividual` instances whose subject URI starts with `http://ontology.naas.ai/abi/`.
  - `get_all_object_property_labels(graph: rdflib.Graph) -> dict[str, str]`
    - Returns a mapping `{object_property_uri: rdfs:label}` for `owl:ObjectProperty` entries that have a label.
  - `export_to_excel(parameters: ExportGraphInstancesToExcelWorkflowParameters) -> str | None`
    - Generates the workbook, writes it under `storage/<data_store_path>/` with a timestamp prefix, uploads it publicly, returns `asset_url` or `None`.
  - `as_tools() -> list[BaseTool]`
    - Exposes a LangChain `StructuredTool` named `export_graph_instances_to_excel`.
  - `as_api(...) -> None`
    - Defined but does not register any routes (no implementation beyond default args handling).

## Configuration/Dependencies
- Requires:
  - `ITripleStoreService` implementation providing `get() -> rdflib.Graph`.
  - `NaasIntegrationConfiguration` to initialize `NaasIntegration`.
  - `ABIModule.get_instance().configuration.workspace_id` and `.storage_name` for asset upload.
- Writes locally to:
  - `storage/<data_store_path>/<timestamp>_<excel_file_name>`
- Uses:
  - `pandas` (Excel writing via `openpyxl`)
  - `rdflib`
  - `langchain_core.tools` (`StructuredTool`)

## Usage
```python
from naas_abi_marketplace.applications.naas.workflows.ExportGraphInstancesToExcelWorkflow import (
    ExportGraphInstancesToExcelWorkflow,
    ExportGraphInstancesToExcelWorkflowConfiguration,
    ExportGraphInstancesToExcelWorkflowParameters,
)

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
- Only individuals whose URI starts with `http://ontology.naas.ai/abi/` are included (SPARQL `STRSTARTS` filter).
- Object-property relations are exported into separate sheets per object property; data properties remain in per-class sheets.
- Excel sheet names are sanitized and truncated to 31 characters; truncation can cause name collisions for long/similar labels.
- The Excel file is always written locally; if asset upload fails, `export_to_excel` returns `None` even though the file exists on disk.
