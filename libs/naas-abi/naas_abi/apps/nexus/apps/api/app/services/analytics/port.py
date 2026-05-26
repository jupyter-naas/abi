"""Analytics service port + HTTP/domain schemas.

Mirrors the TypeScript contract in
``apps/web/src/app/analytics/lib/types.ts`` — the frontend reads the JSON
returned by the primary FastAPI adapter, so these Pydantic models are the
shape contract for both the prebuilt JSON aggregates persisted to object
storage and the responses served by the read endpoints.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Domain / transport schemas (Pydantic)
# ---------------------------------------------------------------------------

EventName = Literal[
    "session_started",
    "session_ended",
    "page_viewed",
    "workspace_opened",
    "workspace_created",
    "workspace_updated",
    "file_uploaded",
    "button_clicked",
    "search_performed",
    "export_clicked",
    "invite_sent",
    "login",
    "logout",
    "error_seen",
]


class AnalyticsEvent(BaseModel):
    """One raw analytics event emitted by the frontend tracker."""

    model_config = ConfigDict(extra="allow")

    event_id: str
    timestamp: str
    user_id: str | None = None
    user_email: str | None = None
    workspace_id: str | None = None
    workspace_name: str | None = None
    session_id: str
    event_name: str
    page_path: str | None = None
    page_title: str | None = None
    properties: dict[str, Any] | None = None
    device: str | None = None
    browser: str | None = None
    country: str | None = None
    referrer: str | None = None


class TimeseriesPoint(BaseModel):
    date: str
    value: float


class MostActiveWorkspace(BaseModel):
    id: str
    name: str
    events: int


class OverviewKpi(BaseModel):
    active_users: int
    total_sessions: int
    avg_sessions_per_user: float
    total_page_views: int
    workspaces_used: int
    avg_session_duration_seconds: int
    returning_users: int
    most_active_workspace: MostActiveWorkspace | None = None


class UserRow(BaseModel):
    user_id: str
    user_email: str
    sessions: int
    page_views: int
    workspaces: int
    last_seen: str
    total_events: int


class PageRow(BaseModel):
    page_path: str
    page_title: str
    views: int
    unique_users: int


class WorkspaceRow(BaseModel):
    workspace_id: str
    workspace_name: str
    active_users: int
    sessions: int
    events: int


class SessionRow(BaseModel):
    session_id: str
    user_email: str
    workspace_name: str | None = None
    started_at: str
    ended_at: str
    duration_seconds: int
    page_views: int
    events: int
    device: str | None = None
    browser: str | None = None


class WorkspaceRef(BaseModel):
    id: str
    name: str


class MostVisitedPage(BaseModel):
    path: str
    title: str
    views: int


class UserDetail(BaseModel):
    user_email: str
    user_id: str
    first_seen: str
    last_seen: str
    total_sessions: int
    total_page_views: int
    workspaces_used: list[WorkspaceRef]
    most_visited_page: MostVisitedPage | None = None
    sessions: list[SessionRow]
    pages: list[PageRow]
    events: list[AnalyticsEvent]


class OverviewResponse(BaseModel):
    kpi: OverviewKpi
    sessions_over_time: list[TimeseriesPoint]
    active_users_over_time: list[TimeseriesPoint]
    top_users: list[UserRow]
    top_pages: list[PageRow]
    workspace_activity: list[WorkspaceRow]
    recent_activity: list[AnalyticsEvent]


class UsersDirectoryEntry(BaseModel):
    user_email: str
    user_id: str
    workspace_ids: list[str] = Field(default_factory=list)


class UsersResponse(BaseModel):
    users: list[UserRow]
    directory: list[UsersDirectoryEntry]


class WorkspacesDirectoryEntry(BaseModel):
    workspace_id: str
    workspace_name: str


class WorkspacesResponse(BaseModel):
    workspaces: list[WorkspaceRow]
    directory: list[WorkspacesDirectoryEntry]


class SessionsResponse(BaseModel):
    sessions: list[SessionRow]


class PagesResponse(BaseModel):
    pages: list[PageRow]


class EventsResponse(BaseModel):
    events: list[AnalyticsEvent]


class Scenario(BaseModel):
    """A pre-computed analytics time window.

    ``date_start`` / ``date_end`` are anchored at rebuild time so the prebuilt
    aggregates always reflect a deterministic period.
    """

    scenario: str
    scenario_id: str
    date_start: str
    date_end: str


class ScenariosResponse(BaseModel):
    scenarios: list[Scenario]


class FileStats(BaseModel):
    file: str
    count: int
    duration_ms: int


class Metadata(BaseModel):
    updated_at: str
    duration_ms: int
    events: FileStats
    aggregates: list[FileStats]


class IngestResponse(BaseModel):
    ok: bool = True
    stored_at: str


class RebuildResponse(BaseModel):
    ok: bool = True
    metadata: Metadata


# ---------------------------------------------------------------------------
# Domain exceptions
# ---------------------------------------------------------------------------


class AnalyticsDomainError(Exception):
    pass


class UserDetailNotFound(AnalyticsDomainError):
    pass


# ---------------------------------------------------------------------------
# Secondary adapter port
# ---------------------------------------------------------------------------


class AnalyticsStoragePort(ABC):
    """Persistence contract for analytics events and prebuilt aggregates.

    The domain owns the file naming convention (which keys mean what) — the
    adapter only knows how to read/write opaque blobs by ``(dir, name)``.
    """

    # --- per-event pickle store ---------------------------------------------

    @abstractmethod
    def save_event(self, event: dict[str, Any]) -> str:
        """Persist one analytics event. Returns the storage key it landed at."""
        raise NotImplementedError

    @abstractmethod
    def list_events(self) -> list[dict[str, Any]]:
        """Return every persisted per-event payload, unordered."""
        raise NotImplementedError

    # --- JSON aggregates (overview.json, users.json, ...) -------------------

    @abstractmethod
    def save_json(self, file_name: str, data: Any) -> None:
        raise NotImplementedError

    @abstractmethod
    def load_json(self, file_name: str, fallback: Any = None) -> Any:
        raise NotImplementedError
