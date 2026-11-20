"""Analytics of an organization or a workspace (epic #1533).

The scope (``AnalyticsScope``: workspace ids and member ids) is resolved by the
primary adapter from IAM and the path, never from a query value; the period is
one of four calendar periods in the organization's time zone (``periods``).
Every figure is read through ``AnalyticsQueryPort`` (bounded SQL over the
rollups); this service only shapes the responses of the API contract and
resolves emails and workspace names at read time (events never store emails).
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import Awaitable, Callable, Sequence
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.analytics.periods import resolve_period
from naas_abi.apps.nexus.apps.api.app.services.analytics.port import (
    AnalyticsEvent,
    AnalyticsQueryPort,
    AnalyticsScope,
    ChatAgentRow,
    ChatAnalyticsKpi,
    ChatAnalyticsResponse,
    ChatFeedbackRow,
    ChatRow,
    ChatsResponse,
    ChatToolRow,
    ChatTopRow,
    EventsResponse,
    MostActiveWorkspace,
    MostVisitedPage,
    OverviewKpi,
    OverviewResponse,
    PageAggregate,
    PageRow,
    PagesResponse,
    PeriodWindow,
    SessionAggregate,
    SessionRow,
    SessionsResponse,
    TimeseriesPoint,
    UserAggregate,
    UserDetail,
    UserRow,
    UsersDirectoryEntry,
    UsersResponse,
    WorkspaceAggregate,
    WorkspaceRef,
    WorkspaceRow,
    WorkspacesDirectoryEntry,
    WorkspacesResponse,
)

TOP = 10
RECENT_ACTIVITY = 25
SESSIONS_LIMIT = 1000
CHATS_LIMIT = 500
TOP_CHATS = 100
USER_EVENTS = 200
EVENTS_MAX = 500

_CHAT_CONV_PATH_RE = re.compile(r"/chat/(conv-[^/?#]+)")


def _decorate_page_title(title: str, path: str) -> str:
    """Chat pages share the title "Chat": the conversation id from the path makes
    each conversation its own row."""
    m = _CHAT_CONV_PATH_RE.search(path or "")
    if not m:
        return title
    conv = m.group(1)
    return title if conv in title else f"{title} - {conv}"


def iso(moment: datetime | None) -> str:
    """A naive UTC timestamp as the tracker writes them (``...Z``); '' for none."""
    if moment is None:
        return ""
    if moment.tzinfo is not None:
        moment = moment.astimezone(UTC).replace(tzinfo=None)
    return moment.isoformat(timespec="milliseconds") + "Z"


def series(window: PeriodWindow, values: Sequence[int]) -> list[TimeseriesPoint]:
    """One point per bucket label; the repeated hour of a daylight saving change
    is one point."""
    found: dict[str, float] = {}
    for slot, value in zip(window.slots, values, strict=True):
        found[slot.label] = found.get(slot.label, 0) + value
    return [TimeseriesPoint(date=label, value=value) for label, value in found.items()]


# Opens a query port on a connection of its own (closed on exit): reads that may run
# at the same time as others.
QueriesFactory = Callable[[], AbstractAsyncContextManager[AnalyticsQueryPort]]


class ScopedAnalyticsService:
    def __init__(
        self,
        queries: AnalyticsQueryPort,
        now: Callable[[], datetime] | None = None,
        *,
        parallel: QueriesFactory | None = None,
    ) -> None:
        self.queries = queries
        self._now = now or (lambda: datetime.now(UTC))
        self._parallel = parallel

    async def _together(self, *reads: Callable[[AnalyticsQueryPort], Awaitable[Any]]) -> list[Any]:
        """The results of ``reads``, in order: at the same time, each on a connection of
        its own, when the service has ``parallel``; else one after another on
        ``queries`` (one connection runs one statement at a time)."""
        if self._parallel is None:
            return [await read(self.queries) for read in reads]
        factory = self._parallel

        async def apart(read: Callable[[AnalyticsQueryPort], Awaitable[Any]]) -> Any:
            async with factory() as queries:
                return await read(queries)

        return list(await asyncio.gather(*(apart(read) for read in reads)))

    def window(self, scope: AnalyticsScope, period: str) -> PeriodWindow:
        return resolve_period(period, scope.timezone, self._now())

    # -- shaping -----------------------------------------------------------------

    async def _emails(self, user_ids: list[str]) -> dict[str, str]:
        return await self.queries.user_emails(sorted(set(filter(None, user_ids))))

    async def _names(self, workspace_ids: list[str]) -> dict[str, str]:
        return await self.queries.workspace_names(sorted(set(filter(None, workspace_ids))))

    @staticmethod
    def _user_row(user: UserAggregate, emails: dict[str, str]) -> UserRow:
        return UserRow(
            user_id=user.user_id,
            user_email=emails.get(user.user_id, ""),
            sessions=user.sessions,
            page_views=user.page_views,
            workspaces=user.workspaces,
            last_seen=iso(user.last_seen),
            total_events=user.total_events,
        )

    @staticmethod
    def _page_row(page: PageAggregate) -> PageRow:
        return PageRow(
            page_path=page.page_path,
            page_title=_decorate_page_title(page.page_title, page.page_path),
            views=page.views,
            unique_users=page.unique_users,
        )

    @staticmethod
    def _workspace_row(row: WorkspaceAggregate, names: dict[str, str]) -> WorkspaceRow:
        return WorkspaceRow(
            workspace_id=row.workspace_id,
            workspace_name=names.get(row.workspace_id, row.workspace_id),
            active_users=row.active_users,
            sessions=row.sessions,
            events=row.events,
        )

    @staticmethod
    def _session_row(
        row: SessionAggregate, emails: dict[str, str], names: dict[str, str]
    ) -> SessionRow:
        return SessionRow(
            session_id=row.session_id,
            user_id=row.user_id or None,
            user_email=emails.get(row.user_id, "unknown"),
            workspace_name=names.get(row.workspace_id, row.workspace_id) or None,
            started_at=iso(row.started_at),
            ended_at=iso(row.ended_at),
            duration_seconds=max(0, int((row.ended_at - row.started_at).total_seconds())),
            page_views=row.page_views,
            events=row.events,
            device=row.device,
            browser=row.browser,
        )

    @staticmethod
    def _events(payloads: list[dict[str, Any]], emails: dict[str, str]) -> list[AnalyticsEvent]:
        found: list[AnalyticsEvent] = []
        for payload in payloads:
            uid = payload.get("user_id")
            data = {k: v for k, v in payload.items() if k != "user_email"}
            if uid and uid in emails:
                data["user_email"] = emails[uid]
            try:
                found.append(AnalyticsEvent.model_validate(data))
            except ValueError:
                continue
        return found

    # -- figures -----------------------------------------------------------------

    async def overview(self, scope: AnalyticsScope, window: PeriodWindow) -> OverviewResponse:
        aggregate, users, pages, workspaces, recent = await self._together(
            lambda q: q.overview(scope, window),
            lambda q: q.users(scope, window),
            lambda q: q.pages(scope, window),
            lambda q: q.workspaces(scope, window),
            lambda q: q.events(scope, window, limit=RECENT_ACTIVITY),
        )
        emails = await self._emails(
            [u.user_id for u in users[:TOP]] + [str(e.get("user_id") or "") for e in recent]
        )
        names = await self._names([w.workspace_id for w in workspaces])
        busiest = max(workspaces, key=lambda w: w.events, default=None)
        active_users = sum(1 for u in users if u.total_events)
        return OverviewResponse(
            kpi=OverviewKpi(
                active_users=active_users,
                total_sessions=aggregate.total_sessions,
                avg_sessions_per_user=(
                    round(aggregate.total_sessions / active_users, 1) if active_users else 0.0
                ),
                total_page_views=sum(u.page_views for u in users),
                workspaces_used=len(workspaces),
                avg_session_duration_seconds=aggregate.avg_session_duration_seconds,
                returning_users=aggregate.returning_users,
                most_active_workspace=(
                    MostActiveWorkspace(
                        id=busiest.workspace_id,
                        name=names.get(busiest.workspace_id, busiest.workspace_id),
                        events=busiest.events,
                    )
                    if busiest is not None
                    else None
                ),
            ),
            sessions_over_time=series(window, aggregate.sessions_per_slot),
            active_users_over_time=series(window, aggregate.users_per_slot),
            top_users=[self._user_row(u, emails) for u in users[:TOP]],
            top_pages=[self._page_row(p) for p in pages[:TOP]],
            workspace_activity=[self._workspace_row(w, names) for w in workspaces],
            recent_activity=self._events(recent, emails),
            period=window.info(),
        )

    async def users(self, scope: AnalyticsScope, window: PeriodWindow) -> UsersResponse:
        users = await self.queries.users(scope, window)
        emails = await self._emails(list(scope.member_ids))
        directory = sorted(
            (
                UsersDirectoryEntry(
                    user_id=uid,
                    user_email=emails.get(uid, ""),
                    workspace_ids=list(scope.member_workspaces.get(uid, ())),
                )
                for uid in scope.member_ids
            ),
            key=lambda entry: entry.user_email or entry.user_id,
        )
        return UsersResponse(users=[self._user_row(u, emails) for u in users], directory=directory)

    async def user_detail(self, scope: AnalyticsScope, window: PeriodWindow) -> UserDetail:
        """The detail of the one member ``scope`` is narrowed to."""
        (user_id,) = scope.member_ids
        users = await self.queries.users(scope, window)
        sessions = await self.queries.sessions(scope, window, limit=SESSIONS_LIMIT)
        pages = await self.queries.pages(scope, window)
        workspaces = await self.queries.workspaces(scope, window)
        events = await self.queries.events(scope, window, limit=USER_EVENTS)
        emails = await self._emails([user_id])
        names = await self._names([w.workspace_id for w in workspaces])
        user = users[0] if users else None
        first = min((s.started_at for s in sessions), default=None)
        last = max((s.ended_at for s in sessions), default=None)
        top_page = pages[0] if pages else None
        return UserDetail(
            user_email=emails.get(user_id, ""),
            user_id=user_id,
            first_seen=iso(first),
            last_seen=iso(last or (user.last_seen if user else None)),
            total_sessions=user.sessions if user else 0,
            total_page_views=user.page_views if user else 0,
            workspaces_used=[
                WorkspaceRef(id=w.workspace_id, name=names.get(w.workspace_id, w.workspace_id))
                for w in workspaces
            ],
            most_visited_page=(
                MostVisitedPage(
                    path=top_page.page_path,
                    title=_decorate_page_title(top_page.page_title, top_page.page_path),
                    views=top_page.views,
                )
                if top_page is not None
                else None
            ),
            sessions=[self._session_row(s, emails, names) for s in sessions],
            pages=[self._page_row(p) for p in pages],
            events=self._events(events, emails),
        )

    async def sessions(self, scope: AnalyticsScope, window: PeriodWindow) -> SessionsResponse:
        rows = await self.queries.sessions(scope, window, limit=SESSIONS_LIMIT)
        emails = await self._emails([r.user_id for r in rows])
        names = await self._names([r.workspace_id for r in rows])
        return SessionsResponse(sessions=[self._session_row(r, emails, names) for r in rows])

    async def pages(self, scope: AnalyticsScope, window: PeriodWindow) -> PagesResponse:
        return PagesResponse(
            pages=[self._page_row(p) for p in await self.queries.pages(scope, window)]
        )

    async def workspaces(
        self, scope: AnalyticsScope, window: PeriodWindow, *, directory: Sequence[str]
    ) -> WorkspacesResponse:
        rows = await self.queries.workspaces(scope, window)
        names = await self._names([r.workspace_id for r in rows] + list(directory))
        return WorkspacesResponse(
            workspaces=[self._workspace_row(r, names) for r in rows],
            directory=sorted(
                (
                    WorkspacesDirectoryEntry(workspace_id=wid, workspace_name=names.get(wid, wid))
                    for wid in directory
                ),
                key=lambda entry: entry.workspace_name.lower(),
            ),
        )

    async def events(
        self, scope: AnalyticsScope, window: PeriodWindow, *, limit: int
    ) -> EventsResponse:
        payloads = await self.queries.events(scope, window, limit=min(limit, EVENTS_MAX))
        emails = await self._emails([str(p.get("user_id") or "") for p in payloads])
        return EventsResponse(events=self._events(payloads, emails))

    async def chats(
        self, scope: AnalyticsScope, window: PeriodWindow, *, can_read_messages: bool
    ) -> ChatsResponse:
        conversations = await self.queries.conversations(scope, window, limit=CHATS_LIMIT)
        views = await self.queries.chat_page_views(scope, window)
        emails = await self._emails([c.user_id for c in conversations])
        names = await self._names([c.workspace_id for c in conversations])
        return ChatsResponse(
            chats=[
                ChatRow(
                    conversation_id=c.conversation_id,
                    title=c.title or c.conversation_id,
                    chat_title=c.title,
                    workspace_id=c.workspace_id,
                    workspace_name=names.get(c.workspace_id, c.workspace_id),
                    user_id=c.user_id,
                    user_email=emails.get(c.user_id),
                    first_viewed_at=iso(c.created_at),
                    last_viewed_at=iso(c.updated_at),
                    page_views=views.get(c.conversation_id, 0),
                    message_count=c.message_count,
                )
                for c in conversations
            ],
            can_read_messages=can_read_messages,
        )

    async def chat_analytics(
        self, scope: AnalyticsScope, window: PeriodWindow
    ) -> ChatAnalyticsResponse:
        found = await self.queries.chat_analytics(scope, window, top=TOP_CHATS)
        agent_ids = [agent for agent, _m, _c in found.agents]
        for chat in found.top_chats:
            agent_ids.extend(chat.agents)
        agent_names = await self.queries.agent_names(sorted(set(agent_ids)))
        emails = await self._emails([c.user_id for c in found.top_chats])
        names = await self._names([c.workspace_id for c in found.top_chats])

        # Agents by name: two ids may share one.
        by_name: dict[str, list[int]] = {}
        for agent, messages, chats in found.agents:
            counts = by_name.setdefault(agent_names.get(agent, agent), [0, 0])
            counts[0] += messages
            counts[1] += chats
        top_agents = sorted(
            (ChatAgentRow(agent=name, messages=m, chats=c) for name, (m, c) in by_name.items()),
            key=lambda row: (-row.messages, row.agent),
        )
        top_tools = [ChatToolRow(tool_name=name, uses=n) for name, n in found.tools]
        return ChatAnalyticsResponse(
            kpi=ChatAnalyticsKpi(
                num_chats=found.num_chats,
                num_messages=found.num_messages,
                last_message_sent=iso(found.last_message_at) or None,
                messages_liked=found.likes,
                messages_disliked=found.dislikes,
                agents_used=len(top_agents),
                most_agent_used=top_agents[0].agent if top_agents else None,
                tools_used=len(top_tools),
                most_tool_used=top_tools[0].tool_name if top_tools else None,
            ),
            messages_over_time=series(window, found.messages_per_slot),
            chats_over_time=series(window, found.chats_per_slot),
            top_agents=top_agents,
            top_tools=top_tools,
            feedback_distribution=[
                ChatFeedbackRow(feedback_type=name, count=n) for name, n in found.feedback_types
            ],
            top_chats=[
                ChatTopRow(
                    conversation_id=chat.conversation_id,
                    title=chat.title or chat.conversation_id,
                    user_email=emails.get(chat.user_id),
                    workspace_name=names.get(chat.workspace_id, chat.workspace_id),
                    message_count=chat.message_count,
                    likes=chat.likes,
                    dislikes=chat.dislikes,
                    agents=sorted({agent_names.get(a, a) for a in chat.agents}),
                    tools=list(chat.tools),
                    last_message_at=iso(chat.last_message_at) or None,
                )
                for chat in found.top_chats
            ],
        )
