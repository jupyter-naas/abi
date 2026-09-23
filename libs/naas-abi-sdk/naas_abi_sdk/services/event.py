from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from naas_abi_sdk.services._codec import ServiceProxy
from naas_abi_sdk.services.models import StoredEvent


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
        stored = await self._request(
            "append",
            event_id=event.id,
            event_type=event.event_type,
            timestamp=event.timestamp,
            payload=payload,
        )
        try:
            await self._bus.publish(
                "evt." + hashlib.sha256(event.event_type.encode()).hexdigest()[:32],
                event.id,
                payload,
            )
        except Exception:
            logging.getLogger(__name__).warning(
                "Live event broadcast failed after durable append", exc_info=True
            )
        return stored

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
        return await self._bus.subscribe(
            "evt." + hashlib.sha256(_type(event_class).encode()).hexdigest()[:32], "#"
        )
