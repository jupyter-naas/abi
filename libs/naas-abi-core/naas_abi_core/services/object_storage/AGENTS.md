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
├── iam_catalog.py                  # IAM action catalog; object_parts builds names
├── ObjectStorageService_authorization_test.py  # authorization contract
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

## Authorization

Every operation is checked in the domain service against IAM
(`ResourceGuard`, see "Enforcing in a data service" in
[`../iam/AGENTS.md`](../iam/AGENTS.md)),
for the caller of the current `CallContext`, so in process and over NATS answer
the same. The catalog is `iam_catalog.py`, registered by the serving engine at
boot. A caller who cannot see a resource gets `Exceptions.ObjectNotFound` (`OBJECT_NOT_FOUND`); one who can see it but not
act gets `PermissionDeniedError` (`PERMISSION_DENIED`). A service not wired into
an engine with IAM (a library use, a NATS facade whose server checks) does not
check. The contract test is `ObjectStorageService_authorization_test.py`: no policy, granted and denied
principals, in process and over NATS.

Resource type: `object/<path>` (`path`, placed): the prefix, stripped of its
leading and trailing `/`, joined to the key with one `/`. Nexus places its
`workspaces/<ws>/*` and `users/<user>/*` prefixes.

| Action | Level | Resource | Subject (`abi.svc.object_storage.v1.`) |
|---|---|---|---|
| `ListObjects` | list | each listed `object/<prefix>/<key>` | `list_objects` |
| `ListObjectsRecursive` | list | each listed object | `list_objects_recursive` |
| `GetObject` | read | `object/<prefix>/<key>` | `get_object` |
| `GetObjectMetadata` | read | `object/<prefix>/<key>` | `get_object_metadata` |
| `GetObjectStream` | read | `object/<prefix>/<key>` | transfer subjects, operation `get` |
| `PutObject` | write | `object/<prefix>/<key>` | `put_object` |
| `PutObjectStream` | write | `object/<prefix>/<key>` | transfer subjects, operation `put` |
| `DeleteObject` | write | `object/<prefix>/<key>` | `delete_object` |

* **Names are plain paths.** IAM checks `prefix/key` as written and a backend
  opens what the path resolves to, so `ws1/../ws2/x` would match `ws1/*` and
  open `ws2/x`, and a key of `/etc/passwd` would replace the filesystem
  adapter's base path. `ObjectStorageService` therefore refuses, before any
  check and for every caller, a prefix or key with a `.` or `..` segment or an
  empty segment (one trailing `/` on a prefix aside), and a leading `/`:
  `Exceptions.InvalidObjectPath`, `INVALID_ARGUMENT` over NATS. It strips only a
  leading `storage/` from a prefix, before the check in every operation
  (metadata included): the name IAM checks is the path the adapter opens.
* `list_objects` and `list_objects_recursive` keep the objects the caller may
  list; the caller's `queue` is filled after filtering. `list_objects` also
  shows a folder holding something the caller may list (one `filter` over
  `<folder>/_` names), and hides an entry a Deny names or a folder whose
  contents a Deny or a suspension hides (`<folder>/*`). Which entries are
  folders is the adapter's `folders(entries)`: by default those ending in `/`
  (S3); the filesystem adapter checks for directories. A caller with no Allow
  for the list action, or a suspended one, gets `ObjectNotFound`, as for a
  missing prefix.
* Streams (`get_object_stream`, `put_object_stream`) have their own actions
  (`GetObjectStream`, `PutObjectStream`).

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

Every primary runs its domain call as the verified caller: it authenticates the
request with `nats_rpc.authenticate_request` (built on `engine/nats_identity.py`,
it answers a refusal itself) and hands that `CallContext`
(`engine/call_context.py`) to its dispatcher. The actor is the
token's identity; the user it acts for is named by the token itself: a
delegated token (`abi:delegated:agent`, `act` the acting service, `sub` the user)
made by IAM's token exchange, never a header (the old `Abi-On-Behalf-Of` header is
refused); trace and container come from the request's `context`. Never read identity from request fields
(`principal_id` and `tenant_id` are reserved). Clients of `api` and `engine` send a
delegation for the current call's user, and the call's trace and container. The domain service authorizes the call on that context (see "Authorization").

Clients inherit connection, JWT renewal, deadlines, and error handling from
`naas_abi_core.engine.nats_rpc.NatsRPCClient`; keep domain conversion and exception
mapping in the adapter. Primaries use `respond_protobuf` for bounded replies.
Requests and replies above the broker limit (8 MiB, or lower) overflow as
transfer frames up to 256 MiB (`naas_abi_core/engine/nats_rpc.py`); above
that, at the overflow host's capacity, or with an older peer, the call fails
with non-retryable `PAYLOAD_TOO_LARGE`. Micro-service error headers raise
instead of becoming an empty success. Overflowed values are held whole in
memory; results that should not be require streaming or a storage reference. No RPC is automatically replayed after transport failure:
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
`nats.object_storage_streaming`; see the standalone
`transfer_integration_test.py` for native-broker coverage.
