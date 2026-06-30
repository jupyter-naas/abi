"""EventService — durable event log + live bus broadcast.

Responsibilities:
- Persist each published event to the SQLite-backed log (durability).
- Broadcast each published event on the BusService topic (live signaling).
- Reconstruct stored events back into their LogProcess subclass instances on read.

Subscriptions are live-only: subscribers connected at publish time receive the
event via the bus. Late or restarted subscribers catch up via
`query_for_consumer`, which uses a per-(consumer_id, event_type) cursor.
"""

from __future__ import annotations

import datetime
import hashlib
from threading import Thread
from typing import Any, Callable, Iterator

from naas_abi_core import logger
from naas_abi_core.services.bus.BusService import BusService
from naas_abi_core.services.event import EventCodec, EventFilter
from naas_abi_core.services.event.EventPort import (
    IEventAdapter,
    IEventService,
    InvalidEventError,
    StoredEvent,
)
from naas_abi_core.services.event.ontologies.modules.EventOntology import LogProcess
from naas_abi_core.services.ServiceBase import ServiceBase


def class_iri_to_topic(class_iri: str) -> str:
    """Map a class IRI to a bus-safe topic name.

    RabbitMQ topic names dislike `://`, `#`, and spaces; we hash the IRI to a
    short, deterministic, ASCII-only string.
    """
    return "evt." + hashlib.sha256(class_iri.encode("utf-8")).hexdigest()[:32]


def _build_subclass_index(root: type = LogProcess) -> dict[str, type]:
    """Walk all LogProcess subclasses and index them by `_class_uri`."""
    index: dict[str, type] = {}

    def walk(cls: type) -> None:
        uri = getattr(cls, "_class_uri", None)
        if uri:
            index[str(uri)] = cls
        for sub in cls.__subclasses__():
            walk(sub)

    walk(root)
    return index


class EventService(ServiceBase, IEventService):
    def __init__(self, adapter: IEventAdapter, bus: BusService | None = None):
        super().__init__()
        self._adapter = adapter
        # `bus` may be passed explicitly (e.g. by EventFactory or in tests) or
        # left None and resolved lazily via wire_services() — the engine sets
        # `self._services`, from which we can pick up `services.bus`.
        self._explicit_bus = bus

    @property
    def _bus(self) -> BusService | None:
        if self._explicit_bus is not None:
            return self._explicit_bus
        if self.services_wired:
            # Fall back to engine-wired bus if available.
            try:
                return self.services.bus
            except AssertionError:
                return None
        return None

    # ------------------------------------------------------------------
    # publish
    # ------------------------------------------------------------------

    def publish(self, event: Any) -> StoredEvent:
        if not isinstance(event, LogProcess):
            raise InvalidEventError(
                f"publish() expects a LogProcess subclass instance, got {type(event).__name__}"
            )

        event_type = str(event._class_uri)
        event_id = str(event._uri)

        # Ensure `created_at` is always populated before we serialize, so it
        # round-trips through reconstruction. Caller-supplied values are kept.
        created_at = getattr(event, "created_at", None)
        if created_at is None:
            created_at = datetime.datetime.now()
            event.created_at = created_at
        timestamp = created_at.isoformat()

        payload = EventCodec.serialize(event)

        stored = self._adapter.append(event_id, event_type, timestamp, payload)

        if self._bus is not None:
            try:
                # Publish on the event-class topic. EventService events use
                # the bus's pub/sub semantics so every registered subscriber
                # receives the event (no competing-consumer races). The
                # event_id is the routing key — subscribers default to "#"
                # so they receive every event of this class.
                self._bus.publish(
                    topic=class_iri_to_topic(event_type),
                    routing_key=event_id,
                    payload=payload,
                )
            except Exception as exc:
                # Durability is the contract; bus failure must not lose the event.
                logger.warning(f"EventService: bus broadcast failed for {event_id}: {exc}")

        return stored

    # ------------------------------------------------------------------
    # query
    # ------------------------------------------------------------------

    def query(
        self,
        event_class: type[LogProcess] | None = None,
        since_seq: int | None = None,
        until_seq: int | None = None,
        since_timestamp: str | None = None,
        until_timestamp: str | None = None,
        filter: dict | None = None,
        limit: int | None = None,
    ) -> list[Any]:
        """Read events.

        ``filter`` is an EventBridge-style dict; see :mod:`EventFilter` for
        the supported syntax. Translated to SQLite JSON1 SQL — pushdown
        happens at the adapter, not in Python.
        """
        event_type = str(event_class._class_uri) if event_class is not None else None
        rows = self._adapter.query(
            event_type=event_type,
            since_seq=since_seq,
            until_seq=until_seq,
            since_timestamp=since_timestamp,
            until_timestamp=until_timestamp,
            json_filter=filter,
            limit=limit,
        )
        return [self._reconstruct(row, event_class) for row in rows]

    def iter_query(
        self,
        event_class: type[LogProcess] | None = None,
        since_seq: int | None = None,
        since_timestamp: str | None = None,
        until_timestamp: str | None = None,
        filter: dict | None = None,
        limit: int | None = None,
        batch_size: int = 500,
    ) -> Iterator[Any]:
        """Stream events matching the filters.

        Snapshot semantics: a max `seq` is captured at the first call and is
        used as the upper bound for the whole iteration. Events appended
        during iteration are not included.

        `limit` caps the total number of events yielded. `batch_size` is the
        SQL fetch size per round-trip.
        """
        if batch_size <= 0:
            raise ValueError("batch_size must be > 0")
        if limit is not None and limit <= 0:
            return

        event_type = str(event_class._class_uri) if event_class is not None else None
        snapshot_max = self._adapter.max_seq(event_type=event_type)
        cursor = since_seq if since_seq is not None else 0
        yielded = 0

        while cursor < snapshot_max:
            fetch_size = batch_size
            if limit is not None:
                fetch_size = min(batch_size, limit - yielded)
                if fetch_size <= 0:
                    return
            rows = self._adapter.query(
                event_type=event_type,
                since_seq=cursor,
                until_seq=snapshot_max,
                since_timestamp=since_timestamp,
                until_timestamp=until_timestamp,
                json_filter=filter,
                limit=fetch_size,
            )
            if not rows:
                break
            for row in rows:
                yield self._reconstruct(row, event_class)
                yielded += 1
                if limit is not None and yielded >= limit:
                    return
            cursor = rows[-1].seq

    def query_for_consumer(
        self,
        consumer_id: str,
        event_class: type[LogProcess],
        limit: int | None = None,
        filter: dict | None = None,
    ) -> list[Any]:
        rows = self._adapter.query_for_consumer(
            consumer_id=consumer_id,
            event_type=str(event_class._class_uri),
            limit=limit,
            json_filter=filter,
        )
        return [self._reconstruct(row, event_class) for row in rows]

    def iter_query_for_consumer(
        self,
        consumer_id: str,
        event_class: type[LogProcess],
        limit: int | None = None,
        batch_size: int = 500,
        filter: dict | None = None,
    ) -> Iterator[Any]:
        """Drain pending events for `consumer_id` in batches, advancing the cursor.

        `limit` caps the total number of events yielded (and the cursor only
        advances over events actually read). `batch_size` is the per-round-trip
        fetch size.
        """
        if batch_size <= 0:
            raise ValueError("batch_size must be > 0")
        if limit is not None and limit <= 0:
            return

        event_type = str(event_class._class_uri)
        yielded = 0
        while True:
            fetch_size = batch_size
            if limit is not None:
                fetch_size = min(batch_size, limit - yielded)
                if fetch_size <= 0:
                    return
            rows = self._adapter.query_for_consumer(
                consumer_id=consumer_id,
                event_type=event_type,
                limit=fetch_size,
                json_filter=filter,
            )
            if not rows:
                return
            for row in rows:
                yield self._reconstruct(row, event_class)
                yielded += 1
                if limit is not None and yielded >= limit:
                    return

    # ------------------------------------------------------------------
    # subscribe
    # ------------------------------------------------------------------

    def subscribe(
        self,
        event_class: type[LogProcess],
        callback: Callable[[Any], None],
        filter: dict | None = None,
    ) -> Thread:
        """Subscribe to live events.

        Each call to :meth:`subscribe` registers an independent listener:
        every subscriber receives every published event (Redis-pub/sub
        semantics), so two subscribers on the same event class don't compete.

        ``filter`` (optional) is evaluated in-memory against each incoming
        event; non-matching events skip the callback. Same dict syntax as
        :meth:`query`. Filtering happens client-side because the bus is just
        a transport — pre-filtering at publish-time would require the
        publisher to know each subscriber's filter.
        """
        if self._bus is None:
            raise RuntimeError("EventService.subscribe requires a BusService")

        topic = class_iri_to_topic(str(event_class._class_uri))

        def _on_message(payload: bytes) -> None:
            try:
                if filter:
                    # Fast path: evaluate filter against the raw JSON dict
                    # before the (more expensive) Pydantic reconstruction.
                    import json
                    if not EventFilter.matches(json.loads(payload), filter):
                        return
                row = StoredEvent(
                    id="",
                    event_type=str(event_class._class_uri),
                    seq=0,
                    timestamp="",
                    payload=payload,
                )
                instance = self._reconstruct(row, event_class)
                callback(instance)
            except Exception as exc:
                logger.exception(f"EventService: subscriber callback failed: {exc}")

        return self._bus.subscribe(topic, "#", _on_message)

    # ------------------------------------------------------------------
    # reconstruction
    # ------------------------------------------------------------------

    def _reconstruct(
        self, row: StoredEvent, hint_class: type[LogProcess] | None
    ) -> Any:
        """Rebuild a LogProcess instance from a stored JSON payload.

        Uses ``hint_class`` if given; otherwise EventCodec resolves the
        target class via the stored ``_class_uri`` (falling back to
        LogProcess). Unknown fields in the stored JSON are dropped to allow
        forward-compatible class evolution.
        """
        instance = EventCodec.deserialize(row.payload, hint_class=hint_class)
        object.__setattr__(instance, "_seq", row.seq)
        object.__setattr__(instance, "_stored_at", row.timestamp)
        return instance
