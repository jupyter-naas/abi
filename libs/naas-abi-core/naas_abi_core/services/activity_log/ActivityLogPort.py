from abc import ABC, abstractmethod
from datetime import datetime, timezone
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
        default_factory=lambda: datetime.now(timezone.utc)
    )
    correlation_id: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class ActivityLogQuery(BaseModel):
    """Optional filters for ``query``. All fields are AND-ed."""

    model_config = ConfigDict(extra="forbid")

    event_type: str | None = None
    since: datetime | None = None
    until: datetime | None = None
    limit: int | None = None


class IActivityLogAdapter(ABC):
    @abstractmethod
    def record(self, event: ActivityEvent) -> None:
        raise NotImplementedError()

    @abstractmethod
    def query(
        self, actor_id: str, query: ActivityLogQuery | None = None
    ) -> list[ActivityEvent]:
        raise NotImplementedError()

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

    @abstractmethod
    def list_actors(self) -> list[str]:
        raise NotImplementedError()

    @abstractmethod
    def shutdown(self) -> None:
        raise NotImplementedError()
