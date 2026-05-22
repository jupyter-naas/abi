"""Analytics domain contracts.

Pure dataclasses and an abstract port. No infra imports here.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AnalyticsFilters:
    start_date: str | None = None
    end_date: str | None = None
    user_email: str | None = None
    workspace_id: str | None = None

    @classmethod
    def from_params(
        cls,
        start_date: str | None = None,
        end_date: str | None = None,
        user_email: str | None = None,
        workspace_id: str | None = None,
    ) -> AnalyticsFilters:
        def _norm(v: str | None) -> str | None:
            if v is None or v == "" or v == "all":
                return None
            return v

        return cls(
            start_date=_norm(start_date),
            end_date=_norm(end_date),
            user_email=_norm(user_email),
            workspace_id=_norm(workspace_id),
        )


@dataclass
class LogRecord:
    """Flat row materialised by the SPARQL adapter — one per nexus:Log."""

    event_id: str
    event_name: str
    timestamp: str
    session_id: str
    user_id: str | None = None
    user_email: str | None = None
    workspace_id: str | None = None
    workspace_name: str | None = None
    page_path: str | None = None
    page_title: str | None = None
    properties: dict[str, Any] | None = None
    referrer: str | None = None
    device: str | None = None
    browser: str | None = None
    country: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_name": self.event_name,
            "timestamp": self.timestamp,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "user_email": self.user_email,
            "workspace_id": self.workspace_id,
            "workspace_name": self.workspace_name,
            "page_path": self.page_path,
            "page_title": self.page_title,
            "properties": self.properties,
            "referrer": self.referrer,
            "device": self.device,
            "browser": self.browser,
            "country": self.country,
        }


class AnalyticsPort(ABC):
    """Read-only port to the analytics event store.

    Implementations must run a single source-of-truth query (typically
    SPARQL against the platform ontology + data graph) and return one
    :class:`LogRecord` per stored log. All KPI aggregation is done by
    :class:`AnalyticsService` on top of that flat list.
    """

    @abstractmethod
    def query_flat_events(self) -> list[LogRecord]:
        """Return every log entry the analytics service can see."""
        raise NotImplementedError
