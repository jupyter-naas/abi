# StorageUtils

## What it is
`StorageUtils` is a thin helper around an `IObjectStorageDomain` implementation that reads/writes common file formats (text, images, CSV, Excel, JSON, YAML, RDF triples, PowerPoint) to object storage and optionally creates a timestamped copy on write.

## Public API
- `class StorageUtils(storage_service: IObjectStorageDomain)`
  - Wraps an object storage service to provide convenience methods.

### Read operations
- `get_text(dir_path, file_name, encoding="utf-8") -> str | None`
  - Fetches and decodes a text object.
- `get_image(dir_path, file_name) -> bytes | None`
  - Fetches raw bytes (intended for images).
- `get_csv(dir_path, file_name, sep=";", decimal=",", encoding="utf-8") -> pandas.DataFrame`
  - Fetches and parses CSV content from bytes.
- `get_excel(dir_path, file_name, sheet_name, skiprows=0, usecols=None) -> pandas.DataFrame`
  - Fetches and reads an Excel sheet from bytes.
- `get_json(dir_path, file_name) -> dict`
  - Fetches, decodes as UTF-8, parses JSON.
- `get_yaml(dir_path, file_name) -> dict`
  - Fetches, decodes as UTF-8, parses YAML with `yaml.safe_load`.
- `get_triples(dir_path, file_name, format="turtle") -> rdflib.Graph`
  - Fetches and parses RDF into an `rdflib.Graph`.
- `get_powerpoint_presentation(dir_path, file_name) -> io.BytesIO`
  - Fetches bytes and returns a `BytesIO` stream positioned at start.

### Write operations (optionally create a timestamped copy)
All save methods return `(dir_path, file_name)` and accept `copy: bool = True` to create an additional object named `YYYYmmddTHHMMSS_<file_name>` in the same prefix.
- `save_text(text, dir_path, file_name, encoding="utf-8", copy=True) -> (str, str)`
- `save_image(image: bytes, dir_path, file_name, copy=True) -> (str, str)`
- `save_csv(data: pandas.DataFrame, dir_path, file_name, sep=";", decimal=",", encoding="utf-8", copy=True) -> (str, str)`
- `save_excel(data: pandas.DataFrame, dir_path, file_name, sheet_name, copy=True) -> (str, str)`
- `save_json(data: dict | list, dir_path, file_name, copy=True) -> (str, str)`
  - Uses `json.dumps(..., indent=4, ensure_ascii=False)` encoded as UTF-8.
- `save_yaml(data: dict | list, dir_path, file_name, copy=True) -> (str, str)`
  - Uses `yaml.dump(..., allow_unicode=True, sort_keys=False)` encoded as UTF-8.
- `save_triples(graph: rdflib.Graph, dir_path, file_name, format="turtle", copy=True) -> (str, str)`
  - Serializes via `graph.serialize(format=format, sort=False)` encoded as UTF-8.
- `save_powerpoint_presentation(presentation, dir_path, file_name, copy=True) -> (str, str)`
  - Calls `presentation.save(BytesIO())` and stores resulting bytes.

## Configuration/Dependencies
- Requires an object that implements `naas_abi_core.services.object_storage.ObjectStoragePort.IObjectStorageDomain` with:
  - `get_object(prefix: str, key: str) -> bytes`
  - `put_object(prefix: str, key: str, content: bytes) -> None`
- External libraries used:
  - `pandas` (CSV/Excel)
  - `PyYAML` (`yaml`)
  - `rdflib` (`Graph`)
- Logging via `naas_abi_core.logger`.

## Usage
```python
import pandas as pd
from naas_abi_core.utils.StorageUtils import StorageUtils

# storage_service must implement IObjectStorageDomain (get_object/put_object).
storage = StorageUtils(storage_service)

# Save/load text
storage.save_text("hello", "my/prefix", "hello.txt", copy=True)
txt = storage.get_text("my/prefix", "hello.txt")

# Save/load CSV
df = pd.DataFrame([{"a": 1}, {"a": 2}])
storage.save_csv(df, "my/prefix", "data.csv")
df2 = storage.get_csv("my/prefix", "data.csv")
```

## Caveats
- Error handling is "best-effort":
  - Most `get_*` methods return an empty object on failure (`None`, `{}`, `pd.DataFrame()`, `Graph()`, or `BytesIO()`), after logging.
  - `save_*` methods return `(dir_path, file_name)` even on failure (and log errors).
- The `copy=True` option creates an additional timestamped object in the same storage prefix; it does not modify local filesystems.
- CSV defaults are locale-like (`sep=";"`, `decimal=","`), which may not match typical comma-separated CSVs.
