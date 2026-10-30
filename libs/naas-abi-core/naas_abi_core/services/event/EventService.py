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
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from itertools import islice
from threading import Thread
from typing import Any

from naas_abi_core import logger
from naas_abi_core.engine.call_context import as_service_account, current_call_context
from naas_abi_core.services.bus.BusService import BusService
from naas_abi_core.services.event import EventCodec, EventFilter
from naas_abi_core.services.event.EventPort import (
    EventNotFoundError,
    EventTypeSummary,
    IEventAdapter,
    IEventService,
    InvalidEventError,
    StoredEvent,
)
from naas_abi_core.services.event.iam_catalog import CATALOG
from naas_abi_core.services.event.ontologies.modules.EventOntology import LogProcess
from naas_abi_core.services.iam.guard import ServiceGuard
from naas_abi_core.services.iam.listing import ResourceLister, named_lister
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


def _stamp(event: Any) -> None:
    """Who and where from the call's context, unless the event says otherwise."""
    context = current_call_context()
    served = context.user
    for field_name, value in (
        ("actor_user_id", served.id if served is not None else None),
        ("actor_container", context.container),
        ("triggered_via", context.triggered_via),
    ):
        if getattr(event, field_name, None) is None and value is not None:
            setattr(event, field_name, value)


def _type_not_found(event_type: str) -> Callable[[], EventNotFoundError]:
    return lambda: EventNotFoundError(f"No events of type {event_type}")


def _cursor_not_found(consumer_id: str, event_type: str) -> Callable[[], Exception]:
    return lambda: EventNotFoundError(
        f"No cursor of consumer {consumer_id} for {event_type}"
    )


class EventService(ServiceBase, IEventService):
    """The durable event log and its live broadcast, each operation authorized.

    Wired with IAM (an owner), it checks every call against the ``event``
    catalog: ``Append`` and ``Query`` on ``event_type/<class IRI>``, cursors on
    ``cursor/<consumer>/<type>``. A read with no event type returns only the
    types the caller may read. A facade over NATS is not wired, and
    the owner it calls checks. ``emit`` appends a kernel service's own audit
    event as the engine.
    """

    def __init__(self, adapter: IEventAdapter, bus: BusService | None = None):
        super().__init__()
        self._adapter = adapter
        self._guard = ServiceGuard.of(CATALOG, self)
        # `bus` may be passed explicitly (e.g. by EventFactory or in tests) or
        # left None and resolved lazily via wire_services() — the engine sets
        # `self._services`, from which we can pick up `services.bus`.
        self._explicit_bus = bus

    @property
    def adapter(self) -> IEventAdapter:
        """The wrapped secondary adapter -- public so callers (e.g.
        ``EngineNATSLoader``) can check what kind of adapter this service is
        backed by, mirroring ``ObjectStorageService.adapter``."""
        return self._adapter

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
            created_at = datetime.datetime.now(datetime.UTC)
            event.created_at = created_at
        timestamp = created_at.isoformat()

        _stamp(event)

        payload = EventCodec.serialize(event)

        self._require("Append", event_type)
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
            except Exception as exc:  # noqa: BLE001
                # Durability is the contract; bus failure must not lose the event.
                logger.warning(f"EventService: bus broadcast failed for {event_id}: {exc}")

        return stored

    def emit(self, event: Any) -> StoredEvent | None:
        """A kernel service's own audit event, for the operation it just served.

        Stamped with the call's user, workspace and trigger as ``publish`` does,
        then appended as the engine: the caller was authorized for the
        operation, not for writing the event log. Never raises: the operation is
        the source of truth, its event is best effort.
        """
        if isinstance(event, LogProcess):
            _stamp(event)
        try:
            with as_service_account("engine"):
                return self.publish(event)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                f"EventService: failed to emit {type(event).__name__}: {exc}"
            )
            return None

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
        newest_first: bool = False,
        search: str | None = None,
    ) -> list[Any]:
        """Read events.

        ``filter`` is an EventBridge-style dict; see :mod:`EventFilter` for
        the supported syntax. Translated to SQLite JSON1 SQL — pushdown
        happens at the adapter, not in Python.

        ``newest_first=True`` orders results by ``seq`` descending so ``limit``
        returns the most recent N matches (e.g. "last 100 of this event type").
        ``search`` is a case-insensitive substring matched against the raw event
        payload (keys and values).
        """
        event_type = str(event_class._class_uri) if event_class is not None else None
        rows = self._rows(
            "Query",
            event_type=event_type,
            since_seq=since_seq,
            until_seq=until_seq,
            since_timestamp=since_timestamp,
            until_timestamp=until_timestamp,
            json_filter=filter,
            limit=limit,
            newest_first=newest_first,
            search=search,
        )
        return [self._reconstruct(row, event_class) for row in rows]

    @contextmanager
    def query_stream(
        self,
        event_class: type[LogProcess] | None = None,
        since_seq: int | None = None,
        until_seq: int | None = None,
        since_timestamp: str | None = None,
        until_timestamp: str | None = None,
        filter: dict | None = None,
        limit: int | None = None,
        newest_first: bool = False,
        search: str | None = None,
    ) -> Iterator[Iterator[Any]]:
        """:meth:`query`, reconstructed as the caller iterates, inside the
        block. Events appended after the block opened are not included."""
        event_type = str(event_class._class_uri) if event_class is not None else None
        with self._row_stream(
            "QueryStream",
            event_type=event_type,
            since_seq=since_seq,
            until_seq=until_seq,
            since_timestamp=since_timestamp,
            until_timestamp=until_timestamp,
            json_filter=filter,
            limit=limit,
            newest_first=newest_first,
            search=search,
        ) as rows:
            yield (self._reconstruct(row, event_class) for row in rows)

    def iam_listers(self) -> dict[tuple[str, str], ResourceLister]:
        """What IAM lists of this service for the policy builder: its event types.
        Read unchecked: IAM filters it as the caller (``list_resources``)."""
        return {
            (CATALOG.service, "event_type"): named_lister(
                lambda query: self._adapter.list_event_types(),
                lambda summary: self._guard.name("event_type", summary.event_type),
                lambda summary: summary.event_type,
            )
        }

    def event_types(self) -> list[EventTypeSummary]:
        """The event types present that the caller may list."""
        return self._guard.filter(
            "ListEventTypes",
            "event_type",
            self._adapter.list_event_types(),
            lambda summary: summary.event_type,
        )

    def query_stored(
        self,
        event_type: str | None = None,
        since_seq: int | None = None,
        until_seq: int | None = None,
        limit: int | None = None,
        newest_first: bool = False,
        search: str | None = None,
        *,
        since_timestamp: str | None = None,
        until_timestamp: str | None = None,
        filter: dict | None = None,
    ) -> list[StoredEvent]:
        return self._rows(
            "Query",
            event_type=event_type,
            since_seq=since_seq,
            until_seq=until_seq,
            since_timestamp=since_timestamp,
            until_timestamp=until_timestamp,
            json_filter=filter,
            limit=limit,
            newest_first=newest_first,
            search=search,
        )

    @contextmanager
    def query_stored_stream(
        self,
        event_type: str | None = None,
        since_seq: int | None = None,
        until_seq: int | None = None,
        limit: int | None = None,
        newest_first: bool = False,
        search: str | None = None,
        *,
        since_timestamp: str | None = None,
        until_timestamp: str | None = None,
        filter: dict | None = None,
    ) -> Iterator[Iterator[StoredEvent]]:
        with self._row_stream(
            "QueryStream",
            event_type=event_type,
            since_seq=since_seq,
            until_seq=until_seq,
            since_timestamp=since_timestamp,
            until_timestamp=until_timestamp,
            json_filter=filter,
            limit=limit,
            newest_first=newest_first,
            search=search,
        ) as rows:
            yield rows

    # ------------------------------------------------------------------
    # stored-level operations: what a remote EventService asks of the log
    # (the event NATS endpoints)
    # ------------------------------------------------------------------

    def append_stored(
        self, event_id: str, event_type: str, timestamp: str, payload: bytes
    ) -> StoredEvent:
        self._require("Append", event_type)
        return self._adapter.append(
            event_id=event_id,
            event_type=event_type,
            timestamp=timestamp,
            payload=payload,
        )

    def max_seq(self, event_type: str | None = None) -> int:
        """The newest ``seq`` of a type; with no type, the newest of the types
        the caller may ask (0 when none), so it reveals no other type."""
        if event_type is not None:
            self._require("MaxSeq", event_type)
            return self._adapter.max_seq(event_type=event_type)
        allowed = self._allowed_types("MaxSeq")
        if allowed is None or allowed[0]:
            return self._adapter.max_seq(event_type=None)
        return max((self._adapter.max_seq(event_type=t) for t in allowed[1]), default=0)

    def get_cursor(self, consumer_id: str, event_type: str) -> int:
        self._require_cursor("GetCursor", consumer_id, event_type)
        return self._adapter.get_cursor(consumer_id, event_type)

    def set_cursor(self, consumer_id: str, event_type: str, last_seq: int) -> None:
        self._require_cursor("SetCursor", consumer_id, event_type)
        self._adapter.set_cursor(consumer_id, event_type, last_seq)

    def query_stored_for_consumer(
        self,
        consumer_id: str,
        event_type: str,
        limit: int | None = None,
        filter: dict | None = None,
    ) -> list[StoredEvent]:
        self._require_consumer(consumer_id, event_type)
        return self._adapter.query_for_consumer(
            consumer_id=consumer_id,
            event_type=event_type,
            limit=limit,
            json_filter=filter,
        )

    def get_stored(self, seq: int) -> StoredEvent:
        def not_found() -> EventNotFoundError:
            return EventNotFoundError(f"No event with seq {seq}")

        rows = self._adapter.query(since_seq=seq - 1, until_seq=seq, limit=1)
        if not rows or rows[0].seq != seq:
            raise not_found()
        # Invisible and missing look the same.
        self._guard.require(
            "Query", "event_type", rows[0].event_type, not_found=not_found
        )
        return rows[0]

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
        SQL fetch size per round-trip. Authorized when called, like ``query``.
        """
        if batch_size <= 0:
            raise ValueError("batch_size must be > 0")
        event_type = str(event_class._class_uri) if event_class is not None else None
        if event_type is not None:
            self._require("Query", event_type)
        return self._iter_query(
            event_class,
            event_type,
            since_seq,
            since_timestamp,
            until_timestamp,
            filter,
            limit,
            batch_size,
        )

    def _iter_query(
        self,
        event_class: type[LogProcess] | None,
        event_type: str | None,
        since_seq: int | None,
        since_timestamp: str | None,
        until_timestamp: str | None,
        filter: dict | None,
        limit: int | None,
        batch_size: int,
    ) -> Iterator[Any]:
        if limit is not None and limit <= 0:
            return
        snapshot_max = self._adapter.max_seq(event_type=event_type)
        cursor = since_seq if since_seq is not None else 0
        yielded = 0

        while cursor < snapshot_max:
            fetch_size = batch_size
            if limit is not None:
                fetch_size = min(batch_size, limit - yielded)
                if fetch_size <= 0:
                    return
            rows = self._rows(
                "Query",
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
        self._require_consumer(consumer_id, str(event_class._class_uri))
        rows = self._adapter.query_for_consumer(
            consumer_id=consumer_id,
            event_type=str(event_class._class_uri),
            limit=limit,
            json_filter=filter,
        )
        return [self._reconstruct(row, event_class) for row in rows]

    def seek_consumer_to_end(
        self, consumer_id: str, event_class: type[LogProcess]
    ) -> dict[str, Any]:
        """Jump ``consumer_id`` to the latest seq for ``event_class``.

        Pending events between the previous cursor and now are skipped
        permanently for this consumer. Returns ``cursor_before`` /
        ``cursor_after`` so callers can log how far the seek jumped.
        """
        event_type = str(event_class._class_uri)
        self._require_cursor("GetCursor", consumer_id, event_type)
        self._require_cursor("SetCursor", consumer_id, event_type)
        self._require("MaxSeq", event_type)
        before = self._adapter.get_cursor(consumer_id, event_type)
        mx = self._adapter.max_seq(event_type)
        if before != mx:
            self._adapter.set_cursor(consumer_id, event_type, mx)
        return {
            "consumer_id": consumer_id,
            "event_type": event_type,
            "cursor_before": before,
            "cursor_after": mx,
        }

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
        fetch size. Authorized when called, like ``query_for_consumer``.
        """
        if batch_size <= 0:
            raise ValueError("batch_size must be > 0")
        event_type = str(event_class._class_uri)
        self._require_consumer(consumer_id, event_type)
        return self._drain_for_consumer(
            consumer_id, event_class, event_type, limit, batch_size, filter
        )

    def _drain_for_consumer(
        self,
        consumer_id: str,
        event_class: type[LogProcess],
        event_type: str,
        limit: int | None,
        batch_size: int,
        filter: dict | None,
    ) -> Iterator[Any]:
        if limit is not None and limit <= 0:
            return
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
    # authorization
    # ------------------------------------------------------------------

    def _require(self, action: str, event_type: str) -> None:
        self._guard.require(
            action, "event_type", event_type, not_found=_type_not_found(event_type)
        )

    def _require_cursor(self, action: str, consumer_id: str, event_type: str) -> None:
        self._guard.require(
            action,
            "cursor",
            (consumer_id, event_type),
            not_found=_cursor_not_found(consumer_id, event_type),
        )

    def _require_consumer(self, consumer_id: str, event_type: str) -> None:
        """A consumer read: the type and the consumer's cursor on it."""
        self._require("QueryForConsumer", event_type)
        self._require_cursor("QueryForConsumer", consumer_id, event_type)

    def _allowed_types(self, action: str) -> tuple[bool, set[str]] | None:
        """For a read with no event type: whether every type present is
        allowed, and the allowed ones; None when this service checks nothing."""
        if not self._guard.enforcing:
            return None
        present = [s.event_type for s in self._adapter.list_event_types()]
        allowed = self._guard.filter(action, "event_type", present, lambda t: t)
        return len(allowed) == len(present), set(allowed)

    def _rows(
        self, action: str, *, event_type: str | None, **query: Any
    ) -> list[StoredEvent]:
        """Stored rows of one type, or of every type the caller may read.
        ``limit`` applies after filtering."""
        if event_type is not None:
            self._require(action, event_type)
            return self._adapter.query(event_type=event_type, **query)
        allowed = self._allowed_types(action)
        if allowed is None:
            return self._adapter.query(**query)
        everything, types = allowed
        if everything:
            # A type first appended after the types were listed stays out.
            return [r for r in self._adapter.query(**query) if r.event_type in types]
        rows = [
            row
            for t in sorted(types)
            for row in self._adapter.query(event_type=t, **query)
        ]
        rows.sort(key=lambda row: row.seq, reverse=bool(query.get("newest_first")))
        limit = query.get("limit")
        return rows if limit is None else rows[:limit]

    @contextmanager
    def _row_stream(
        self, action: str, *, event_type: str | None, **query: Any
    ) -> Iterator[Iterator[StoredEvent]]:
        """``_rows``, read as the caller iterates."""
        if event_type is not None:
            self._require(action, event_type)
            with self._adapter.query_stream(event_type=event_type, **query) as rows:
                yield rows
            return
        allowed = self._allowed_types(action)
        if allowed is None:
            with self._adapter.query_stream(**query) as rows:
                yield rows
            return
        everything, types = allowed
        limit = None if everything else query.pop("limit", None)
        with self._adapter.query_stream(**query) as rows:
            kept = (row for row in rows if row.event_type in types)
            yield kept if limit is None else islice(kept, limit)

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
        # Checked once, for the subscriber: live events are not checked one by one.
        self._require("Query", str(event_class._class_uri))

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
            except Exception as exc:  # noqa: BLE001
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
