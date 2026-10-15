# DocumentCheckpointSaver

## What it is
- An **async LangGraph 3.x checkpoint saver** that persists checkpoints and task writes to the **Naas document service**.
- Designed for use with `graph.ainvoke(...)` / `graph.astream(...)`.
- Uses the document-service-backed schema defined in `naas_abi_sdk.langgraph_documents` (schema 2), with optional **read compatibility** for legacy schema 1.
- Does **not** connect to a database and does **not** fall back to local/in-memory storage.

## Public API

### Class: `DocumentCheckpointSaver(BaseCheckpointSaver)`
Checkpoint persistence implementation for LangGraph.

#### Constructor
- `DocumentCheckpointSaver(documents, *, agent_id, serde=None, legacy_reads=True)`
  - `documents`: `DocumentClient` or `DocumentService` (uses `.rpc` when a `DocumentService` is provided)
  - `agent_id`: stable identifier for the graph/agent; used to isolate state
  - `serde`: optional LangGraph serializer (`SerializerProtocol`)
  - `legacy_reads`: when `True`, can read schema 1 checkpoints if schema 2 is absent; continued writes proceed in schema 2

#### Methods (async)
- `setup() -> None`
  - Ensures required document collections exist (per `COLLECTIONS` in `naas_abi_sdk.langgraph_documents`).

- `aput(config, checkpoint, metadata, new_versions) -> RunnableConfig`
  - Persists a checkpoint and returns an updated `RunnableConfig` (as planned by the schema helper).

- `aput_writes(config, writes, task_id, task_path="") -> None`
  - Persists task writes for a given `task_id` (and optional `task_path`).

- `aget_tuple(config) -> CheckpointTuple | None`
  - Loads a specific checkpoint (if `checkpoint_id` is present in config) or the latest checkpoint for the thread/namespace scope.

- `alist(config, *, filter=None, before=None, limit=None) -> AsyncIterator[CheckpointTuple]`
  - Streams checkpoint history (schema 2 first, then legacy schema 1).
  - Supports:
    - `filter`: metadata filtering (delegated to schema matcher)
    - `before`: pagination/anchor via `before["configurable"]["checkpoint_id"]`
    - `limit`: max number of results (no results when `limit <= 0`)

- `adelete_thread(thread_id: str) -> None`
  - Deletes all documents for a thread across checkpoint, write, and value collections (including legacy collections).

#### Retention / Maintenance (async)
- `athread_ids() -> list[str]`
  - Lists thread IDs that have checkpoints for this `agent_id` (schema 2 or schema 1).

- `aprune(thread_id, *, keep_last, apply=True, grace=RETENTION_GRACE) -> RetentionReport`
  - Retention pruning for a thread:
    - Keeps newest `keep_last` checkpoints (and subgraph steps derived via `kept_checkpoints`)
    - Deletes older checkpoints (schema 2 + legacy), their writes, and unreferenced value documents
    - Keeps value documents created within `grace`
    - `apply=False` performs a dry-run count
  - Raises `ValueError` if `keep_last < 1`.

## Configuration/Dependencies
- Install: `naas-abi-sdk[langgraph]`
- Runtime dependencies (by import):
  - `langgraph.checkpoint.*` (LangGraph checkpoint interfaces)
  - `naas_abi_sdk.document.DocumentClient` or `naas_abi_sdk.services.document.DocumentService`
  - `naas_abi_proto.document.v1.document_pb2` and `naas_abi_proto.document.values` for request/encoding
  - `naas_abi_sdk.langgraph_documents` for schema, collection names, paging constants, and retention helpers
- Requires a namespace-bound document client/service capable of:
  - `ensure_collection`, `put`, `get`, `find`, `delete`
- Error handling relies on `naas_abi_sdk.transport.RPCError` codes (e.g. `COLLECTION_NOT_FOUND`, `DOCUMENT_NOT_FOUND`, `VERSION_CONFLICT`).

## Usage

```python
import asyncio

from naas_abi_sdk.document import DocumentClient
from naas_abi_sdk.langgraph import DocumentCheckpointSaver

async def main():
    # DocumentClient construction depends on your environment/config.
    documents = DocumentClient(...)  # provide transport/credentials/namespace as required

    saver = DocumentCheckpointSaver(documents, agent_id="my-agent")
    await saver.setup()

    # Pass `saver` into your LangGraph graph compilation / execution per LangGraph API.
    # Example (pseudo, depends on your graph setup):
    # graph = builder.compile(checkpointer=saver)
    # result = await graph.ainvoke({"input": "hello"}, config={"configurable": {"thread_id": "t1"}})

asyncio.run(main())
```

## Caveats
- **One active run per agent/thread is required** (as stated in the class docstring).
- Call **`setup()` before running** a graph to ensure collections exist.
- Deleting/pruning a thread assumes its runs are **stopped first** (`adelete_thread`, `aprune`).
- With `legacy_reads=True`, schema 1 checkpoints may be read, but subsequent persistence continues in **schema 2**.
- Conflict behavior:
  - On `VERSION_CONFLICT`, some writes compare content and will raise if divergent (per internal plan’s `on_conflict="compare"`); others may allow first-writer-wins semantics.
