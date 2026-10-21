# LinkedInExportIntegration

## What it is
- Integration for working with a LinkedIn data export **ZIP** file:
  - Extracts the ZIP into a sibling directory (same parent, directory name = ZIP stem).
  - Lists extracted files/folders.
  - Reads CSV files from the extracted export into a `pandas.DataFrame`.
- Optional helper to expose the integration as LangChain `StructuredTool`s.

## Public API

### `LinkedInExportIntegrationConfiguration`
- Dataclass configuration (extends `IntegrationConfiguration`).
- Fields:
  - `export_file_path: str` — path to the LinkedIn export ZIP file.

### `LinkedInExportIntegration`
Integration class (extends `Integration`).

- `__init__(configuration: LinkedInExportIntegrationConfiguration)`
  - Initializes the integration with the provided configuration.

- `unzip_export() -> dict[str, Any]`
  - Validates that `export_file_path` exists and is a ZIP.
  - Extracts all contents into `<zip_parent>/<zip_stem>` (directory is created if missing).
  - Returns:
    - `extracted_directory: str`
    - `files_count: int`
    - `folders_count: int`
    - `files: list[str]` (paths relative to extracted directory)
    - `folders: list[str]` (paths relative to extracted directory)
    - `file_created_at: datetime` (UTC)
    - `file_modified_at: datetime` (UTC)

- `list_files_and_folders(recursive: bool = True) -> dict`
  - Calls `unzip_export()` and lists contents of the extracted directory.
  - Returns:
    - `files: list[str]` (sorted, relative paths)
    - `folders: list[str]` (sorted, relative paths)
    - `total_files: int`
    - `total_folders: int`
    - `path: str` (extracted directory path)

- `list_files() -> list[str]`
  - Convenience wrapper returning `list_files_and_folders()["files"]` (recursive).

- `read_csv(csv_file_name: str, sep: str = ",", encodings: list[str] | None = None, header: int | None = 0, skiprows: int | None = None, nrows: int | None = None) -> pd.DataFrame`
  - Calls `unzip_export()`, then reads `csv_file_name` from the extracted directory.
  - Tries multiple encodings (default: `["utf-8", "latin-1"]`).
  - Attempts to detect the header row by scanning for the first line containing `sep` where the first column token length is `< 25`; uses that row as the starting point when `header is not None`.
  - Returns a `pandas.DataFrame`.

### `as_tools(configuration: LinkedInExportIntegrationConfiguration) -> list`
- Builds LangChain `StructuredTool`s backed by a `LinkedInExportIntegration` instance:
  - `linkedin_export_unzip`
  - `linkedin_export_list_files_and_folders`
  - `linkedin_export_list_files`
  - `linkedin_export_read_csv` (args: `csv_file_name`, `sep`)

## Configuration/Dependencies
- Required:
  - `pandas`
  - Standard library: `os`, `zipfile`, `dataclasses`, `datetime`, `pathlib`, `typing`
  - `naas_abi_core.integration.integration` (`Integration`, `IntegrationConfiguration`)
- Optional (only for `as_tools`):
  - `langchain_core.tools.StructuredTool`
  - `pydantic` (`BaseModel`, `Field`)

## Usage

```python
from naas_abi_marketplace.applications.linkedin.integrations.LinkedInExportIntegration import (
    LinkedInExportIntegration,
    LinkedInExportIntegrationConfiguration,
)

cfg = LinkedInExportIntegrationConfiguration(
    export_file_path="/path/to/LinkedInDataExport.zip"
)

integration = LinkedInExportIntegration(cfg)

info = integration.unzip_export()
print(info["extracted_directory"])

print(integration.list_files()[:10])

df = integration.read_csv("Connections.csv", sep=",")
print(df.head())
```

## Caveats
- `list_files_and_folders()`, `list_files()`, and `read_csv()` call `unzip_export()` internally; repeated calls will re-run extraction into the same directory.
- CSV header detection is heuristic and based on finding the first “separator-containing” line with a short first token (`< 25` characters).
