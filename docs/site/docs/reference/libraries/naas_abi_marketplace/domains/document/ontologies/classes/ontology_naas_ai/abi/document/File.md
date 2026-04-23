# `File`

## What it is
`File` is a document ontology class that adds object-storage and triple-store integration on top of the generated ontology `File` (`DocumentOntology.File`). It supports uploading binary content to object storage, creating an RDF record in a graph, fetching a file by SHA-256, and reading stored bytes.

## Public API
- `class File(_File)`
  - `actions(self) -> None`
    - Placeholder action hook (currently `pass`).
  - `read(self) -> bytes`
    - Reads the file content from object storage using `self.file_path` as the key (with empty prefix).
  - `@classmethod GetFromSha256(cls, sha256: str, graph_name: str) -> Self`
    - Queries the triple store for a `File` resource with matching `doc:sha256` in the specified graph.
    - Asserts exactly one match.
  - `@staticmethod key_from_filename(filename: str) -> str`
    - Builds a storage key with a timestamp suffix; includes an extension segment if the filename contains a dot.
  - `@classmethod UploadAndCreateFile(cls, content: bytes, filename: str, graph_name: str, destination_path: str = "", metadata: ObjectMetaData = None, kwargs: dict = {}) -> Self`
    - Uploads `content` to object storage under `destination_path` + generated key.
    - Retrieves metadata (unless provided) and creates a new `File` instance populated from metadata plus computed SHA-256.
    - Inserts the RDF representation into the triple store graph and returns the stored entity via `GetFromSha256`.

## Configuration/Dependencies
- Requires `ABIModule.get_instance()` to be configured with:
  - `engine.services.object_storage` implementing:
    - `put_object(prefix, key, content)`
    - `get_object(prefix, key)`
    - `get_object_metadata(prefix, key)`
  - `engine.services.triple_store` implementing:
    - `query(sparql_query)`
    - `insert(rdf_data, graph_name=...)`
- Uses `ObjectMetaData` from `naas_abi_core.services.object_storage.ObjectStoragePort`.

## Usage
```python
from naas_abi_marketplace.domains.document.ontologies.classes.ontology_naas_ai.abi.document.File import File

graph = "http://example.org/graphs/documents"

# Upload bytes, create RDF record, and get back the stored File entity
f = File.UploadAndCreateFile(
    content=b"hello world",
    filename="example.txt",
    graph_name=graph,
    destination_path="uploads",
)

# Read bytes back from object storage
data = f.read()
print(data)
```

## Caveats
- `GetFromSha256` uses `assert len(result) == 1`; it will raise `AssertionError` if no match or multiple matches are found.
- `read()` calls object storage with `prefix=""` and `key=self.file_path`; ensure your object storage implementation expects the full path in `key` in this case.
- `UploadAndCreateFile(..., kwargs: dict = {})` uses a mutable default; passing/retaining this dict across calls may have unintended side effects if mutated.
