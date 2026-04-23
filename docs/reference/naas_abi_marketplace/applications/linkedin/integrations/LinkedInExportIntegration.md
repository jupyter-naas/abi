# LinkedInExportIntegration

## What it is
- A small integration that works with a LinkedIn data export **ZIP** file:
  - Extracts the ZIP into a sibling folder.
  - Lists extracted files/folders.
  - Reads CSV files from the extracted export into a `pandas.DataFrame`.
- Includes a helper to expose the integration as LangChain `StructuredTool`s.

## Public API

### `LinkedInExportIntegrationConfiguration`
- Dataclass configuration (extends `IntegrationConfiguration`).
- **Fields**
  - `export_file_path: str` — path to the LinkedIn export ZIP file.

### `LinkedInExportIntegration`
Integration class (extends `Integration`).

- `__init__(configuration: LinkedInExportIntegrationConfiguration)`
  - Stores configuration.

- `unzip_export() -> Dict[str, Any]`
  - Validates the configured ZIP path and extracts it to a directory next to the ZIP.
  - Returns a dict with:
    - `extracted_directory: str`
    - `files_count: int`, `folders_count: int`
    - `files: List[str]` (relative paths)
    - `folders: List[str]` (relative paths)
    - `file_created_at: datetime`, `file_modified_at: datetime`

- `list_files_and_folders(recursive: bool = True) -> Dict`
  - Calls `unzip_export()` and lists the extracted directory contents.
  - Returns:
    - `files: List[str]`, `folders: List[str]` (relative paths)
    - `total_files: int`, `total_folders: int`
    - `path: str` (extracted directory path)

- `list_files() -> List[str]`
  - Convenience wrapper returning `list_files_and_folders()["files"]`.

- `read_csv(csv_file_name: str, sep: str = ",", encodings: List[str] = ["utf-8", "latin-1"], header: Optional[int] = 0, skiprows: Optional[int] = None, nrows: Optional[int] = None) -> pd.DataFrame`
  - Calls `unzip_export()`, then reads a CSV inside the extracted directory.
  - Tries multiple encodings; attempts to detect the header row by scanning for the first “header-like” line containing `sep`.
  - Returns a `pandas.DataFrame`.

### `as_tools(configuration: LinkedInExportIntegrationConfiguration) -> list`
- Returns a list of LangChain `StructuredTool`s:
  - `linkedin_export_unzip`
  - `linkedin_export_list_files_and_folders`
  - `linkedin_export_list_files`
  - `linkedin_export_read_csv` (args: `csv_file_name`, `sep`)

## Configuration/Dependencies
- Requires:
  - `pandas`
  - Standard library: `os`, `zipfile`, `dataclasses`, `datetime`, `pathlib`
  - `naas_abi_core.integration.integration` (`Integration`, `IntegrationConfiguration`)
- Optional (only if using `as_tools`):
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

files = integration.list_files()
print(files[:5])

df = integration.read_csv("Connections.csv", sep=",")
print(df.head())
```

## Caveats
- `list_files_and_folders()`, `list_files()`, and `read_csv()` call `unzip_export()` internally; repeated calls may re-extract the ZIP into the same directory.
- Extraction directory naming is derived from `export_file_path` (`<zip parent>/<zip stem>`), and the directory is created if missing.
- `read_csv()` header detection is heuristic; it scans for the first line containing the separator and assumes it is a header when the first column name length is below a fixed threshold.
