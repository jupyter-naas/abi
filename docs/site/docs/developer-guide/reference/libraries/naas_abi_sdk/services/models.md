# `models` (DTO dataclasses)

## What it is
A generated module of lightweight **dataclass DTOs** (data transfer objects) used across Naas ABI services. It also provides a `DTO_TYPES` mapping from fully-qualified ABI type names to the corresponding Python dataclass.

## Public API
### Dataclasses
- `ObjectMetaData`: File/object metadata (paths, sizes, timestamps, permissions, MIME).
- `ActivityEvent`: Activity log event (actor, type, timestamp, attributes, sequence).
- `ActivityLogQuery`: Activity log query filter (time range, pagination by sequence, ordering).
- `WorkspaceTemplate`: Workspace template reference (id/name/active version).
- `WorkspaceStatus`: Workspace state (phase, readiness, owner/template, created_at).
- `WorkspaceAccess`: Workspace access details (url, token, expiry).
- `Repo`: Source control repository metadata.
- `ContentEntry`: Repository content entry (name/path/type/size).
- `FileContent`: File content payload (text or bytes) plus binary flag.
- `Commit`: Commit metadata (sha/message/author/date).
- `Branch`: Branch metadata (name/commit sha/protected).
- `DiffFile`: Diff file entry (path/status/additions/deletions/patch/old_path).
- `Diff`: Collection of diff files (`files: list[DiffFile]`).
- `Comment`: Review/comment metadata (path/line/body/author/time).
- `Review`: Review metadata (state/body/author/submitted_at).
- `Check`: Check/run status and conclusion.
- `Proposal`: Proposal/PR metadata (branches, mergeability, approvals, url).
- `WorkflowRun`: CI workflow run metadata.
- `MergeResult`: Merge outcome (`merged`, optional `sha` and `message`).
- `ColumnSpec`: Dataset column spec (`name`, `type`).
- `PartitionSpec`: Dataset partition spec (`column`, `transform`).
- `DatasetSpec`: Dataset definition (namespace, columns, partitions, primary key).
- `DatasetInfo`: Dataset metadata plus `snapshot_id` and `location`.
- `DatasetSnapshotInfo`: Snapshot metadata (`snapshot_id`, `created_at`).
- `QueryResult`: Query response (`columns`, `rows` as list of dicts).
- `EmailAttachment`: Email attachment payload (bytes, MIME, inline flags).
- `SentEmailSummary`: Summary of a sent email.
- `SentEmail`: Sent email container (`summary`, `raw` bytes).
- `VectorDocument`: Vector store document (id, vector, metadata, payload).
- `SearchResult`: Vector search result (id, score, optional vector/metadata/payload).
- `VectorPage`: Paginated vector documents (`documents`, `next_cursor`).
- `CollectionInfo`: Vector collection metadata (dimension/metric/size).
- `StoredEvent`: Stored event record (id/type/seq/timestamp/payload bytes).
- `FileWrite`: Simple file write request (`path`, `content` as `str|bytes`).
- `FieldSpec`: Document DB field spec (`indexed`, `unique` flags).
- `CollectionSpec`: Document DB collection spec (fields and unique constraints).
- `Document`: Document DB record (id, data, timestamps, version).
- `Page`: Paginated documents (`items`, `cursor`).

### Module constants
- `DTO_TYPES: dict[str, type]`: Maps ABI type strings (e.g. `"abi.dataset.v1.DatasetSpec"`) to their Python dataclass type.

## Configuration/Dependencies
- Standard library only:
  - `dataclasses` (`@dataclass`, `field`)
  - `datetime` (`datetime`, `timezone`)
  - `typing` (`Any`)
- Some fields default to UTC “now”:
  - `ActivityEvent.timestamp` uses `datetime.now(timezone.utc)` via `default_factory`.

## Usage
```python
from datetime import datetime, timezone
from naas_abi_sdk.services.models import ActivityEvent, DTO_TYPES

# Construct a DTO
evt = ActivityEvent(actor_id="user-123", event_type="login")
assert evt.timestamp.tzinfo is not None  # defaults to UTC timestamp

# Resolve a DTO class by ABI type name
cls = DTO_TYPES["abi.activity_log.v1.ActivityEvent"]
evt2 = cls(actor_id="user-456", event_type="logout")
```

## Caveats
- This file is generated (“do not edit”); changes may be overwritten.
- Many timestamp/date fields are typed as `str | None` (not `datetime`), depending on the DTO.
- `DTO_TYPES` includes only the subset of dataclasses listed in its mapping (not every dataclass defined in the file).
