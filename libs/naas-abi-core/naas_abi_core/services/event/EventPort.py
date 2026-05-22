from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from threading import Thread
from typing import Any, Callable, Iterator


class EventNotFoundError(Exception):
    pass


class InvalidEventError(Exception):
    """Raised when a published object is not a LogProcess subclass instance."""


@dataclass(frozen=True)
class StoredEvent:
    """Adapter-level representation of a persisted event.

    The service layer round-trips this back to an onto2py instance using the
    class IRI (`event_type`) to look up the target Python class.
    """

    id: str            # instance IRI (the LogProcess instance's _uri)
    event_type: str    # class IRI (the LogProcess subclass's _class_uri)
    seq: int           # global monotonic sequence
    timestamp: str     # ISO 8601
    payload: bytes     # serialized RDF graph (n-triples)


class IEventAdapter(ABC):
    """Secondary port: durable event log."""

    @abstractmethod
    def append(
        self,
        event_id: str,
        event_type: str,
        timestamp: str,
        payload: bytes,
    ) -> StoredEvent:
        """Persist one event. Returns the stored record with its assigned `seq`."""

    @abstractmethod
    def query(
        self,
        event_type: str | None = None,
        since_seq: int | None = None,
        until_seq: int | None = None,
        since_timestamp: str | None = None,
        until_timestamp: str | None = None,
        limit: int | None = None,
    ) -> list[StoredEvent]:
        """Read events matching the filters, ordered by `seq` ascending."""

    @abstractmethod
    def max_seq(self, event_type: str | None = None) -> int:
        """Return the highest `seq` currently stored (0 if empty).

        Used by iterators to capture a snapshot upper bound at start of
        iteration so that events appended during iteration are not included.
        """

    @abstractmethod
    def get_cursor(self, consumer_id: str, event_type: str) -> int:
        """Return last delivered seq for (consumer_id, event_type). 0 if unset."""

    @abstractmethod
    def query_for_consumer(
        self,
        consumer_id: str,
        event_type: str,
        limit: int | None = None,
    ) -> list[StoredEvent]:
        """Return events with seq > cursor, then advance cursor to the last seq read.

        Atomic: the cursor advance happens in the same transaction as the read,
        so a crashed caller cannot skip events — at-most-once delivery only if
        the caller processes successfully after this returns.
        """


class IEventService(ABC):
    """Primary port: event publishing, querying, and live subscription."""

    @abstractmethod
    def publish(self, event: Any) -> StoredEvent:
        """Persist `event` (a LogProcess subclass instance) and broadcast on the bus.

        Raises `InvalidEventError` if `event` is not a LogProcess subclass instance.
        """

    @abstractmethod
    def query(
        self,
        event_class: "type | None" = None,
        since_seq: int | None = None,
        until_seq: int | None = None,
        since_timestamp: str | None = None,
        until_timestamp: str | None = None,
        limit: int | None = None,
    ) -> list[Any]:
        """Return reconstructed event instances matching the filters."""

    @abstractmethod
    def iter_query(
        self,
        event_class: "type | None" = None,
        since_seq: int | None = None,
        since_timestamp: str | None = None,
        until_timestamp: str | None = None,
        limit: int | None = None,
        batch_size: int = 500,
    ) -> Iterator[Any]:
        """Stream events matching the filters as reconstructed instances.

        Snapshot semantics: the iterator captures the current max `seq` at the
        first call and stops once it has yielded everything up to that point.
        Events appended **during iteration are not included** — call again to
        pick them up. This guarantees deterministic termination.
        """

    @abstractmethod
    def query_for_consumer(
        self,
        consumer_id: str,
        event_class: type,
        limit: int | None = None,
    ) -> list[Any]:
        """Return undelivered events for `consumer_id` and advance the cursor."""

    @abstractmethod
    def iter_query_for_consumer(
        self,
        consumer_id: str,
        event_class: type,
        limit: int | None = None,
        batch_size: int = 500,
    ) -> Iterator[Any]:
        """Stream undelivered events for `consumer_id`, advancing the cursor.

        Drains all currently-pending events in batches of `batch_size`. The
        cursor is advanced per batch (same atomic semantics as `query_for_consumer`).
        Stops when the consumer is caught up.
        """

    @abstractmethod
    def subscribe(
        self,
        event_class: type,
        callback: Callable[[Any], None],
        routing_key: str = "#",
    ) -> Thread:
        """Subscribe to live events of `event_class` via the bus.

        Live-only — does not replay history. Use `query_for_consumer` for catch-up.
        """
