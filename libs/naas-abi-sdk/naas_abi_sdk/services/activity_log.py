"""Activity log facade: the generated proxy plus streamed queries."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import replace

from naas_abi_proto.activity_log.v1 import activity_log_pb2 as pb

from naas_abi_sdk.services._activity_log import (
    ActivityLogService as _GeneratedActivityLogService,
)
from naas_abi_sdk.services._codec import decode, message
from naas_abi_sdk.services._streams import each, open_stream
from naas_abi_sdk.services.models import ActivityEvent, ActivityLogQuery
from naas_abi_sdk.transport import RPCError

TRANSFER_PREFIX = "abi.svc.activity_log.v1.transfer"


class ActivityLogService(_GeneratedActivityLogService):
    @asynccontextmanager
    async def query_stream(
        self, actor_id: str, query: ActivityLogQuery | None = None
    ) -> AsyncIterator[AsyncIterator[ActivityEvent]]:
        """``query``, read as the caller iterates, inside the block
        (docs/adr/20261003_nats-streamed-results.md). The snapshot is pinned
        when the block opens: events recorded while it is read are not
        included. Leaving the block closes the session."""
        newest = await self.query(
            actor_id, ActivityLogQuery(newest_first=True, limit=1)
        )
        if not newest or newest[0].seq is None:
            yield each([])
            return
        filters = query or ActivityLogQuery()
        bound = newest[0].seq + 1
        if filters.before_seq is not None:
            bound = min(bound, filters.before_seq)
        request = pb.QueryRequest(
            actor_id=actor_id,
            filter=message(
                pb.ActivityLogQueryFilter, replace(filters, before_seq=bound)
            ),
        )
        async with open_stream(
            self._client, TRANSFER_PREFIX, "query", request.SerializeToString()
        ) as frames:
            if frames is None:
                raise RPCError("UNAVAILABLE", "No engine streams activity logs")
            yield _events(frames)


async def _events(frames: AsyncIterator[bytes]) -> AsyncIterator[ActivityEvent]:
    async for frame in frames:
        for event in pb.ActivityEvents.FromString(frame).events:
            yield decode(event)
