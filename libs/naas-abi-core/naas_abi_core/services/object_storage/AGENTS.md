# Object Storage Service — AGENTS.md

> Scope: `libs/naas-abi-core/naas_abi_core/services/object_storage/`. Canonical reference for agents.

## Purpose

S3-style blob storage facade with pluggable backends. Emits `ObjectPut` / `ObjectDeleted` events.

## Files

```
object_storage/
├── ObjectStoragePort.py            # IObjectStorageAdapter, IObjectStorageDomain, ObjectMetaData
├── ObjectStorageService.py         # public service + event publishing
├── ObjectStorageFactory.py
├── ObjectStorageService_test.py
├── adapters/secondary/
│   ├── ObjectStorageSecondaryAdapterFS.py
│   ├── ObjectStorageSecondaryAdapterS3.py
│   ├── ObjectStorageSecondaryAdapterNaas.py
│   └── ObjectStorageSecondaryAdapterR2.py
└── ontologies/                     # ObjectPut, ObjectDeleted
```

## Port (`ObjectStoragePort.py`)

```python
class IObjectStorageAdapter:
    def get_object(prefix: str, key: str) -> bytes
    def put_object(prefix: str, key: str, content: bytes) -> None
    def delete_object(prefix: str, key: str) -> None
    def list_objects(prefix: str, queue: Queue | None = None) -> list[str]
    def get_object_metadata(prefix: str, key: str) -> ObjectMetaData

class IObjectStorageDomain:  # identical signature surface
    ...

class ObjectMetaData(BaseModel):
    file_path: str
    file_name: str
    file_size_bytes: int
    created_time: ...
    modified_time: ...
    accessed_time: ...
    permissions: ...
    mime_type: str
    encoding: ...
```

## Service API (`ObjectStorageService.py`)

```python
get_object(prefix, key) -> bytes                   # normalises 'storage/' prefix
put_object(prefix, key, content)                   # → publishes ObjectPut
delete_object(prefix, key)                         # → publishes ObjectDeleted
list_objects(prefix="", queue=None) -> list[str]   # depth-1 listing
get_object_metadata(prefix, key) -> ObjectMetaData
```

## Available Adapters

| Adapter | Backend / Notes |
|---|---|
| `ObjectStorageSecondaryAdapterFS` | Local filesystem |
| `ObjectStorageSecondaryAdapterS3` | AWS S3 (boto3). `endpoint_url` enables MinIO |
| `ObjectStorageSecondaryAdapterNaas` | Naas workspace storage (wraps S3 with credential refresh) |
| `ObjectStorageSecondaryAdapterR2` | Cloudflare R2 (subclasses S3 adapter, derives endpoint from `account_id`, forces `region_name="auto"`) |

## Factory (`ObjectStorageFactory.py`)

```python
ObjectStorageFactory.ObjectStorageServiceFS(base_path)
ObjectStorageFactory.ObjectStorageServiceFS__find_storage(needle="storage")
ObjectStorageFactory.ObjectStorageServiceS3(
    access_key_id, secret_access_key, bucket_name, base_prefix, session_token=None,
)
ObjectStorageFactory.ObjectStorageServiceNaas(
    naas_api_key, workspace_id, storage_name, base_prefix="",
)
ObjectStorageFactory.ObjectStorageServiceR2(
    account_id, access_key_id, secret_access_key, bucket_name, base_prefix="",
)
```

## Tests

```bash
uv run pytest libs/naas-abi-core/naas_abi_core/services/object_storage/ObjectStorageService_test.py
uv run pytest libs/naas-abi-core/naas_abi_core/services/object_storage/adapters/secondary/ObjectStorageSecondaryAdapterFS_test.py
uv run pytest libs/naas-abi-core/naas_abi_core/services/object_storage/adapters/secondary/ObjectStorageSecondaryAdapterS3_test.py
```

## Adding a new adapter

1. Implement `IObjectStorageAdapter` in `adapters/secondary/<Name>.py`. All abstract methods, including streaming and recursive listing.
2. `list_objects` must implement **depth-1** semantics — list direct children of the given prefix, not the full subtree.
3. `get_object_metadata` must populate at least `file_path`, `file_name`, `file_size_bytes`, `mime_type`. Timestamps / permissions / encoding optional.
4. Add a `ObjectStorageFactory.<Name>(...)` builder.

## NATS RPC adapters

`adapters/primary/object_storage__primary_adapter__NATS.py` exposes the service's
protobuf endpoints. `adapters/secondary/ObjectStorageSecondaryAdapterNATSClient.py` implements the outbound
port. Wire contracts live under `naas_abi_core/proto/object_storage/v1/`.

Clients inherit connection, JWT renewal, deadlines, and error handling from
`naas_abi_core.engine.nats_rpc.NatsRPCClient`; keep domain conversion and exception
mapping in the adapter. Primaries use `respond_protobuf` for bounded replies.
The maximum message size is 8 MiB (or a lower broker limit); oversized replies
return non-retryable `PAYLOAD_TOO_LARGE`, and micro-service error headers raise
instead of becoming an empty success. Larger results require streaming or a
storage reference. No RPC is automatically replayed after transport failure:
a timeout can hide a completed operation. Reconcile its outcome before retrying.
`close()` releases only the client's transport, including for vector storage.

Run the colocated NATS tests with `--import-mode=importlib`; shared regressions
are in `engine/nats_rpc_test.py` and `engine/nats_rpc_integration_test.py`.
The latter uses a local `nats-server` executable without Docker.


Object GET/PUT facades now use `transfer/v1` under object-storage subjects. GET
reads the backend streaming port in bounded chunks; PUT stages chunks on temporary
disk and calls the streaming port only after an explicit start. The old unary
endpoints remain compatible and bounded. Transfer sessions are authenticated,
caller-bound, sequence-checked and never replayed. Configure capacities through
`nats.object_storage_streaming`; see the chunked-transfers ADR and standalone
`transfer_integration_test.py` for native-broker coverage.
