# DatasetService

## What it is
A dataset service facade that extends the generated `DatasetService` proxy with:
- Streamed dataset writes (`write_stream`) for iterables/async iterables of rows.
- Streamed query results (`query_stream`) yielding rows as they arrive.

## Public API

### `RowStream` (dataclass)
Represents a streamed query result.
- `columns: list[str]` — column names from the query result header.
- `rows: AsyncIterator[dict[str, Any]]` — single-use async iterator of decoded rows (only valid within the context manager block).

### `DatasetService` (class)
Extends `naas_abi_sdk.services._dataset.DatasetService`.

#### `await write_stream(name, rows, *, namespace="default", mode="append", snapshot_id=None) -> DatasetInfo`
Stream rows from a (sync or async) iterator to the backend and commit in a single snapshot (all-or-none).
- Parameters:
  - `name`: dataset name
  - `rows`: `Iterable[dict]` or `AsyncIterable[dict]`
  - `namespace`: namespace (default `"default"`)
  - `mode`: write mode (default `"append"`)
  - `snapshot_id`: optional snapshot id
- Returns: `DatasetInfo`
- Errors:
  - Raises `RPCError("UNAVAILABLE", ...)` if no engine accepts streamed writes.
  - Raises `RPCError("INTERNAL", ...)` if the stream ends without returning a result.
  - Raises a domain-specific error via `domain_error(...)` if the response contains an error.
  - May raise `ValueError` for NaN or infinity values (as documented in the method docstring).

#### `query_stream(sql, *, namespace="default", snapshot_id=None) -> AsyncContextManager[RowStream]`
Async context manager for streaming query results.
- Parameters:
  - `sql`: SQL query string
  - `namespace`: namespace (default `"default"`)
  - `snapshot_id`: optional snapshot id
- Yields: `RowStream(columns, rows_iterator)`
- Errors:
  - Raises `RPCError("UNAVAILABLE", ...)` if no engine hosts dataset streams.

## Configuration/Dependencies
- Uses protobuf messages from `naas_abi_proto.dataset.v1.dataset_pb2`:
  - `WriteRequest`, `WriteResponse`, `QueryRequest`, `QueryResult`
- Row encoding/decoding:
  - `encode_row` / `decode_row` from `naas_abi_proto.dataset.rows`
- Streaming transport:
  - `open_stream` from `naas_abi_sdk.services._streams`
  - Internal stream prefix: `abi.svc.dataset.v1.transfer`
- Error handling:
  - `RPCError` from `naas_abi_sdk.transport`
  - `domain_error` from `naas_abi_sdk.services.errors`
- Response decoding:
  - `decode` from `naas_abi_sdk.services._codec` (for `DatasetInfo`)

## Usage

### Stream write from an in-memory iterable
```python
import asyncio
from naas_abi_sdk.services.dataset import DatasetService

async def main():
    svc = DatasetService(...)  # created/configured elsewhere
    info = await svc.write_stream(
        name="events",
        rows=[{"id": 1, "type": "click"}, {"id": 2, "type": "view"}],
        namespace="default",
        mode="append",
    )
    print(info)

asyncio.run(main())
```

### Stream query results
```python
import asyncio
from naas_abi_sdk.services.dataset import DatasetService

async def main():
    svc = DatasetService(...)  # created/configured elsewhere
    async with svc.query_stream("select * from events", namespace="default") as result:
        print(result.columns)
        async for row in result.rows:
            print(row)

asyncio.run(main())
```

## Caveats
- `RowStream.rows` is a single-use async iterator intended to be consumed inside the `async with query_stream(...)` block.
- `write_stream` uploads rows as they are read; if invalid values (NaN/inf) occur, it may raise `ValueError` and write nothing (per docstring).
- If no backend engine supports the relevant streaming operation, an `RPCError("UNAVAILABLE", ...)` is raised.
