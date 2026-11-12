from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from naas_abi_proto.event.v1 import event_pb2 as pb

from naas_abi_sdk.services._codec import ServiceProxy, message
from naas_abi_sdk.services._streams import open_stream
from naas_abi_sdk.services.models import StoredEvent
from naas_abi_sdk.transport import RPCError

TRANSFER_PREFIX = "abi.svc.event.v1.transfer"


@dataclass
class Event:
    """Portable event payload. Core ontology classes remain engine-specific."""

    event_type: str
    payload: dict[str, Any]
    id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


def _type(value):
    return str(getattr(value, "_class_uri", value)) if value is not None else None


def live_event_class(data: bytes) -> str | None:
    """The class IRI a live event declares (``_class_uri``), or None."""
    try:
        value = json.loads(data)
    except (TypeError, ValueError):
        return None
    found = value.get("_class_uri") if isinstance(value, dict) else None
    return found if isinstance(found, str) else None


class LiveEvents:
    """The live events of one type: a message of any other class is dropped,
    whoever put it on the type's topic."""

    def __init__(self, subscription: Any, event_type: str) -> None:
        self._subscription, self.event_type = subscription, event_type

    async def next_msg(self, timeout: float = 1.0) -> Any:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while True:
            remaining = max(deadline - loop.time(), 0.001)
            msg = await self._subscription.next_msg(timeout=remaining)
            if live_event_class(msg.data) == self.event_type:
                return msg

    @property
    async def messages(self) -> Any:
        async for msg in self._subscription.messages:
            if live_event_class(msg.data) == self.event_type:
                yield msg

    def __getattr__(self, name: str) -> Any:
        return getattr(self._subscription, name)


class EventService(ServiceProxy):
    domain = "event"

    def __init__(self, client, bus):
        super().__init__(client)
        self._bus = bus

    async def publish(self, event: Event) -> StoredEvent:
        if not isinstance(event, Event):
            raise TypeError("Use naas_abi_sdk.services.event.Event for portable events")
        payload = json.dumps(
            event.payload
            | {
                "_uri": event.id,
                "_class_uri": event.event_type,
                "created_at": event.timestamp,
            }
        ).encode()
        # The event service broadcasts the live copy once it is appended: a
        # module never publishes on the live topics itself.
        return await self._request(
            "append",
            event_id=event.id,
            event_type=event.event_type,
            timestamp=event.timestamp,
            payload=payload,
        )

    def _restore(self, rows, event_class):
        data = [json.loads(row.payload) for row in rows]
        if isinstance(event_class, type):
            return [event_class.model_validate(item) for item in data]
        return data

    async def query(
        self,
        event_class=None,
        since_seq: int | None = None,
        until_seq: int | None = None,
        since_timestamp: str | None = None,
        until_timestamp: str | None = None,
        filter: dict | None = None,
        limit: int | None = None,
        newest_first: bool = False,
        search: str | None = None,
    ) -> list[Any]:
        rows = await self._request(
            "query",
            event_type=_type(event_class),
            since_seq=since_seq,
            until_seq=until_seq,
            since_timestamp=since_timestamp,
            until_timestamp=until_timestamp,
            json_filter=filter,
            limit=limit,
            newest_first=newest_first,
            search=search,
        )
        return self._restore(rows, event_class)

    @asynccontextmanager
    async def query_stream(
        self,
        event_class=None,
        since_seq: int | None = None,
        until_seq: int | None = None,
        since_timestamp: str | None = None,
        until_timestamp: str | None = None,
        filter: dict | None = None,
        limit: int | None = None,
        newest_first: bool = False,
        search: str | None = None,
    ) -> AsyncIterator[AsyncIterator[Any]]:
        """``query``, restored as the caller iterates, inside the block. The highest ``seq`` is
        pinned when the block opens: events appended while it is read are not
        included. Leaving the block closes the session."""
        event_type = _type(event_class)
        upper = await self._request("max_seq", event_type=event_type)
        if until_seq is not None:
            upper = min(upper, until_seq)
        request = message(
            pb.QueryRequest,
            {
                "event_type": event_type,
                "since_seq": since_seq,
                "until_seq": upper,
                "since_timestamp": since_timestamp,
                "until_timestamp": until_timestamp,
                "json_filter": filter,
                "limit": limit,
                "newest_first": newest_first,
                "search": search,
            },
        )
        async with open_stream(
            self._client, TRANSFER_PREFIX, "query", request.SerializeToString()
        ) as frames:
            if frames is None:
                raise RPCError("UNAVAILABLE", "No engine streams events")
            yield self._restored(frames, event_class)

    async def _restored(
        self, frames: AsyncIterator[bytes], event_class
    ) -> AsyncIterator[Any]:
        async for frame in frames:
            rows = pb.StoredEvents.FromString(frame).events
            for item in self._restore(rows, event_class):
                yield item

    async def query_for_consumer(
        self,
        consumer_id: str,
        event_class,
        limit: int | None = None,
        filter: dict | None = None,
    ) -> list[Any]:
        return self._restore(
            await self._request(
                "query_for_consumer",
                consumer_id=consumer_id,
                event_type=_type(event_class),
                limit=limit,
                json_filter=filter,
            ),
            event_class,
        )

    async def seek_consumer_to_end(
        self, consumer_id: str, event_class
    ) -> dict[str, Any]:
        event_type = _type(event_class)
        seq = await self._request("max_seq", event_type=event_type)
        await self._request(
            "set_cursor", consumer_id=consumer_id, event_type=event_type, last_seq=seq
        )
        return {"consumer_id": consumer_id, "event_type": event_type, "last_seq": seq}

    async def subscribe(self, event_class, callback=None, filter=None):
        if callback is not None or filter is not None:
            raise NotImplementedError(
                "Consume the returned async subscription; callback/filter adapters are not implemented"
            )
        event_type = _type(event_class)
        return LiveEvents(
            await self._bus.subscribe(
                "evt." + hashlib.sha256(event_type.encode()).hexdigest()[:32], "#"
            ),
            event_type,
        )
