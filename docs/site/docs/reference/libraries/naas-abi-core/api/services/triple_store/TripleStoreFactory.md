# TripleStoreFactory

## What it is
- A small factory module that builds `TripleStoreService` instances backed by different secondary adaptors:
  - Naas object storage
  - Local filesystem
  - AWS Neptune via SSH tunnel
  - Oxigraph HTTP endpoint
  - Apache Jena Fuseki (TDB2) HTTP endpoint

## Public API
- `class TripleStoreFactory`
  - `TripleStoreServiceNaas(naas_api_key: str, workspace_id: str, storage_name: str, base_prefix: str = "ontologies") -> TripleStoreService`
    - Creates a `TripleStoreService` using Naas object storage via `ObjectStorageFactory.ObjectStorageServiceNaas` and an object-storage-backed triple store adaptor.
  - `TripleStoreServiceFilesystem(path: str) -> TripleStoreService`
    - Creates a `TripleStoreService` using a filesystem-backed adaptor rooted at `path`.
  - `TripleStoreServiceAWSNeptuneSSHTunnel(...) -> TripleStoreService`
    - Creates a `TripleStoreService` using an AWS Neptune SSH tunnel adaptor.
    - Note: Although parameters are present, the implementation reads required values from environment variables (see below).
  - `TripleStoreServiceOxigraph(oxigraph_url: str | None = None) -> TripleStoreService`
    - Creates a `TripleStoreService` using an Oxigraph adaptor pointed at `oxigraph_url` (or env/default).
  - `TripleStoreServiceApacheJenaTDB2(jena_tdb2_url: str | None = None) -> TripleStoreService`
    - Creates a `TripleStoreService` using an Apache Jena Fuseki (TDB2) adaptor pointed at `jena_tdb2_url` (or env/default).

## Configuration/Dependencies
- Imports/depends on:
  - `TripleStoreService`
  - Secondary adaptors:
    - `TripleStoreService__SecondaryAdaptor__ObjectStorage`
    - `TripleStoreService__SecondaryAdaptor__Filesystem`
    - `AWSNeptuneSSHTunnel`
    - `Oxigraph`
    - `ApacheJenaTDB2`
  - `ObjectStorageFactory` for Naas storage integration
- Environment variables:
  - For `TripleStoreServiceAWSNeptuneSSHTunnel` (required; asserted non-null/non-sentinel):
    - `AWS_REGION`
    - `AWS_ACCESS_KEY_ID`
    - `AWS_SECRET_ACCESS_KEY`
    - `AWS_NEPTUNE_DB_INSTANCE_IDENTIFIER`
    - `AWS_BASTION_HOST`
    - `AWS_BASTION_PORT` (must parse to int and not equal `-42`)
    - `AWS_BASTION_USER`
    - `AWS_BASTION_PRIVATE_KEY`
  - For `TripleStoreServiceOxigraph`:
    - `OXIGRAPH_URL` (default: `http://localhost:7878`)
  - For `TripleStoreServiceApacheJenaTDB2`:
    - `JENA_TDB2_URL` (default: `http://localhost:3030/ds`)

## Usage
```python
from naas_abi_core.services.triple_store.TripleStoreFactory import TripleStoreFactory

# Filesystem-backed triple store
ts = TripleStoreFactory.TripleStoreServiceFilesystem("/tmp/triples")

# Oxigraph-backed triple store (uses OXIGRAPH_URL or default)
ts_oxi = TripleStoreFactory.TripleStoreServiceOxigraph()

# Apache Jena Fuseki (TDB2) dataset (uses JENA_TDB2_URL or default)
ts_jena = TripleStoreFactory.TripleStoreServiceApacheJenaTDB2("http://localhost:3030/ds")

# Naas object-storage-backed triple store
ts_naas = TripleStoreFactory.TripleStoreServiceNaas(
    naas_api_key="...",
    workspace_id="...",
    storage_name="...",
    base_prefix="ontologies",
)
```

## Caveats
- `TripleStoreServiceAWSNeptuneSSHTunnel(...)` ignores its passed arguments and always overwrites them from environment variables; missing/invalid env vars trigger `assert` failures.
- `AWS_BASTION_PORT` must be set; if absent it defaults to `-42` and will fail the assertion.
