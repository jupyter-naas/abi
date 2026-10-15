---
title: "naas_abi_proto"
---

# naas_abi_proto

The canonical v1 protobuf contracts of ABI's kernel services, with their
generated Python classes and type stubs. The only runtime dependency is
`protobuf`: the package imports neither ABI core, nor the SDK, nor NATS.
`naas-abi-core` and `naas-abi-sdk` both build on it, so an engine and a remote
module agree on every message.

```python
from naas_abi_proto.object_storage.v1 import object_storage_pb2

request = object_storage_pb2.PutObjectRequest(prefix="demo", key="hello", content=b"world")
```

Most code never touches these classes: the SDK's facades
(`self.engine.services.<name>`) take ordinary Python values. Use them through
`engine.rpc` or `ABIClient` when you need the raw contract.

## Packages

Each schema lives in `naas_abi_proto/<package>/v1/<package>.proto`, wire
package `abi.<package>.v1`, with `<package>_pb2.py` next to it.

| Package | What |
|---|---|
| `common` | `CallContext` (trace id, deadline, principal, workspace, tenant), carried by every request, and `CallError` (`code`, `message`, `retryable`), returned by every failed call. |
| `activity_log`, `cache`, `coding_environment`, `dataset`, `document`, `email`, `event`, `keyvalue`, `object_storage`, `secret`, `source_control`, `triple_store`, `vector_store` | The kernel services (below). |
| `model_registry` | Model lookup, chat, streaming and embeddings. |
| `discovery` | The module registry: `ModuleDescriptor` (agents, jobs, models, apps, dependencies), registration, leases, lookups, authorization. |
| `agent` | Remote agent invocation: submit, status, events, cancel. |
| `app` | Remote app requests and responses (`HttpRequest`, `HttpResponse`) and streamed bodies. |
| `transfer` | Chunked transfer sessions, used by object storage, models, RPC overflow and streamed results. |

Helpers next to the schemas: `dataset.rows` and `document.values` (portable
value encodings) and `vector_store.values`.

## Kernel service operations

The engine serves each operation on the NATS subject
`abi.svc.<service>.v1.<operation>`, as a request/reply call carrying the
service token in its headers.

| Service | Operations |
|---|---|
| `activity_log` | `record`, `query`, `list_actors`, `shutdown` |
| `cache` | `get`, `set`, `set_if_absent`, `delete`, `exists`, `describe`, `list_keys` |
| `coding_environment` | `ensure_user`, `list_templates`, `provision`, `start`, `stop`, `delete`, `list_environments`, `list_all_environments`, `get_status`, `get_logs`, `get_access` |
| `dataset` | `create`, `describe`, `list`, `write`, `query`, `flush`, `inlined_row_count`, `compact`, `list_snapshots`, `drop` |
| `document` | `ensure_collection`, `drop_collection`, `collections`, `collection_spec`, `namespaces`, `put`, `get`, `delete`, `find`, `count` |
| `email` | `send`, `list_sent`, `get_sent`, `delete_sent` |
| `event` | `append`, `query`, `max_seq`, `get_cursor`, `set_cursor`, `query_for_consumer`, `list_event_types` |
| `keyvalue` | `get`, `set`, `set_if_not_exists`, `delete`, `delete_if_value_matches`, `exists`, `list_keys`, `get_ttl` |
| `model_registry` | `list_models`, `resolve`, `chat`, `stream_open`, `stream_next`, `stream_close`, `embed` |
| `object_storage` | `get_object`, `put_object`, `delete_object`, `list_objects`, `list_objects_recursive`, `get_object_metadata` |
| `secret` | `get`, `set`, `remove`, `list` |
| `source_control` | `ensure_user`, `ensure_repo`, `list_repos`, `delete_repo`, `add_collaborator`, `list_contents`, `get_file`, `upsert_file`, `upsert_files`, `list_commits`, `list_branches`, `create_branch`, `delete_branch`, `get_diff`, `create_proposal`, `list_proposals`, `get_proposal`, `get_proposal_diff`, `list_proposal_commits`, `list_comments`, `list_reviews`, `add_comment`, `submit_review`, `list_checks`, `set_branch_protection`, `merge`, `list_workflow_runs`, `mint_git_token` |
| `triple_store` | `insert`, `remove`, `get`, `handle_view_event`, `query`, `query_view`, `get_subject_graph`, `create_graph`, `clear_graph`, `drop_graph`, `list_graphs` |
| `vector_store` | `initialize`, `create_collection`, `delete_collection`, `list_collections`, `store_vectors`, `search`, `get_vector`, `update_vector`, `delete_vectors`, `count_vectors`, `list_vectors`, `get_collection_info`, `close` |

The inventory is generated into `naas_abi_sdk.catalog.OPERATIONS`. Object
storage, models, triple store, dataset, vector store, event and activity log
also stream through transfer sessions on `abi.svc.<service>.v1.transfer` (see
[Large payloads](/architecture/remote-apps#large-payloads)).

Other subjects:

| Subject | What |
|---|---|
| `abi.discovery.<project>.v1.<operation>` | Discovery, served by the engine that hosts it. |
| `abi.agent.<project>.<instance>...`, `abi.mod.<project>.<instance>...` | A module instance's agents, models and apps (`...app.<name>.http`). |
| `abi.jobs.<project>.>` | Job triggers, schedules and cancels (stream `ABI_JOBS_<project>`). |
| `abi.rpc.overflow` | RPC overflow sessions. |

## Compatibility

Only additive changes belong in v1: new fields, messages and operations.
A breaking change gets v2 schemas and v2 subjects. The schemas carry no
validation annotations: the engine's adapters validate requests.

Generated files are checked in. To change a schema, edit the `.proto`, then
run `make generate` in `libs/naas-abi-proto` (pinned `grpcio-tools`), which
also regenerates the SDK's clients.
