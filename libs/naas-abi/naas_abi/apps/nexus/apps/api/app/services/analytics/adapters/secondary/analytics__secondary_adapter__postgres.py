"""SQL adapters of the scoped analytics: the rollups and the reads over them.

Like the other Nexus ``postgres`` adapters they run on SQLAlchemy, on PostgreSQL
in production and on SQLite (``abi dev``, tests): the only dialect-specific
pieces are the upsert statement, ``greatest``/``least`` and the seconds between
two timestamps (``_Dialect``).

Writes (``AnalyticsSecondaryAdapterPostgresEvents``) are idempotent: an event is
counted only when its raw row is new (``INSERT ... ON CONFLICT DO NOTHING
RETURNING``), so the consumer, a direct ingest and the backfill can all hand
over the same event. Reads (``AnalyticsSecondaryAdapterPostgresQueries``) are
one ``GROUP BY`` each over the rollups of a scope (workspace ids and member ids)
and a period; the chat figures read the chat tables, read only.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from collections.abc import Iterable, Sequence
from datetime import datetime, timedelta
from typing import Any

from naas_abi.apps.nexus.apps.api.app.models import (
    AgentConfigModel,
    AnalyticsEventModel,
    AnalyticsHourlyModel,
    AnalyticsJobModel,
    AnalyticsPageModel,
    AnalyticsSessionModel,
    AnalyticsUserHourlyModel,
    ConversationModel,
    MessageModel,
    MessageToolModel,
    OrganizationModel,
    UserModel,
    WorkspaceModel,
)
from naas_abi.apps.nexus.apps.api.app.services.analytics.port import (
    AnalyticsEventPort,
    AnalyticsQueryPort,
    AnalyticsScope,
    ChatAggregate,
    ChatTopAggregate,
    ConversationAggregate,
    OverviewAggregate,
    PageAggregate,
    PeriodWindow,
    RecordedEvent,
    SessionAggregate,
    UserAggregate,
    WorkspaceAggregate,
)
from sqlalchemy import ColumnElement, and_, case, delete, distinct, func, literal, select, update
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.ext.asyncio import AsyncSession

PAGE_VIEWED = "page_viewed"
# Rows per multi-row INSERT: well under SQLite's bound-parameter limit.
_CHUNK = 400
_CHAT_PATH = re.compile(r"/chat/(conv-[^/?#]+)")


def event_key(user_id: str | None, event_id: str) -> str:
    """The raw row's key: one per (user, tracker event id)."""
    return hashlib.sha256(f"{user_id or ''}\x1f{event_id}".encode()).hexdigest()


def _clip(value: str | None, size: int) -> str:
    return (value or "")[:size]


def _bounded_id(value: str | None) -> str:
    """An id fit for a 64-character key column: kept when short, hashed otherwise."""
    value = value or ""
    return value if len(value) <= 64 else hashlib.sha256(value.encode()).hexdigest()


def _hour(moment: datetime) -> datetime:
    return moment.replace(minute=0, second=0, microsecond=0)


def _chunks(rows: Sequence[Any], size: int = _CHUNK) -> Iterable[Sequence[Any]]:
    for index in range(0, len(rows), size):
        yield rows[index : index + size]


class _Dialect:
    """What differs between PostgreSQL and SQLite."""

    def __init__(self, db: AsyncSession) -> None:
        self.name = db.get_bind().dialect.name

    @property
    def postgres(self) -> bool:
        return self.name == "postgresql"

    def insert(self, table: Any) -> Any:
        return postgresql.insert(table) if self.postgres else sqlite.insert(table)

    def greatest(self, *values: Any) -> Any:
        return func.greatest(*values) if self.postgres else func.max(*values)

    def least(self, *values: Any) -> Any:
        return func.least(*values) if self.postgres else func.min(*values)

    def seconds(self, start: Any, end: Any) -> Any:
        if self.postgres:
            return func.extract("epoch", end - start)
        return (func.julianday(end) - func.julianday(start)) * 86400.0


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------


class AnalyticsSecondaryAdapterPostgresEvents(AnalyticsEventPort):
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _organizations_of(self, workspace_ids: set[str]) -> dict[str, str]:
        if not workspace_ids:
            return {}
        rows = await self.db.execute(
            select(WorkspaceModel.id, WorkspaceModel.organization_id).where(
                WorkspaceModel.id.in_(workspace_ids)
            )
        )
        return {ws: org for ws, org in rows.all() if org}

    async def apply_events(self, events: list[RecordedEvent], *, not_before: datetime) -> int:
        fresh: dict[str, RecordedEvent] = {}
        for event in events:
            if event.timestamp < not_before or not event.event_id or not event.event_name:
                continue
            fresh.setdefault(event_key(event.user_id, event.event_id), event)
        if not fresh:
            return 0
        dialect = _Dialect(self.db)
        orgs = await self._organizations_of(
            {e.workspace_id for e in fresh.values() if e.workspace_id and not e.organization_id}
        )

        def organization(event: RecordedEvent) -> str:
            return event.organization_id or orgs.get(event.workspace_id or "", "")

        table = AnalyticsEventModel.__table__
        inserted: set[str] = set()
        rows = [
            {
                "event_key": key,
                "timestamp": e.timestamp,
                "organization_id": organization(e),
                "workspace_id": e.workspace_id or "",
                "user_id": e.user_id or "",
                "session_id": _bounded_id(e.session_id),
                "event_name": _clip(e.event_name, 64),
                "page_path": _clip(e.page_path, 512),
                "payload": json.dumps(
                    {**e.payload, "organization_id": organization(e) or None},
                    sort_keys=True,
                    default=str,
                ),
            }
            for key, e in fresh.items()
        ]
        for chunk in _chunks(rows):
            statement = (
                dialect.insert(table)
                .values(list(chunk))
                .on_conflict_do_nothing(index_elements=["event_key"])
                .returning(table.c.event_key)
            )
            inserted.update((await self.db.execute(statement)).scalars().all())
        new = [fresh[key] for key in fresh if key in inserted]
        if not new:
            return 0
        await self._count(dialect, new, organization)
        await self._sessions(dialect, new, organization)
        await self._titles(dialect, new)
        await self.db.flush()
        return len(new)

    async def _count(self, dialect: _Dialect, events: list[RecordedEvent], organization) -> None:
        counts: dict[tuple[datetime, str, str, str, str, str], int] = defaultdict(int)
        for e in events:
            key = (
                _hour(e.timestamp),
                organization(e),
                e.workspace_id or "",
                e.user_id or "",
                _clip(e.event_name, 64),
                _clip(e.page_path, 512),
            )
            counts[key] += 1
        table = AnalyticsHourlyModel.__table__
        columns = (
            "bucket_hour",
            "organization_id",
            "workspace_id",
            "user_id",
            "event_name",
            "page_path",
        )
        rows = [{**dict(zip(columns, key, strict=True)), "count": n} for key, n in counts.items()]
        for chunk in _chunks(rows):
            statement = dialect.insert(table).values(list(chunk))
            statement = statement.on_conflict_do_update(
                index_elements=list(columns),
                set_={"count": table.c.count + statement.excluded.count},
            )
            await self.db.execute(statement)

        per_user: dict[tuple[datetime, str, str, str], list[int]] = defaultdict(lambda: [0, 0])
        for (hour, org, ws, user, name, _path), n in counts.items():
            totals = per_user[(hour, org, ws, user)]
            totals[0] += n
            if name == PAGE_VIEWED:
                totals[1] += n
        users = AnalyticsUserHourlyModel.__table__
        keys = ("bucket_hour", "organization_id", "workspace_id", "user_id")
        user_rows = [
            {**dict(zip(keys, key, strict=True)), "events": n, "page_views": views}
            for key, (n, views) in per_user.items()
        ]
        for chunk in _chunks(user_rows):
            statement = dialect.insert(users).values(list(chunk))
            statement = statement.on_conflict_do_update(
                index_elements=list(keys),
                set_={
                    "events": users.c.events + statement.excluded.events,
                    "page_views": users.c.page_views + statement.excluded.page_views,
                },
            )
            await self.db.execute(statement)

    async def _sessions(self, dialect: _Dialect, events: list[RecordedEvent], organization) -> None:
        found: dict[tuple[str, str], dict[str, Any]] = {}
        for e in sorted(events, key=lambda e: e.timestamp):
            if not e.session_id:
                continue
            key = (_bounded_id(e.session_id), e.workspace_id or "")
            row = found.get(key)
            if row is None:
                row = found[key] = {
                    "session_id": key[0],
                    "workspace_id": key[1],
                    "organization_id": organization(e),
                    "user_id": e.user_id or "",
                    "started_at": e.timestamp,
                    "ended_at": e.timestamp,
                    "page_views": 0,
                    "events": 0,
                    "device": _clip(e.device, 64) or None,
                    "browser": _clip(e.browser, 64) or None,
                }
            row["ended_at"] = e.timestamp
            row["events"] += 1
            if e.event_name == PAGE_VIEWED:
                row["page_views"] += 1
            row["user_id"] = row["user_id"] or e.user_id or ""
        table = AnalyticsSessionModel.__table__
        for chunk in _chunks(list(found.values())):
            statement = dialect.insert(table).values(list(chunk))
            new = statement.excluded
            statement = statement.on_conflict_do_update(
                index_elements=["session_id", "workspace_id"],
                set_={
                    "started_at": dialect.least(table.c.started_at, new.started_at),
                    "ended_at": dialect.greatest(table.c.ended_at, new.ended_at),
                    "page_views": table.c.page_views + new.page_views,
                    "events": table.c.events + new.events,
                    "device": func.coalesce(table.c.device, new.device),
                    "browser": func.coalesce(table.c.browser, new.browser),
                    "user_id": case((table.c.user_id == "", new.user_id), else_=table.c.user_id),
                    "organization_id": case(
                        (table.c.organization_id == "", new.organization_id),
                        else_=table.c.organization_id,
                    ),
                },
            )
            await self.db.execute(statement)

    async def _titles(self, dialect: _Dialect, events: list[RecordedEvent]) -> None:
        titles: dict[str, str] = {}
        for e in sorted(events, key=lambda e: e.timestamp):
            if e.event_name == PAGE_VIEWED and e.page_path and e.page_title:
                titles[_clip(e.page_path, 512)] = _clip(e.page_title, 512)
        if not titles:
            return
        table = AnalyticsPageModel.__table__
        rows = [{"page_path": path, "page_title": title} for path, title in titles.items()]
        for chunk in _chunks(rows):
            statement = dialect.insert(table).values(list(chunk))
            statement = statement.on_conflict_do_update(
                index_elements=["page_path"],
                set_={"page_title": statement.excluded.page_title},
            )
            await self.db.execute(statement)

    async def purge_events(self, before: datetime) -> int:
        result = await self.db.execute(
            delete(AnalyticsEventModel).where(AnalyticsEventModel.timestamp < before)
        )
        await self.db.flush()
        return int(getattr(result, "rowcount", 0) or 0)

    async def job_last_run(self, name: str) -> datetime | None:
        return (
            await self.db.execute(
                select(AnalyticsJobModel.last_run_at).where(AnalyticsJobModel.name == name)
            )
        ).scalar_one_or_none()

    async def record_job_run(self, name: str, at: datetime) -> None:
        dialect = _Dialect(self.db)
        table = AnalyticsJobModel.__table__
        statement = dialect.insert(table).values(name=name, last_run_at=at)
        statement = statement.on_conflict_do_update(
            index_elements=["name"], set_={"last_run_at": statement.excluded.last_run_at}
        )
        await self.db.execute(statement)
        await self.db.flush()

    async def claim_job(self, name: str, *, now: datetime, every: float) -> bool:
        dialect = _Dialect(self.db)
        table = AnalyticsJobModel.__table__
        claimed = await self.db.execute(
            dialect.insert(table)
            .values(name=name, last_run_at=now)
            .on_conflict_do_nothing(index_elements=["name"])
            .returning(table.c.name)
        )
        if claimed.scalar_one_or_none() is not None:
            return True
        # Compare-and-set: of several processes, the one whose update lands wins.
        result = await self.db.execute(
            update(AnalyticsJobModel)
            .where(
                AnalyticsJobModel.name == name,
                AnalyticsJobModel.last_run_at <= now - timedelta(seconds=every),
            )
            .values(last_run_at=now)
        )
        return bool(getattr(result, "rowcount", 0))


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


def _slot(column: Any, window: PeriodWindow) -> Any:
    """The index of the period's bucket ``column`` falls in (portable ``CASE``)."""
    last = len(window.slots) - 1
    whens = [(column < slot.end, index) for index, slot in enumerate(window.slots[:-1])]
    return case(*whens, else_=literal(last)) if whens else literal(0)


def _per_slot(rows: Iterable[Any], window: PeriodWindow) -> tuple[int, ...]:
    found = dict.fromkeys(range(len(window.slots)), 0)
    for index, value in rows:
        if index is not None and int(index) in found:
            found[int(index)] = int(value or 0)
    return tuple(found[i] for i in range(len(window.slots)))


class AnalyticsSecondaryAdapterPostgresQueries(AnalyticsQueryPort):
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # -- the scope's directory -------------------------------------------------

    async def organization_timezone(self, organization_id: str) -> str | None:
        return (
            await self.db.execute(
                select(OrganizationModel.timezone).where(OrganizationModel.id == organization_id)
            )
        ).scalar_one_or_none()

    async def organization_workspaces(self, organization_id: str) -> list[str]:
        rows = await self.db.execute(
            select(WorkspaceModel.id)
            .where(WorkspaceModel.organization_id == organization_id)
            .order_by(WorkspaceModel.id)
        )
        return list(rows.scalars().all())

    async def workspace_organization(self, workspace_id: str) -> tuple[bool, str | None]:
        row = (
            await self.db.execute(
                select(WorkspaceModel.id, WorkspaceModel.organization_id).where(
                    WorkspaceModel.id == workspace_id
                )
            )
        ).first()
        return (False, None) if row is None else (True, row[1])

    async def user_emails(self, user_ids: list[str]) -> dict[str, str]:
        if not user_ids:
            return {}
        rows = await self.db.execute(
            select(UserModel.id, UserModel.email).where(UserModel.id.in_(set(user_ids)))
        )
        return dict(rows.tuples().all())

    async def workspace_names(self, workspace_ids: list[str]) -> dict[str, str]:
        if not workspace_ids:
            return {}
        rows = await self.db.execute(
            select(WorkspaceModel.id, WorkspaceModel.name).where(
                WorkspaceModel.id.in_(set(workspace_ids))
            )
        )
        return dict(rows.tuples().all())

    async def agent_names(self, agent_ids: list[str]) -> dict[str, str]:
        if not agent_ids:
            return {}
        rows = await self.db.execute(
            select(AgentConfigModel.id, AgentConfigModel.name).where(
                AgentConfigModel.id.in_(set(agent_ids))
            )
        )
        return dict(rows.tuples().all())

    # -- scope predicates ------------------------------------------------------

    @staticmethod
    def _in_scope(model: Any, scope: AnalyticsScope) -> list[ColumnElement[bool]]:
        found = [
            model.workspace_id.in_(scope.workspace_ids),
            model.user_id.in_(scope.member_ids),
        ]
        if scope.kind == "organization" and scope.organization_id:
            # Events recorded while a workspace belonged to another organization
            # stay that organization's.
            found.append(model.organization_id == scope.organization_id)
        return found

    def _hourly(self, scope: AnalyticsScope, window: PeriodWindow) -> list[ColumnElement[bool]]:
        h = AnalyticsHourlyModel
        return [
            *self._in_scope(h, scope),
            h.bucket_hour >= _hour(window.start),
            h.bucket_hour < window.end,
        ]

    def _user_hourly(
        self, scope: AnalyticsScope, window: PeriodWindow
    ) -> list[ColumnElement[bool]]:
        u = AnalyticsUserHourlyModel
        return [
            *self._in_scope(u, scope),
            u.bucket_hour >= _hour(window.start),
            u.bucket_hour < window.end,
        ]

    def _sessions_where(
        self, scope: AnalyticsScope, window: PeriodWindow
    ) -> list[ColumnElement[bool]]:
        s = AnalyticsSessionModel
        return [*self._in_scope(s, scope), s.started_at >= window.start, s.started_at < window.end]

    @staticmethod
    def _empty(scope: AnalyticsScope) -> bool:
        return not scope.workspace_ids or not scope.member_ids

    # -- rollups ---------------------------------------------------------------

    async def overview(self, scope: AnalyticsScope, window: PeriodWindow) -> OverviewAggregate:
        zeros = tuple(0 for _ in window.slots)
        if self._empty(scope):
            return OverviewAggregate(0, 0, 0, 0, 0, 0, zeros, zeros)
        u = AnalyticsUserHourlyModel
        where = self._user_hourly(scope, window)
        totals = (
            await self.db.execute(
                select(
                    func.count(distinct(u.user_id)),
                    func.coalesce(func.sum(u.page_views), 0),
                    func.count(distinct(u.workspace_id)),
                ).where(*where)
            )
        ).one()
        slot = _slot(u.bucket_hour, window).label("slot")
        users_per_slot = await self.db.execute(
            select(slot, func.count(distinct(u.user_id))).where(*where).group_by(slot)
        )

        dialect = _Dialect(self.db)
        s = AnalyticsSessionModel
        per_session = (
            select(
                s.session_id.label("session_id"),
                func.min(s.user_id).label("user_id"),
                func.min(s.started_at).label("started_at"),
                func.max(s.ended_at).label("ended_at"),
            )
            .where(*self._sessions_where(scope, window))
            .group_by(s.session_id)
            .subquery()
        )
        sessions = (
            await self.db.execute(
                select(
                    func.count(),
                    func.coalesce(
                        func.avg(dialect.seconds(per_session.c.started_at, per_session.c.ended_at)),
                        0,
                    ),
                ).select_from(per_session)
            )
        ).one()
        returning = (
            await self.db.execute(
                select(func.count()).select_from(
                    select(per_session.c.user_id)
                    .group_by(per_session.c.user_id)
                    .having(func.count() > 1)
                    .subquery()
                )
            )
        ).scalar_one()
        session_slot = _slot(per_session.c.started_at, window).label("slot")
        sessions_per_slot = await self.db.execute(
            select(session_slot, func.count()).select_from(per_session).group_by(session_slot)
        )
        return OverviewAggregate(
            active_users=int(totals[0] or 0),
            total_sessions=int(sessions[0] or 0),
            total_page_views=int(totals[1] or 0),
            workspaces_used=int(totals[2] or 0),
            avg_session_duration_seconds=int(float(sessions[1] or 0)),
            returning_users=int(returning or 0),
            sessions_per_slot=_per_slot(sessions_per_slot.all(), window),
            users_per_slot=_per_slot(users_per_slot.all(), window),
        )

    async def users(self, scope: AnalyticsScope, window: PeriodWindow) -> list[UserAggregate]:
        if self._empty(scope):
            return []
        u = AnalyticsUserHourlyModel
        activity = await self.db.execute(
            select(
                u.user_id,
                func.sum(u.page_views),
                func.count(distinct(u.workspace_id)),
                func.sum(u.events),
                func.max(u.bucket_hour),
            )
            .where(*self._user_hourly(scope, window))
            .group_by(u.user_id)
        )
        s = AnalyticsSessionModel
        sessions = await self.db.execute(
            select(s.user_id, func.count(distinct(s.session_id)), func.max(s.ended_at))
            .where(*self._sessions_where(scope, window))
            .group_by(s.user_id)
        )
        by_session = {uid: (int(n), last) for uid, n, last in sessions.all()}
        found: list[UserAggregate] = []
        for uid, page_views, workspaces, total, last_hour in activity.all():
            count, last_seen = by_session.pop(uid, (0, None))
            found.append(
                UserAggregate(
                    user_id=uid,
                    sessions=count,
                    page_views=int(page_views or 0),
                    workspaces=int(workspaces or 0),
                    total_events=int(total or 0),
                    last_seen=last_seen or last_hour,
                )
            )
        for uid, (count, last_seen) in by_session.items():
            found.append(UserAggregate(uid, count, 0, 0, 0, last_seen))
        found.sort(key=lambda u: (-u.total_events, u.user_id))
        return found

    async def sessions(
        self, scope: AnalyticsScope, window: PeriodWindow, *, limit: int
    ) -> list[SessionAggregate]:
        if self._empty(scope):
            return []
        s = AnalyticsSessionModel
        started = func.min(s.started_at)
        rows = await self.db.execute(
            select(
                s.session_id,
                func.min(s.user_id),
                func.min(s.workspace_id),
                started,
                func.max(s.ended_at),
                func.sum(s.page_views),
                func.sum(s.events),
                func.max(s.device),
                func.max(s.browser),
            )
            .where(*self._sessions_where(scope, window))
            .group_by(s.session_id)
            .order_by(started.desc(), s.session_id)
            .limit(limit)
        )
        return [
            SessionAggregate(
                session_id=sid,
                user_id=uid,
                workspace_id=wid,
                started_at=begin,
                ended_at=end,
                page_views=int(views or 0),
                events=int(events or 0),
                device=device,
                browser=browser,
            )
            for sid, uid, wid, begin, end, views, events, device, browser in rows.all()
        ]

    async def pages(self, scope: AnalyticsScope, window: PeriodWindow) -> list[PageAggregate]:
        if self._empty(scope):
            return []
        h = AnalyticsHourlyModel
        views = func.sum(h.count)
        rows = await self.db.execute(
            select(
                h.page_path,
                views,
                func.count(distinct(h.user_id)),
                func.max(AnalyticsPageModel.page_title),
            )
            .outerjoin(AnalyticsPageModel, AnalyticsPageModel.page_path == h.page_path)
            .where(*self._hourly(scope, window), h.event_name == PAGE_VIEWED, h.page_path != "")
            .group_by(h.page_path)
            .order_by(views.desc(), h.page_path)
        )
        return [
            PageAggregate(
                page_path=path, page_title=title or path, views=int(n), unique_users=int(users)
            )
            for path, n, users, title in rows.all()
        ]

    async def workspaces(
        self, scope: AnalyticsScope, window: PeriodWindow
    ) -> list[WorkspaceAggregate]:
        if self._empty(scope):
            return []
        u = AnalyticsUserHourlyModel
        events = func.sum(u.events)
        activity = await self.db.execute(
            select(u.workspace_id, func.count(distinct(u.user_id)), events)
            .where(*self._user_hourly(scope, window))
            .group_by(u.workspace_id)
            .order_by(events.desc(), u.workspace_id)
        )
        s = AnalyticsSessionModel
        sessions: dict[str, int] = dict(
            (
                await self.db.execute(
                    select(s.workspace_id, func.count(distinct(s.session_id)))
                    .where(*self._sessions_where(scope, window))
                    .group_by(s.workspace_id)
                )
            )
            .tuples()
            .all()
        )
        return [
            WorkspaceAggregate(
                workspace_id=wid,
                active_users=int(users),
                sessions=int(sessions.get(wid, 0)),
                events=int(n or 0),
            )
            for wid, users, n in activity.all()
        ]

    async def events(
        self, scope: AnalyticsScope, window: PeriodWindow, *, limit: int
    ) -> list[dict[str, Any]]:
        if self._empty(scope):
            return []
        e = AnalyticsEventModel
        rows = await self.db.execute(
            select(e.payload)
            .where(*self._in_scope(e, scope), e.timestamp >= window.start, e.timestamp < window.end)
            .order_by(e.timestamp.desc(), e.event_key)
            .limit(limit)
        )
        found: list[dict[str, Any]] = []
        for (raw,) in rows.all():
            try:
                payload = json.loads(raw)
            except (TypeError, ValueError):
                continue
            if isinstance(payload, dict):
                found.append(payload)
        return found

    async def chat_page_views(self, scope: AnalyticsScope, window: PeriodWindow) -> dict[str, int]:
        if self._empty(scope):
            return {}
        h = AnalyticsHourlyModel
        rows = await self.db.execute(
            select(h.page_path, func.sum(h.count))
            .where(
                *self._hourly(scope, window),
                h.event_name == PAGE_VIEWED,
                h.page_path.like("%/chat/conv-%"),
            )
            .group_by(h.page_path)
        )
        found: dict[str, int] = defaultdict(int)
        for path, n in rows.all():
            match = _CHAT_PATH.search(path or "")
            if match:
                found[match.group(1)] += int(n or 0)
        return dict(found)

    # -- chats -----------------------------------------------------------------

    @staticmethod
    def _conversations_where(scope: AnalyticsScope) -> list[ColumnElement[bool]]:
        c = ConversationModel
        return [c.workspace_id.in_(scope.workspace_ids), c.user_id.in_(scope.member_ids)]

    async def _message_counts(self, conversation_ids: list[str]) -> dict[str, int]:
        if not conversation_ids:
            return {}
        rows = await self.db.execute(
            select(MessageModel.conversation_id, func.count())
            .where(MessageModel.conversation_id.in_(conversation_ids))
            .group_by(MessageModel.conversation_id)
        )
        return {cid: int(n) for cid, n in rows.all()}

    _CONVERSATION_COLUMNS = (
        ConversationModel.id,
        ConversationModel.workspace_id,
        ConversationModel.user_id,
        ConversationModel.title,
        ConversationModel.agent,
        ConversationModel.created_at,
        ConversationModel.updated_at,
    )

    @staticmethod
    def _conversation(row: Any, counts: dict[str, int]) -> ConversationAggregate:
        cid, workspace_id, user_id, title, agent, created_at, updated_at = row
        return ConversationAggregate(
            conversation_id=cid,
            workspace_id=workspace_id,
            user_id=user_id,
            title=title,
            agent=agent,
            created_at=created_at,
            updated_at=updated_at,
            message_count=counts.get(cid, 0),
        )

    async def conversations(
        self, scope: AnalyticsScope, window: PeriodWindow, *, limit: int
    ) -> list[ConversationAggregate]:
        if self._empty(scope):
            return []
        c = ConversationModel
        rows = (
            await self.db.execute(
                select(*self._CONVERSATION_COLUMNS)
                .where(
                    *self._conversations_where(scope),
                    c.updated_at >= window.start,
                    c.updated_at < window.end,
                )
                .order_by(c.updated_at.desc(), c.id)
                .limit(limit)
            )
        ).all()
        counts = await self._message_counts([row[0] for row in rows])
        return [self._conversation(row, counts) for row in rows]

    async def conversation_in_scope(
        self, scope: AnalyticsScope, conversation_id: str
    ) -> ConversationAggregate | None:
        if self._empty(scope):
            return None
        c = ConversationModel
        row = (
            await self.db.execute(
                select(*self._CONVERSATION_COLUMNS).where(
                    c.id == conversation_id, *self._conversations_where(scope)
                )
            )
        ).first()
        if row is None:
            return None
        return self._conversation(row, await self._message_counts([row[0]]))

    async def chat_analytics(
        self, scope: AnalyticsScope, window: PeriodWindow, *, top: int
    ) -> ChatAggregate:
        zeros = tuple(0 for _ in window.slots)
        if self._empty(scope):
            return ChatAggregate(0, 0, 0, 0, None, zeros, zeros, (), (), (), ())
        c = ConversationModel
        m = MessageModel
        chats_where = [
            *self._conversations_where(scope),
            c.updated_at >= window.start,
            c.updated_at < window.end,
        ]
        chats_slot = _slot(c.updated_at, window).label("slot")
        chats_per_slot = (
            await self.db.execute(
                select(chats_slot, func.count()).where(*chats_where).group_by(chats_slot)
            )
        ).all()
        num_chats = sum(int(n) for _slot_index, n in chats_per_slot)
        chats_by_agent = (
            await self.db.execute(
                select(c.agent, func.count()).where(*chats_where).group_by(c.agent)
            )
        ).all()

        # Messages written in the period, in the scope's conversations.
        in_period = and_(
            *self._conversations_where(scope),
            m.created_at >= window.start,
            m.created_at < window.end,
        )
        likes = func.sum(case((m.feedback == "like", 1), else_=0))
        dislikes = func.sum(case((m.feedback == "dislike", 1), else_=0))
        totals = (
            await self.db.execute(
                select(func.count(), likes, dislikes, func.max(m.created_at))
                .select_from(m)
                .join(c, c.id == m.conversation_id)
                .where(in_period)
            )
        ).one()
        message_slot = _slot(m.created_at, window).label("slot")
        messages_per_slot = (
            await self.db.execute(
                select(message_slot, func.count())
                .select_from(m)
                .join(c, c.id == m.conversation_id)
                .where(in_period)
                .group_by(message_slot)
            )
        ).all()
        messages_by_agent: dict[str, int] = dict(
            (
                await self.db.execute(
                    select(c.agent, func.count())
                    .select_from(m)
                    .join(c, c.id == m.conversation_id)
                    .where(in_period)
                    .group_by(c.agent)
                )
            )
            .tuples()
            .all()
        )
        feedback_types = (
            await self.db.execute(
                select(m.feedback_type, func.count())
                .select_from(m)
                .join(c, c.id == m.conversation_id)
                .where(in_period, m.feedback == "dislike", m.feedback_type.is_not(None))
                .group_by(m.feedback_type)
                .order_by(func.count().desc(), m.feedback_type)
            )
        ).all()
        t = MessageToolModel
        uses = func.sum(t.uses)
        tools = (
            await self.db.execute(
                select(t.tool_name, uses)
                .select_from(t)
                .join(m, m.id == t.message_id)
                .join(c, c.id == m.conversation_id)
                .where(in_period)
                .group_by(t.tool_name)
                .order_by(uses.desc(), t.tool_name)
            )
        ).all()

        count = func.count()
        top_rows = (
            await self.db.execute(
                select(
                    m.conversation_id,
                    count,
                    likes,
                    dislikes,
                    func.max(m.created_at),
                    func.min(c.workspace_id),
                    func.min(c.user_id),
                    func.min(c.title),
                    func.min(c.agent),
                )
                .select_from(m)
                .join(c, c.id == m.conversation_id)
                .where(in_period)
                .group_by(m.conversation_id)
                .order_by(count.desc(), m.conversation_id)
                .limit(top)
            )
        ).all()
        top_ids = [row[0] for row in top_rows]
        agents_of: dict[str, set[str]] = defaultdict(set)
        tools_of: dict[str, set[str]] = defaultdict(set)
        if top_ids:
            for cid, agent in (
                await self.db.execute(
                    select(m.conversation_id, m.agent)
                    .where(m.conversation_id.in_(top_ids), m.agent.is_not(None))
                    .group_by(m.conversation_id, m.agent)
                )
            ).all():
                agents_of[cid].add(agent)
            for cid, tool in (
                await self.db.execute(
                    select(m.conversation_id, t.tool_name)
                    .select_from(t)
                    .join(m, m.id == t.message_id)
                    .join(c, c.id == m.conversation_id)
                    .where(m.conversation_id.in_(top_ids), in_period)
                    .group_by(m.conversation_id, t.tool_name)
                )
            ).all():
                tools_of[cid].add(tool)
        top_chats = tuple(
            ChatTopAggregate(
                conversation_id=cid,
                workspace_id=wid,
                user_id=uid,
                title=title,
                message_count=int(n),
                likes=int(lk or 0),
                dislikes=int(dk or 0),
                agents=tuple(sorted({agent, *agents_of[cid]} - {""})),
                tools=tuple(sorted(tools_of[cid])),
                last_message_at=last,
            )
            for cid, n, lk, dk, last, wid, uid, title, agent in top_rows
        )
        agents = sorted(
            (
                (agent or "unknown", int(messages_by_agent.get(agent, 0)), int(chats))
                for agent, chats in chats_by_agent
            ),
            key=lambda row: (-row[1], row[0]),
        )
        return ChatAggregate(
            num_chats=num_chats,
            num_messages=int(totals[0] or 0),
            likes=int(totals[1] or 0),
            dislikes=int(totals[2] or 0),
            last_message_at=totals[3],
            messages_per_slot=_per_slot(messages_per_slot, window),
            chats_per_slot=_per_slot(chats_per_slot, window),
            agents=tuple(agents),
            tools=tuple((name, int(n)) for name, n in tools),
            feedback_types=tuple((name, int(n)) for name, n in feedback_types),
            top_chats=top_chats,
        )
