# TripleStoreFactory

## What it is
- A factory module that builds `TripleStoreService` instances backed by different secondary adaptors (Naas object storage, filesystem, AWS Neptune via SSH tunnel, Oxigraph, Apache Jena TDB2/Fuseki, Oxigraph embedded).

## Public API
- `class TripleStoreFactory`
  - `TripleStoreServiceNaas(naas_api_key: str, workspace_id: str, storage_name: str, base_prefix: str = "ontologies") -> TripleStoreService`
    - Creates a `TripleStoreService` using Naas object storage via `ObjectStorageFactory.ObjectStorageServiceNaas(...)`.
  - `TripleStoreServiceFilesystem(path: str) -> TripleStoreService`
    - Creates a `TripleStoreService` using a filesystem-based secondary adaptor rooted at `path`.
  - `TripleStoreServiceAWSNeptuneSSHTunnel(...) -> TripleStoreService`
    - Creates a `TripleStoreService` backed by `AWSNeptuneSSHTunnel`.
    - Note: despite having parameters, it reads all configuration from environment variables (see below).
  - `TripleStoreServiceOxigraph(oxigraph_url: str | None = None) -> TripleStoreService`
    - Creates a `TripleStoreService` backed by an Oxigraph HTTP endpoint.
  - `TripleStoreServiceApacheJenaTDB2(jena_tdb2_url: str | None = None) -> TripleStoreService`
    - Creates a `TripleStoreService` backed by an Apache Jena Fuseki (TDB2) dataset URL.
  - `TripleStoreServiceOxigraphEmbedded(store_path: str, graph_base_iri: str = "http://ontology.naas.ai/graph/default") -> TripleStoreService`
    - Creates a `TripleStoreService` backed by an embedded Oxigraph store at `store_path`.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.services.triple_store.TripleStoreService.TripleStoreService`
  - Secondary adaptors:
    - `TripleStoreService__SecondaryAdaptor__ObjectStorage`
    - `TripleStoreService__SecondaryAdaptor__Filesystem`
    - `AWSNeptuneSSHTunnel`
    - `Oxigraph`
    - `ApacheJenaTDB2`
    - `TripleStoreService__SecondaryAdaptor__OxigraphEmbedded`
  - `ObjectStorageFactory.ObjectStorageServiceNaas` for Naas-backed storage.

### Environment variables
- `TripleStoreServiceAWSNeptuneSSHTunnel` **requires** (asserted non-null):
  - `AWS_REGION`
  - `AWS_ACCESS_KEY_ID`
  - `AWS_SECRET_ACCESS_KEY`
  - `AWS_NEPTUNE_DB_INSTANCE_IDENTIFIER`
  - `AWS_BASTION_HOST`
  - `AWS_BASTION_PORT` (must be set; defaults to `-42` and is rejected)
  - `AWS_BASTION_USER`
  - `AWS_BASTION_PRIVATE_KEY`
- `TripleStoreServiceOxigraph`
  - `OXIGRAPH_URL` (default: `http://localhost:7878`)
- `TripleStoreServiceApacheJenaTDB2`
  - `JENA_TDB2_URL` (default: `http://localhost:3030/ds`)

## Usage
```python
from naas_abi_core.services.triple_store.TripleStoreFactory import TripleStoreFactory

# Oxigraph (HTTP)
ts = TripleStoreFactory.TripleStoreServiceOxigraph()

# Apache Jena Fuseki (TDB2)
ts_jena = TripleStoreFactory.TripleStoreServiceApacheJenaTDB2(
    jena_tdb2_url="http://localhost:3030/ds"
)

# Filesystem-backed store
ts_fs = TripleStoreFactory.TripleStoreServiceFilesystem(path="./data/triples")
```

## Caveats
- `TripleStoreServiceAWSNeptuneSSHTunnel(...)` ignores its function parameters and always reads configuration from environment variables; missing variables will trigger `assert` failures.
- `AWS_BASTION_PORT` must be set; otherwise it defaults to `-42` and fails the assertion.
