# ActivityLogService

## What it is
- A facade over the generated Activity Log gRPC/NATS proxy that adds a streamed query API.
- Provides an async context manager that yields an async iterator of `ActivityEvent` records from a pinned snapshot.

## Public API
- `class ActivityLogService(_GeneratedActivityLogService)`
  - Extends the generated service `naas_abi_sdk.services._activity_log.ActivityLogService`.
  - `async def query_stream(self, actor_id: str, query: ActivityLogQuery | None = None) -> AsyncIterator[AsyncIterator[ActivityEvent]]`
    - Opens a streamed query session for an `actor_id`.
    - Snapshot semantics: determines a bound sequence at session start; events recorded while you iterate are not included.
    - Usage pattern: `async with service.query_stream(...) as events: async for e in events: ...`
    - If the engine does not provide streams, raises `RPCError("UNAVAILABLE", ...)`.
    - If there are no events (or no sequence available), yields an empty iterator.

## Configuration/Dependencies
- Depends on:
  - Generated protobufs: `naas_abi_proto.activity_log.v1.activity_log_pb2`
  - Generated service base: `naas_abi_sdk.services._activity_log.ActivityLogService`
  - Streaming utilities: `naas_abi_sdk.services._streams.open_stream`, `naas_abi_sdk.services._streams.each`
  - Encoding helpers: `naas_abi_sdk.services._codec.message`, `naas_abi_sdk.services._codec.decode`
  - Models: `naas_abi_sdk.services.models.ActivityEvent`, `ActivityLogQuery`
  - Transport error: `naas_abi_sdk.transport.RPCError`
- Uses stream subject prefix constant: `TRANSFER_PREFIX = "abi.svc.activity_log.v1.transfer"`.

## Usage
```python
import asyncio
from naas_abi_sdk.services.activity_log import ActivityLogService
from naas_abi_sdk.services.models import ActivityLogQuery

async def main():
    # service must be constructed the same way as the generated base service requires
    service = ActivityLogService(...)  # provide required client/transport args

    query = ActivityLogQuery(newest_first=False)  # optional filters
    async with service.query_stream(actor_id="actor-123", query=query) as events:
        async for event in events:
            print(event)

asyncio.run(main())
```

## Caveats
- Streamed results are snapshot-bounded: events added after the context manager opens are not included.
- If no engine provides streamed activity logs, `query_stream` raises `RPCError("UNAVAILABLE", "No engine streams activity logs")`.
- The stream may be empty if there are no events or if the newest event lacks a sequence (`seq`).
