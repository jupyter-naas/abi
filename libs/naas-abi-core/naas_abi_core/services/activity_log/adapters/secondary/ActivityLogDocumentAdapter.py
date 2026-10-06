"""Activity events stored in the Document Service.

Shared by every engine when the Document Service is (PostgreSQL), so deploys can
hand over without downtime (docs/adr/20261006_single-serving-engine.md).

Collections in the ``naas_abi_core.services.activity_log`` namespace:

- ``events``: one document per event, id ``<actor_id>#<seq, 20 digits>``.
- ``actors``: one document per actor, id ``<actor_id>``.

Each actor's ``seq`` is the next number after its newest event, written
create-only. A writer only picks n + 1 after event n is stored, so readers paging
by ``seq`` never miss an event stored late. A conflict (another engine recorded
first) reads the newest ``seq`` again and retries.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from datetime import UTC, datetime
from itertools import islice
from typing import Any

from naas_abi_core.services.activity_log.ActivityLogPort import (
    ActivityEvent,
    ActivityLogQuery,
    IActivityLogAdapter,
)
from naas_abi_core.services.document.DocumentPort import (
    MAX_PAGE_SIZE,
    CollectionSpec,
    FieldSpec,
    Predicate,
    Value,
    VersionConflict,
)
from naas_abi_core.services.document.DocumentService import DocumentService

NAMESPACE = "naas_abi_core.services.activity_log"
EVENTS = "events"
ACTORS = "actors"
MAX_ATTEMPTS = 20
REMEMBERED_ACTORS = 10_000  # newest seq kept in memory per actor


def _event_id(actor_id: str, seq: int) -> str:
    # The fixed-width suffix keeps ids distinct whatever the actor id contains.
    return f"{actor_id}#{seq:020d}"


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


class ActivityLogDocumentAdapter(IActivityLogAdapter):
    def __init__(self, documents: DocumentService | None = None) -> None:
        """``documents``: bound to this adapter's namespace; the engine binds it
        through ``wire_services`` instead."""
        self._documents = documents
        self._ensured = False
        self._newest: OrderedDict[str, int] = OrderedDict()
        self._locks: dict[str, threading.Lock] = {}
        self._registry = threading.Lock()

    def wire_services(self, services: Any) -> None:
        """Bind the engine's Document Service (``CacheService`` wires the same way)."""
        self._documents = services.document.for_namespace(NAMESPACE)
        self._ensured = False

    def _store(self) -> DocumentService:
        documents = self._documents
        if documents is None:
            raise RuntimeError(
                "The activity log's document adapter is not wired to a Document Service"
            )
        if not self._ensured:
            documents.ensure_collection(
                CollectionSpec(
                    name=EVENTS,
                    fields=(
                        FieldSpec(name="actor_id", type="string", indexed=True),
                        FieldSpec(name="seq", type="int", indexed=True),
                        FieldSpec(name="event_type", type="string", indexed=True),
                        FieldSpec(name="timestamp", type="datetime", indexed=True),
                    ),
                )
            )
            documents.ensure_collection(CollectionSpec(name=ACTORS))
            self._ensured = True
        return documents

    def _lock_for(self, actor_id: str) -> threading.Lock:
        with self._registry:
            return self._locks.setdefault(actor_id, threading.Lock())

    def _stored_newest(self, documents: DocumentService, actor_id: str) -> int:
        newest = documents.find(
            EVENTS,
            where=[("actor_id", "eq", actor_id)],
            order_by=("seq", "desc"),
            limit=1,
        ).items
        return int(newest[0].data["seq"]) if newest else 0  # type: ignore[arg-type]

    def _remember(self, actor_id: str, seq: int) -> None:
        with self._registry:
            self._newest[actor_id] = seq
            self._newest.move_to_end(actor_id)
            while len(self._newest) > REMEMBERED_ACTORS:
                self._newest.popitem(last=False)

    def record(self, event: ActivityEvent) -> None:
        documents = self._store()
        actor_id = event.actor_id
        with self._lock_for(actor_id):
            with self._registry:
                newest = self._newest.get(actor_id)
            if newest is None:
                try:
                    documents.put(
                        ACTORS, actor_id, {"actor_id": actor_id}, if_version=0
                    )
                except VersionConflict:
                    pass  # recorded before, by this engine or another
                newest = self._stored_newest(documents, actor_id)
            data: dict[str, Value] = {
                "actor_id": actor_id,
                "event_type": event.event_type,
                "timestamp": _utc(event.timestamp),
                "correlation_id": event.correlation_id,
                "attributes": event.attributes,
            }
            for _ in range(MAX_ATTEMPTS):
                seq = newest + 1
                try:
                    documents.put(
                        EVENTS,
                        _event_id(actor_id, seq),
                        {**data, "seq": seq},
                        if_version=0,
                    )
                except VersionConflict:  # another engine recorded first
                    newest = self._stored_newest(documents, actor_id)
                    continue
                self._remember(actor_id, seq)
                return
            raise RuntimeError(
                f"Could not record an activity event for {actor_id!r}: "
                f"{MAX_ATTEMPTS} concurrent writes in a row"
            )

    def query(
        self, actor_id: str, query: ActivityLogQuery | None = None
    ) -> list[ActivityEvent]:
        query = query or ActivityLogQuery()
        if query.limit is not None and query.limit <= 0:
            return []
        where: list[Predicate] = [("actor_id", "eq", actor_id)]
        if query.event_type is not None:
            where.append(("event_type", "eq", query.event_type))
        if query.since is not None:
            where.append(("timestamp", "gte", _utc(query.since)))
        if query.until is not None:
            where.append(("timestamp", "lte", _utc(query.until)))
        if query.before_seq is not None:
            where.append(("seq", "lt", query.before_seq))
        if query.after_seq is not None:
            where.append(("seq", "gt", query.after_seq))
        batch = min(query.limit or 500, MAX_PAGE_SIZE)
        documents = self._store().iterate(
            EVENTS,
            where=where,
            order_by=("seq", "desc" if query.newest_first else "asc"),
            batch=batch,
        )
        return [
            ActivityEvent(
                actor_id=actor_id,
                event_type=doc.data["event_type"],  # type: ignore[arg-type]
                timestamp=doc.data["timestamp"],  # type: ignore[arg-type]
                correlation_id=doc.data.get("correlation_id"),  # type: ignore[arg-type]
                attributes=doc.data.get("attributes") or {},  # type: ignore[arg-type]
                seq=doc.data["seq"],  # type: ignore[arg-type]
            )
            for doc in islice(documents, query.limit)
        ]

    def list_actors(self) -> list[str]:
        return [doc.id for doc in self._store().iterate(ACTORS)]

    def shutdown(self) -> None:
        """Nothing to release: the Document Service belongs to the engine."""
