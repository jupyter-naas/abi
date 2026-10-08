from abc import ABC, abstractmethod
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ActivityEvent(BaseModel):
    """A single activity log entry.

    ``actor_id`` is opaque — the core service never parses it. Callers
    pick a convention; the recommended one is ``"<namespace>:<id>"``
    (e.g. ``"user:abc-123"``, ``"service:triple_store"``, ``"anonymous"``).

    ``event_type`` is a dotted namespace string (e.g. ``"http.request"``,
    ``"triple_store.insert"``). The service never enumerates them.
    """

    model_config = ConfigDict(extra="forbid")

    actor_id: str
    event_type: str
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC)
    )
    correlation_id: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    # Assigned by the store, increasing per actor; set on events read back,
    # ignored on ``record``. Used to page through an actor's log.
    seq: int | None = None


class ActivityLogQuery(BaseModel):
    """Optional filters for ``query``. All fields are AND-ed.

    Paging: ``newest_first`` orders by ``seq`` descending (default ascending);
    ``before_seq`` / ``after_seq`` keep events strictly below / above a seq, so
    the last ``seq`` of a page is the cursor for the next one.
    """

    model_config = ConfigDict(extra="forbid")

    event_type: str | None = None
    since: datetime | None = None
    until: datetime | None = None
    limit: int | None = None
    newest_first: bool = False
    before_seq: int | None = None
    after_seq: int | None = None


STREAM_PAGE = 500  # events per page read by the default ``query_stream``

_Query = Callable[[str, "ActivityLogQuery | None"], "list[ActivityEvent]"]


def pin_snapshot(
    query: _Query, actor_id: str, filters: ActivityLogQuery | None
) -> ActivityLogQuery | None:
    """``filters`` bounded below the actor's newest event at this moment, so a
    stream opened now never includes events recorded while it is read;
    ``None`` when the actor has no events."""
    newest = query(actor_id, ActivityLogQuery(newest_first=True, limit=1))
    if not newest or newest[0].seq is None:
        return None
    filters = filters or ActivityLogQuery()
    bound = newest[0].seq + 1
    if filters.before_seq is not None:
        bound = min(bound, filters.before_seq)
    return filters.model_copy(update={"before_seq": bound})


def paged_events(
    query: _Query, actor_id: str, filters: ActivityLogQuery | None
) -> Iterator[ActivityEvent]:
    """The actor's events matching ``filters``, read ``STREAM_PAGE`` at a time
    by keyset on ``seq``; the snapshot is pinned when this is called."""
    pinned = pin_snapshot(query, actor_id, filters)
    if pinned is None:
        return iter(())
    return _pages(query, actor_id, pinned)


def _pages(
    query: _Query, actor_id: str, filters: ActivityLogQuery
) -> Iterator[ActivityEvent]:
    remaining = filters.limit
    while remaining is None or remaining > 0:
        page = STREAM_PAGE if remaining is None else min(STREAM_PAGE, remaining)
        rows = query(actor_id, filters.model_copy(update={"limit": page}))
        yield from rows
        if len(rows) < page:
            return
        if remaining is not None:
            remaining -= len(rows)
        cursor = "before_seq" if filters.newest_first else "after_seq"
        filters = filters.model_copy(update={cursor: rows[-1].seq})


class IActivityLogAdapter(ABC):
    @abstractmethod
    def record(self, event: ActivityEvent) -> None:
        raise NotImplementedError()

    @abstractmethod
    def query(
        self, actor_id: str, query: ActivityLogQuery | None = None
    ) -> list[ActivityEvent]:
        raise NotImplementedError()

    @contextmanager
    def query_stream(
        self, actor_id: str, query: ActivityLogQuery | None = None
    ) -> Iterator[Iterator[ActivityEvent]]:
        """``query``, read as the caller iterates, inside the block
        (docs/adr/20261003_nats-streamed-results.md). Events recorded after
        the block opened are not included, so the stream always ends. This
        default reads ``STREAM_PAGE`` events at a time by keyset on ``seq``,
        holding no lock between pages."""
        yield paged_events(self.query, actor_id, query)

    @abstractmethod
    def list_actors(self) -> list[str]:
        raise NotImplementedError()

    @abstractmethod
    def shutdown(self) -> None:
        raise NotImplementedError()


class IActivityLogDomain(ABC):
    @abstractmethod
    def record(self, event: ActivityEvent) -> None:
        raise NotImplementedError()

    @abstractmethod
    def query(
        self, actor_id: str, query: ActivityLogQuery | None = None
    ) -> list[ActivityEvent]:
        raise NotImplementedError()

    @contextmanager
    def query_stream(
        self, actor_id: str, query: ActivityLogQuery | None = None
    ) -> Iterator[Iterator[ActivityEvent]]:
        """``query``, read as the caller iterates, inside the block; events
        recorded after the block opened are not included."""
        yield paged_events(self.query, actor_id, query)

    @abstractmethod
    def list_actors(self) -> list[str]:
        raise NotImplementedError()

    @abstractmethod
    def shutdown(self) -> None:
        raise NotImplementedError()
