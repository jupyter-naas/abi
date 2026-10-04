"""Dataset facade: the generated proxy plus streamed queries."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

from naas_abi_proto.dataset.v1 import dataset_pb2 as pb

from naas_abi_sdk.services._dataset import DatasetService as _GeneratedDatasetService
from naas_abi_sdk.services._dataset_rows import decode_rows
from naas_abi_sdk.services._streams import each, open_stream

TRANSFER_PREFIX = "abi.svc.dataset.v1.transfer"


@dataclass
class RowStream:
    """A query's rows as they arrive (docs/adr/20261003_nats-streamed-results.md):
    ``rows`` is a single-use async iterator, valid inside the block."""

    columns: list[str]
    rows: AsyncIterator[dict[str, Any]]


class DatasetService(_GeneratedDatasetService):
    @asynccontextmanager
    async def query_stream(
        self, sql: str, *, namespace: str = "default", snapshot_id: int | None = None
    ) -> AsyncIterator[RowStream]:
        request = pb.QueryRequest(sql=sql, namespace=namespace, accept_json_rows=True)
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


async def _rows(frames: AsyncIterator[bytes]) -> AsyncIterator[dict[str, Any]]:
    async for frame in frames:
        for row in decode_rows(pb.QueryResult.FromString(frame)):
            yield row
