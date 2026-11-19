"""Analytics ports + HTTP/domain schemas.

The Pydantic models mirror the TypeScript contract in
``apps/web/src/components/analytics/types.ts``: they are the shape of the
scoped reads (``analytics__primary_adapter__scoped``) and of the tracker's
ingest (``POST /api/analytics/events``).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
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
    # Stamped by the server from the workspace (``POST /events``); a value sent
    # by the tracker is replaced.
    organization_id: str | None = None
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
    user_id: str | None = None
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


class PeriodInfo(BaseModel):
    """The calendar period a scoped response covers, in the organization's time zone."""

    period: str
    date_start: str  # ISO-8601 with the zone's offset
    date_end: str
    timezone: str
    granularity: Literal["hour", "day"]


class AnalyticsAccess(BaseModel):
    """What the caller may read of a scope's analytics (``GET .../analytics/access``)."""

    can_read: bool
    can_read_conversations: bool
    timezone: str


class OverviewResponse(BaseModel):
    kpi: OverviewKpi
    sessions_over_time: list[TimeseriesPoint]
    active_users_over_time: list[TimeseriesPoint]
    top_users: list[UserRow]
    top_pages: list[PageRow]
    workspace_activity: list[WorkspaceRow]
    recent_activity: list[AnalyticsEvent]
    period: PeriodInfo | None = None


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


class ChatRow(BaseModel):
    """One conversation surfaced from analytics ``page_viewed`` events.

    Derived from the analytics event stream and enriched at request time with
    ``message_count`` and ``chat_title`` from the chat database (single
    grouped/IN queries batched over every conversation in the list).
    """

    conversation_id: str
    title: str
    chat_title: str | None = None
    workspace_id: str | None = None
    workspace_name: str | None = None
    user_id: str | None = None
    user_email: str | None = None
    first_viewed_at: str
    last_viewed_at: str
    page_views: int
    message_count: int = 0


class ChatsResponse(BaseModel):
    chats: list[ChatRow]
    # Whether the caller may open a conversation's messages (``ReadAnalyticsConversation``).
    can_read_messages: bool = False


class ChatMessage(BaseModel):
    """Single message in a conversation (analytics-facing projection).

    ``metadata`` mirrors the JSON persisted on ``messages.metadata_`` — most
    importantly the ``steps`` list (tool calls, tool responses, agent routing
    steps) that drives the activity stream of an assistant turn.
    """

    id: str
    role: str
    content: str
    agent: str | None = None
    created_at: str | None = None
    metadata: dict[str, Any] | None = None


class ChatDetail(BaseModel):
    """Conversation + its messages, served to the analytics UI."""

    conversation_id: str
    workspace_id: str
    user_id: str
    title: str
    agent: str
    created_at: str | None = None
    updated_at: str | None = None
    messages: list[ChatMessage] = Field(default_factory=list)


class ChatTopRow(BaseModel):
    conversation_id: str
    title: str | None = None
    user_email: str | None = None
    workspace_name: str | None = None
    message_count: int
    likes: int = 0
    dislikes: int = 0
    agents: list[str] = []
    tools: list[str] = []
    last_message_at: str | None = None


class ChatAgentRow(BaseModel):
    agent: str
    messages: int
    chats: int


class ChatToolRow(BaseModel):
    tool_name: str
    uses: int


class ChatFeedbackRow(BaseModel):
    feedback_type: str
    count: int


class ChatAnalyticsKpi(BaseModel):
    num_chats: int
    num_messages: int
    last_message_sent: str | None = None
    chat_with_most_messages: dict | None = None
    messages_liked: int = 0
    messages_disliked: int = 0
    agents_used: int = 0
    most_agent_used: str | None = None
    tools_used: int = 0
    most_tool_used: str | None = None


class ChatAnalyticsResponse(BaseModel):
    kpi: ChatAnalyticsKpi
    messages_over_time: list[TimeseriesPoint]
    chats_over_time: list[TimeseriesPoint]
    top_agents: list[ChatAgentRow]
    top_tools: list[ChatToolRow]
    feedback_distribution: list[ChatFeedbackRow]
    top_chats: list[ChatTopRow]


class IngestResponse(BaseModel):
    ok: bool = True
    stored_at: str


# ---------------------------------------------------------------------------
# Domain exceptions
# ---------------------------------------------------------------------------


class AnalyticsDomainError(Exception):
    pass


class OutOfScope(AnalyticsDomainError):
    """A workspace, user or conversation the scope does not hold: answered 404.
    ``what`` names which (``"Workspace"``, ``"User"``)."""

    def __init__(self, what: str, identifier: str) -> None:
        super().__init__(f"{what} {identifier} is not in the scope")
        self.what = what


# ---------------------------------------------------------------------------
# Scoped analytics (epic #1533): domain values and ports
# ---------------------------------------------------------------------------

Period = Literal["today", "yesterday", "this_week", "this_month"]


@dataclass(frozen=True)
class AnalyticsScope:
    """What a scoped read may count: resolved on the server (primary adapter), never
    from a request value. Only events of ``member_ids`` in ``workspace_ids`` count.

    ``organization_id`` is the organization of the scope (the workspace's for a
    workspace scope, None for a workspace in no organization); ``timezone`` is that
    organization's.
    """

    kind: Literal["organization", "workspace"]
    organization_id: str | None
    workspace_ids: tuple[str, ...]
    member_ids: tuple[str, ...]
    timezone: str = "UTC"
    # The scope's workspaces each member holds a role in (the users directory).
    member_workspaces: dict[str, tuple[str, ...]] = field(
        default_factory=dict, compare=False, hash=False
    )

    def narrowed(
        self, *, workspace_id: str | None = None, user_id: str | None = None
    ) -> AnalyticsScope:
        """The scope cut to one workspace and/or one user, both of which it must
        hold (``OutOfScope`` otherwise)."""
        workspaces = self.workspace_ids
        members = self.member_ids
        if workspace_id is not None:
            if workspace_id not in workspaces:
                raise OutOfScope("Workspace", workspace_id)
            workspaces = (workspace_id,)
        if user_id is not None:
            if user_id not in members:
                raise OutOfScope("User", user_id)
            members = (user_id,)
        return AnalyticsScope(
            self.kind,
            self.organization_id,
            workspaces,
            members,
            self.timezone,
            {m: self.member_workspaces.get(m, ()) for m in members},
        )


@dataclass(frozen=True)
class Slot:
    """One bucket of a period's time series: ``label`` in the organization's time
    zone (``YYYY-MM-DDTHH`` or ``YYYY-MM-DD``), ``[start, end)`` in naive UTC."""

    label: str
    start: datetime
    end: datetime


@dataclass(frozen=True)
class PeriodWindow:
    """A calendar period resolved in a time zone: ``[start, end)`` in naive UTC (what
    the tables hold), the local bounds for display, and its buckets."""

    period: str
    timezone: str
    start: datetime
    end: datetime
    local_start: datetime
    local_end: datetime
    granularity: Literal["hour", "day"]
    slots: tuple[Slot, ...]

    def info(self) -> PeriodInfo:
        return PeriodInfo(
            period=self.period,
            date_start=self.local_start.isoformat(),
            date_end=self.local_end.isoformat(),
            timezone=self.timezone,
            granularity=self.granularity,
        )


@dataclass(frozen=True)
class RecordedEvent:
    """A tracker event as the rollups apply it: identity already set by the server
    (``user_id`` from the token, ``workspace_id`` kept only for a member,
    ``organization_id`` from the workspace). ``timestamp`` is naive UTC; ``payload``
    is the tracker payload without any email."""

    event_id: str
    timestamp: datetime
    session_id: str
    event_name: str
    user_id: str | None = None
    workspace_id: str | None = None
    organization_id: str | None = None
    page_path: str | None = None
    page_title: str | None = None
    device: str | None = None
    browser: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SessionAggregate:
    session_id: str
    user_id: str
    workspace_id: str
    started_at: datetime
    ended_at: datetime
    page_views: int
    events: int
    device: str | None
    browser: str | None


@dataclass(frozen=True)
class UserAggregate:
    user_id: str
    sessions: int
    page_views: int
    workspaces: int
    total_events: int
    last_seen: datetime | None


@dataclass(frozen=True)
class PageAggregate:
    page_path: str
    page_title: str
    views: int
    unique_users: int


@dataclass(frozen=True)
class WorkspaceAggregate:
    workspace_id: str
    active_users: int
    sessions: int
    events: int


@dataclass(frozen=True)
class OverviewAggregate:
    """The session figures of the overview and its series; active users, page views
    and workspaces are the sums of ``users`` and ``workspaces``, which it reads too."""

    total_sessions: int
    avg_session_duration_seconds: int
    returning_users: int
    sessions_per_slot: tuple[int, ...]
    users_per_slot: tuple[int, ...]


@dataclass(frozen=True)
class ConversationAggregate:
    conversation_id: str
    workspace_id: str
    user_id: str
    title: str
    agent: str
    created_at: datetime | None
    updated_at: datetime | None
    message_count: int


@dataclass(frozen=True)
class ChatTopAggregate:
    conversation_id: str
    workspace_id: str
    user_id: str
    title: str
    message_count: int
    likes: int
    dislikes: int
    agents: tuple[str, ...]
    tools: tuple[str, ...]
    last_message_at: datetime | None


@dataclass(frozen=True)
class ChatAggregate:
    num_chats: int
    num_messages: int
    likes: int
    dislikes: int
    last_message_at: datetime | None
    messages_per_slot: tuple[int, ...]
    chats_per_slot: tuple[int, ...]
    # (agent id, messages, chats), (tool, uses), (feedback type, count)
    agents: tuple[tuple[str, int, int], ...]
    tools: tuple[tuple[str, int], ...]
    feedback_types: tuple[tuple[str, int], ...]
    top_chats: tuple[ChatTopAggregate, ...]


class AnalyticsEventLogPort(ABC):
    """Where an ingested event is recorded first: the EventService log
    (``AnalyticsEventRecorded``), which the rollups' consumer reads."""

    @abstractmethod
    def save_event(self, event: dict[str, Any]) -> str:
        """Append one stamped tracker event to the log (never its email). Returns
        where it landed."""
        raise NotImplementedError


class AnalyticsEventPort(ABC):
    """Ingest side: where the tracker's events become rollups.

    ``apply_events`` is idempotent (an event already applied is skipped), so the
    consumer, a direct ingest and the backfill may all hand it the same event.
    """

    @abstractmethod
    async def apply_events(self, events: list[RecordedEvent], *, not_before: datetime) -> int:
        """Store and count the events not seen yet, newer than ``not_before``
        (naive UTC). Events with no organization get their workspace's. Returns how
        many were new."""
        raise NotImplementedError

    @abstractmethod
    async def purge_events(self, before: datetime) -> int:
        """Delete the raw events older than ``before`` (naive UTC); the rollups stay."""
        raise NotImplementedError

    @abstractmethod
    async def job_last_run(self, name: str) -> datetime | None:
        """When the job ``name`` last ran (naive UTC); None if never."""
        raise NotImplementedError

    @abstractmethod
    async def record_job_run(self, name: str, at: datetime) -> None:
        raise NotImplementedError

    @abstractmethod
    async def claim_job(self, name: str, *, now: datetime, every: float) -> bool:
        """Claim the run of a periodic job at ``now``: True for the one process that
        finds it never ran or last ran at least ``every`` seconds ago."""
        raise NotImplementedError


class AnalyticsQueryPort(ABC):
    """Read side: one bounded SQL query per figure, over the rollups of a scope and
    a period. Nothing reads the whole history."""

    # -- the scope's directory -------------------------------------------------

    @abstractmethod
    async def organization_timezone(self, organization_id: str) -> str | None:
        """The organization's time zone; None for an unknown organization."""
        raise NotImplementedError

    @abstractmethod
    async def organization_workspaces(self, organization_id: str) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    async def workspace_organization(self, workspace_id: str) -> tuple[bool, str | None]:
        """(whether the workspace exists, its organization)."""
        raise NotImplementedError

    @abstractmethod
    async def user_emails(self, user_ids: list[str]) -> dict[str, str]:
        raise NotImplementedError

    @abstractmethod
    async def workspace_names(self, workspace_ids: list[str]) -> dict[str, str]:
        raise NotImplementedError

    @abstractmethod
    async def agent_names(self, agent_ids: list[str]) -> dict[str, str]:
        raise NotImplementedError

    # -- rollups ---------------------------------------------------------------

    @abstractmethod
    async def overview(self, scope: AnalyticsScope, window: PeriodWindow) -> OverviewAggregate:
        raise NotImplementedError

    @abstractmethod
    async def users(self, scope: AnalyticsScope, window: PeriodWindow) -> list[UserAggregate]:
        raise NotImplementedError

    @abstractmethod
    async def sessions(
        self, scope: AnalyticsScope, window: PeriodWindow, *, limit: int
    ) -> list[SessionAggregate]:
        raise NotImplementedError

    @abstractmethod
    async def pages(self, scope: AnalyticsScope, window: PeriodWindow) -> list[PageAggregate]:
        raise NotImplementedError

    @abstractmethod
    async def workspaces(
        self, scope: AnalyticsScope, window: PeriodWindow
    ) -> list[WorkspaceAggregate]:
        raise NotImplementedError

    @abstractmethod
    async def events(
        self, scope: AnalyticsScope, window: PeriodWindow, *, limit: int
    ) -> list[dict[str, Any]]:
        """The raw events (tracker payloads, newest first) of the scope and period."""
        raise NotImplementedError

    @abstractmethod
    async def chat_page_views(self, scope: AnalyticsScope, window: PeriodWindow) -> dict[str, int]:
        """Page views of each conversation's page (``/chat/<conversation id>``)."""
        raise NotImplementedError

    # -- chats (the chat tables, read only) ------------------------------------

    @abstractmethod
    async def conversations(
        self, scope: AnalyticsScope, window: PeriodWindow, *, limit: int
    ) -> list[ConversationAggregate]:
        """Conversations of the scope updated in the period, most recent first."""
        raise NotImplementedError

    @abstractmethod
    async def conversation_in_scope(
        self, scope: AnalyticsScope, conversation_id: str
    ) -> ConversationAggregate | None:
        raise NotImplementedError

    @abstractmethod
    async def chat_analytics(
        self, scope: AnalyticsScope, window: PeriodWindow, *, top: int
    ) -> ChatAggregate:
        raise NotImplementedError
