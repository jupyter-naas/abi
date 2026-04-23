# StorageUtils

## What it is
- A small helper class that reads/writes common file formats to an object storage backend.
- Wraps an `IObjectStorageDomain` implementation and provides convenience methods for text, images, CSV/Excel, JSON/YAML, RDF triples, and PowerPoint presentations.
- Optionally creates a timestamped copy of the stored content on each save.

## Public API
### Class: `StorageUtils`
**Constructor**
- `StorageUtils(storage_service: IObjectStorageDomain)`
  - Binds the utility to an object storage service.

**Read methods**
- `get_text(dir_path: str, file_name: str, encoding: str = "utf-8") -> str | None`
  - Fetches bytes from storage and decodes to text. Returns `None` on error.
- `get_image(dir_path: str, file_name: str) -> bytes | None`
  - Fetches raw bytes. Returns `None` on error.
- `get_csv(dir_path: str, file_name: str, sep: str = ";", decimal: str = ",", encoding: str = "utf-8") -> pandas.DataFrame`
  - Reads CSV content into a DataFrame. Returns empty `DataFrame()` on error.
- `get_excel(dir_path: str, file_name: str, sheet_name: str, skiprows: int = 0, usecols: list | None = None) -> pandas.DataFrame`
  - Reads an Excel sheet into a DataFrame. Returns empty `DataFrame()` on error.
- `get_json(dir_path: str, file_name: str) -> Dict`
  - Loads JSON into a Python object (typed as `Dict` in signature). Returns `{}` on error.
- `get_yaml(dir_path: str, file_name: str) -> Dict`
  - Loads YAML via `yaml.safe_load`. Returns `{}` on error or if YAML content is empty/null.
- `get_triples(dir_path: str, file_name: str, format: str = "turtle") -> rdflib.Graph`
  - Parses RDF content into an `rdflib.Graph`. Returns an empty `Graph()` on error.
- `get_powerpoint_presentation(dir_path: str, file_name: str) -> io.BytesIO`
  - Returns a `BytesIO` stream for the presentation content. Returns empty `BytesIO()` on error.

**Write methods**
- `save_text(text: str, dir_path: str, file_name: str, encoding: str = "utf-8", copy: bool = True) -> tuple[str, str]`
  - Encodes and stores text. Optionally writes a timestamped copy.
- `save_image(image: bytes, dir_path: str, file_name: str, copy: bool = True) -> tuple[str, str]`
  - Stores raw image bytes. Optionally writes a timestamped copy.
- `save_csv(data: pandas.DataFrame, dir_path: str, file_name: str, sep: str = ";", decimal: str = ",", encoding: str = "utf-8", copy: bool = True) -> tuple[str, str]`
  - Stores a DataFrame as CSV bytes. Optionally writes a timestamped copy.
- `save_excel(data: pandas.DataFrame, dir_path: str, file_name: str, sheet_name: str, copy: bool = True) -> tuple[str, str]`
  - Stores a DataFrame as an Excel file (in-memory). Optionally writes a timestamped copy.
- `save_json(data: dict | list, dir_path: str, file_name: str, copy: bool = True) -> tuple[str, str]`
  - Stores JSON (pretty-printed, `ensure_ascii=False`). Optionally writes a timestamped copy.
- `save_yaml(data: dict | list, dir_path: str, file_name: str, copy: bool = True) -> tuple[str, str]`
  - Stores YAML via `yaml.dump(..., allow_unicode=True, sort_keys=False)`. Optionally writes a timestamped copy.
- `save_triples(graph: rdflib.Graph, dir_path: str, file_name: str, format: str = "turtle", copy: bool = True) -> tuple[str, str]`
  - Serializes an RDF graph and stores it. Optionally writes a timestamped copy.
- `save_powerpoint_presentation(presentation, dir_path: str, file_name: str, copy: bool = True) -> tuple[str, str]`
  - Saves a presentation into an in-memory stream using `presentation.save(stream)` and stores it. Optionally writes a timestamped copy.

## Configuration/Dependencies
- Requires an object implementing `naas_abi_core.services.object_storage.ObjectStoragePort.IObjectStorageDomain` with:
  - `get_object(prefix_or_dir_path, key_or_file_name) -> bytes`
  - `put_object(prefix: str, key: str, content: bytes) -> None`
- External libraries used:
  - `pandas` (CSV/Excel)
  - `PyYAML` (`yaml`)
  - `rdflib` (`Graph`)
- Uses `naas_abi_core.logger` for debug/warning/error logs.

## Usage
```python
import pandas as pd
from naas_abi_core.utils.StorageUtils import StorageUtils

# storage_service must implement IObjectStorageDomain
storage = StorageUtils(storage_service)

# Text
storage.save_text("hello", dir_path="mydir", file_name="hello.txt", copy=False)
print(storage.get_text("mydir", "hello.txt"))

# CSV
df = pd.DataFrame([{"a": 1, "b": 2}])
storage.save_csv(df, dir_path="mydir", file_name="data.csv", copy=False)
print(storage.get_csv("mydir", "data.csv"))
```

## Caveats
- Error handling is non-throwing:
  - Many `get_*` methods return `None`, `{}`, `BytesIO()`, or empty `DataFrame()` on failure.
  - `save_*` methods return `(dir_path, file_name)` even on failure (and log errors).
- `copy=True` creates an additional object named `YYYYMMDDTHHMMSS_<original_name>` in the same `dir_path`.
- `get_json` is annotated to return `Dict` but `json.loads` may return a `list` depending on stored content.
