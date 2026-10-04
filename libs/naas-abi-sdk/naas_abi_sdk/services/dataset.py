"""Dataset facade: the generated proxy plus streamed queries."""

from __future__ import annotations

from collections.abc import AsyncIterable, AsyncIterator, Iterable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

from naas_abi_proto.dataset.rows import decode_row, encode_row
from naas_abi_proto.dataset.v1 import dataset_pb2 as pb

from naas_abi_sdk.services._codec import decode, message
from naas_abi_sdk.services._dataset import DatasetService as _GeneratedDatasetService
from naas_abi_sdk.services._streams import each, open_stream
from naas_abi_sdk.services.errors import domain_error
from naas_abi_sdk.services.models import DatasetInfo
from naas_abi_sdk.transport import RPCError

TRANSFER_PREFIX = "abi.svc.dataset.v1.transfer"


@dataclass
class RowStream:
    """A query's rows as they arrive (docs/adr/20261003_nats-streamed-results.md):
    ``rows`` is a single-use async iterator, valid inside the block."""

    columns: list[str]
    rows: AsyncIterator[dict[str, Any]]


class DatasetService(_GeneratedDatasetService):
    async def write_stream(
        self,
        name: str,
        rows: Iterable[dict[str, Any]] | AsyncIterable[dict[str, Any]],
        *,
        namespace: str = "default",
        mode: str = "append",
        snapshot_id: int | None = None,
    ) -> DatasetInfo:
        """``write`` for rows read once from a (sync or async) iterator, uploaded
        as they are read and committed in one snapshot: all or none
        (docs/adr/20261003_nats-streamed-results.md). ``ValueError`` for NaN
        or an infinity; nothing is written then."""
        request = message(
            pb.WriteRequest,
            {
                "name": name,
                "namespace": namespace,
                "mode": mode,
                "snapshot_id": snapshot_id,
            },
        )
        async with open_stream(
            self._client,
            TRANSFER_PREFIX,
            "write",
            request.SerializeToString(),
            upload=_lines(rows),
        ) as frames:
            if frames is None:
                raise RPCError("UNAVAILABLE", "No engine accepts streamed writes")
            frame = await anext(frames, None)
        if frame is None:
            raise RPCError("INTERNAL", "Streamed write ended without its result")
        response = pb.WriteResponse.FromString(frame)
        if response.HasField("error"):
            error = response.error.error
            raise domain_error(RPCError(error.code, error.message, response=response))
        return decode(response.info)

    @asynccontextmanager
    async def query_stream(
        self, sql: str, *, namespace: str = "default", snapshot_id: int | None = None
    ) -> AsyncIterator[RowStream]:
        request = pb.QueryRequest(sql=sql, namespace=namespace)
        if snapshot_id is not None:
            request.snapshot_id = snapshot_id
        async with open_stream(
            self._client, TRANSFER_PREFIX, "query", request.SerializeToString()
        ) as frames:
            if frames is None:  # an engine without the transfer endpoint
                result = await self.query(
                    sql, namespace=namespace, snapshot_id=snapshot_id
                )
                yield RowStream(list(result.columns), each(list(result.rows)))
                return
            header = pb.QueryResult.FromString(await anext(frames))
            yield RowStream(list(header.columns), _rows(frames))


async def _lines(
    rows: Iterable[dict[str, Any]] | AsyncIterable[dict[str, Any]],
) -> AsyncIterator[bytes]:
    # One JSON object per line: JSON escapes newlines inside strings.
    if isinstance(rows, AsyncIterable):
        async for row in rows:
            yield encode_row(row) + b"\n"
    else:
        for row in rows:
            yield encode_row(row) + b"\n"


async def _rows(frames: AsyncIterator[bytes]) -> AsyncIterator[dict[str, Any]]:
    async for frame in frames:
        for row in pb.QueryResult.FromString(frame).rows:
            yield decode_row(row)
