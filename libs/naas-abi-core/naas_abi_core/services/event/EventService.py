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
from typing import Any, Callable

from rdflib import Graph

from naas_abi_core import logger
from naas_abi_core.services.bus.BusService import BusService
from naas_abi_core.services.event.EventPort import (
    IEventAdapter,
    IEventService,
    InvalidEventError,
    StoredEvent,
)
from naas_abi_core.services.event.event_ontology import LogProcess
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
        self._bus = bus

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
        event_ts = getattr(event, "event_timestamp", None)
        timestamp = (
            event_ts.isoformat()
            if event_ts is not None
            else datetime.datetime.now().isoformat()
        )
        payload = event.rdf().serialize(format="nt", encoding="utf-8")

        stored = self._adapter.append(event_id, event_type, timestamp, payload)

        if self._bus is not None:
            try:
                self._bus.topic_publish(
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
        since_timestamp: str | None = None,
        until_timestamp: str | None = None,
        limit: int | None = None,
    ) -> list[Any]:
        event_type = str(event_class._class_uri) if event_class is not None else None
        rows = self._adapter.query(
            event_type=event_type,
            since_timestamp=since_timestamp,
            until_timestamp=until_timestamp,
            limit=limit,
        )
        return [self._reconstruct(row, event_class) for row in rows]

    def query_for_consumer(
        self,
        consumer_id: str,
        event_class: type[LogProcess],
        limit: int | None = None,
    ) -> list[Any]:
        rows = self._adapter.query_for_consumer(
            consumer_id=consumer_id,
            event_type=str(event_class._class_uri),
            limit=limit,
        )
        return [self._reconstruct(row, event_class) for row in rows]

    # ------------------------------------------------------------------
    # subscribe
    # ------------------------------------------------------------------

    def subscribe(
        self,
        event_class: type[LogProcess],
        callback: Callable[[Any], None],
        routing_key: str = "#",
    ) -> Thread:
        if self._bus is None:
            raise RuntimeError("EventService.subscribe requires a BusService")

        topic = class_iri_to_topic(str(event_class._class_uri))

        def _on_message(payload: bytes) -> None:
            try:
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

        return self._bus.topic_consume(topic, routing_key, _on_message)

    # ------------------------------------------------------------------
    # reconstruction
    # ------------------------------------------------------------------

    def _reconstruct(
        self, row: StoredEvent, hint_class: type[LogProcess] | None
    ) -> Any:
        """Rebuild a LogProcess instance from a stored RDF payload.

        If `hint_class` is given, use it. Otherwise look up the class by its IRI
        in the subclass index; if unknown, fall back to LogProcess.
        """
        cls: type[LogProcess]
        if hint_class is not None:
            cls = hint_class
        else:
            index = _build_subclass_index()
            cls = index.get(row.event_type, LogProcess)

        graph = Graph()
        graph.parse(data=row.payload, format="nt")

        # Find the event subject IRI in the graph if we don't have it (subscribe path).
        subject_iri = row.id
        if not subject_iri:
            from rdflib import RDF, URIRef

            for s, _, _ in graph.triples(
                (None, RDF.type, URIRef(row.event_type))
            ):
                subject_iri = str(s)
                break

        return cls.from_iri(subject_iri, query_executor=graph.query)
