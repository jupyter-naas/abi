# CheckpointDocuments

## What it is
- A pure planning/decoding module for storing LangGraph checkpoints as *documents* using a stable schema (v2), with backward reads for schema v1.
- Provides:
  - A document schema (collections, refs, batching rules).
  - Write planning (what documents to create/update, and in what order).
  - Read resolution helpers (find referenced documents without deserializing).
  - Secret redaction during serialization.
  - Retention helpers to decide which checkpoints to keep and which documents can be pruned.

## Public API

### Constants
- `SCHEMA_VERSION = 2`
- Collection names:
  - `CHECKPOINTS = "langgraph_checkpoints_v2"`
  - `WRITES = "langgraph_writes_v2"`
  - `BLOBS = "langgraph_blobs_v2"`
  - `ITEMS = "langgraph_items_v2"`
  - `PARTS = "langgraph_parts_v2"`
  - Legacy:
    - `LEGACY_CHECKPOINTS = "langgraph_checkpoints_v1"`
    - `LEGACY_WRITES = "langgraph_writes_v1"`
- Size/batching parameters:
  - `PART_SIZE`, `INLINE_LIMIT`, `CHUNK_SIZE`, `READ_BUDGET`, `MAX_IN_VALUES`, etc.
- Secret marker:
  - `REDACTED_SECRET`

### Functions
- `next_version(current: Any) -> Any`
  - Computes the next channel version while preserving the thread’s version type (int vs `"<counter>.<random>"`-like string format).
- `redact_secrets(value: Any) -> Any`
  - Walks common containers/models and replaces secret-like objects (anything with `get_secret_value`) with a same-typed redacted marker.
- `kept_checkpoints(stored: Iterable[Retained], keep_last: int) -> frozenset[tuple[str, str]]`
  - Returns the `(checkpoint_ns, checkpoint_id)` pairs to retain for a thread, keeping root checkpoints plus subgraph steps linked to them.
- `created_before(created_at: datetime | str | None, cutoff: datetime) -> bool`
  - Compares document `created_at` (datetime or ISO string) to a cutoff; unknown/unparseable returns `False` (keep it).
- `collection_of(ref: str) -> str`
  - Maps a reference prefix (`b-`, `c-`, `e-`, `p-`) to its collection.
- Reading helpers (do not deserialize values):
  - `references(data: Mapping[str, Any]) -> list[tuple[str, int]]`
    - Extracts referenced document refs from a stored document, with estimated byte costs.
  - `batches(refs: Iterable[tuple[str, int]]) -> list[tuple[str, list[str]]]`
    - Groups refs into read batches constrained by `READ_BUDGET` and `MAX_IN_VALUES`.
  - `resolution(roots: Iterable[Mapping[str, Any]]) -> Generator[...]`
    - Generator that yields `(collection, refs)` to fetch, accepts found documents via `.send()`, and returns a dict of all fetched docs by `ref`. Raises if any referenced doc is missing.
  - `raw_value(stored: Mapping[str, Any], fetched: Mapping[str, Any]) -> dict[str, Any]`
    - Reconstructs a typed `{"kind","payload"}` value, joining parts if split.
  - `raw_channel_values(data: Mapping[str, Any], fetched: Mapping[str, Any]) -> dict[str, Any]`
    - Produces typed values for each channel; list channels are expanded to typed element lists.

### Classes
- `RedactingSerializer`
  - Wraps a LangGraph `SerializerProtocol`.
  - `dumps_typed(obj)`: redacts secrets before delegating.
  - `loads_typed(data)`: delegates unchanged.

- `Retained(NamedTuple)`
  - Fields: `checkpoint_ns`, `checkpoint_id`, `root_parent`
  - Minimal view used by retention logic.

- `RetentionReport` (dataclass)
  - Fields: `thread_id`, `keep_last`, `applied`, plus counters (`kept`, `checkpoints`, `writes`, `values`)
  - `as_dict()`: returns `dataclasses.asdict(self)`

- Planning types:
  - `Put(NamedTuple)`
    - `collection`, `key`, `data`, `if_version` (0=create-only, `None`=replace), `on_conflict` (`"keep"`/`"compare"`)
  - `Plan(NamedTuple)`
    - `puts` (ordered), `config` (RunnableConfig), `remember` (cache update tuple)
  - `Known(NamedTuple)`
    - `refs`: refs known to exist
    - `channels`: mapping `channel -> (version, checkpoint_entry_dict)`

- `KnownReferences`
  - Thread-safe bounded LRU cache of `Known` per `(thread_id, checkpoint_ns, checkpoint_id)`.
  - Methods:
    - `remember(key, known)`: store/refresh entry and evict LRU when over capacity.
    - `recall(thread_id, parent, ancestors) -> Known`: union refs across parent+ancestors; returns parent’s channels when available.
    - `forget(thread_id)`: drop all cached knowledge for a thread.

- `CheckpointDocuments`
  - Central schema/planning/decoding API for a stable `agent_id`.
  - Constructor:
    - `CheckpointDocuments(agent_id: str, serde: SerializerProtocol)`
      - Wraps `serde` in `RedactingSerializer`.
  - Key/scoping:
    - `key(*parts) -> str`: SHA-256 of JSON([agent_id, *parts]) for document keys.
    - `scope(config) -> dict[str,str]`: `{agent_id, thread_id, checkpoint_ns}` from `config["configurable"]`.
    - `thread_scope(thread_id) -> dict[str,str]`
    - `history_scope(config|None) -> dict[str,str]`: filters for listing (agent/thread/ns/checkpoint_id).
    - `checkpoint_key(config) -> str | None`: key for a named checkpoint or `None` for “latest”.
    - `config(data) -> RunnableConfig`: reconstructs `{"configurable": {...}}` from stored doc fields.
    - `pending_scope(data) -> dict[str,str]`: validates schema and returns SCOPE_FIELDS.
  - Retention support:
    - `retained(data, fetched) -> Retained`: extracts retention view from checkpoint doc; expects `fetched` to include metadata parts if split.
    - `metadata_roots(data) -> list[dict[str,Any]]`: returns roots to resolve before `retained` (metadata parts only).
  - Write planning:
    - `checkpoint_plan(config, checkpoint, metadata) -> Plan`
      - Produces ordered `Put`s:
        - referenced parts/items/chunks/blobs first
        - then the checkpoint document (`compare` on conflict, create-only)
      - Also returns a `remember` tuple to update `KnownReferences`.
    - `write_plan(config, writes, task_id, task_path="") -> list[Put]`
      - Plans pending write documents; large values may produce PARTS puts first.
      - Uses create-only for normal writes (`index >= 0`), replace for special negative indices.
  - Read decoding:
    - `restore(data, writes, fetched) -> CheckpointTuple`
      - Schema v2: reconstructs checkpoint and channel values via `raw_*` helpers and deserializes through `serde`.
      - Schema v1: uses `_legacy` (checkpoint snapshot inline).
      - Updates `KnownReferences` for later incremental writes.
    - `matches(metadata, filter) -> bool`
      - Helper for list filtering: all keys in `filter` must match metadata values.

## Configuration/Dependencies
- Requires `langgraph-checkpoint` (imports from `langgraph.checkpoint.*`).
- Expects an implementation of `langgraph.checkpoint.serde.base.SerializerProtocol`.
- The module is pure planning/decoding; actual I/O (RPC/DB/document service) is performed by separate saver implementations.

## Usage

```python
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from naas_abi_sdk.langgraph_documents import CheckpointDocuments

serde = JsonPlusSerializer()
docs = CheckpointDocuments(agent_id="my-agent", serde=serde)

# Build a minimal runnable config and checkpoint payload
config = {"configurable": {"thread_id": "t-1", "checkpoint_ns": ""}}
checkpoint = {
    "id": "cp-1",
    "channel_versions": {"x": 1},
    "channel_values": {"x": {"hello": "world"}},
}
metadata = {}

plan = docs.checkpoint_plan(config, checkpoint, metadata)

# Persist plan.puts (in order) using your document store, then:
# docs.known.remember(*plan.remember)  # typically done by the saver after successful writes
```

## Caveats
- `CheckpointDocuments` enforces a non-empty, stable `agent_id`; changing it changes all document keys.
- Secrets are intentionally not stored:
  - any object with `get_secret_value()` is replaced with `REDACTED_SECRET` on write via `RedactingSerializer`.
- `resolution(...)` raises `ValueError` if any referenced document is missing (stored checkpoints are expected to be complete).
