"""The rollups and the scoped reads over them, on SQLite (as ``abi dev`` runs them)."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from naas_abi.apps.nexus.apps.api.app.core.database import Base
from naas_abi.apps.nexus.apps.api.app.models import (
    AnalyticsEventModel,
    AnalyticsHourlyModel,
    AnalyticsSessionModel,
    AnalyticsUserHourlyModel,
    ConversationModel,
    MessageModel,
    MessageToolModel,
    OrganizationModel,
    UserModel,
    WorkspaceModel,
)
from naas_abi.apps.nexus.apps.api.app.services.analytics.adapters.secondary.analytics__secondary_adapter__postgres import (  # noqa: E501
    AnalyticsSecondaryAdapterPostgresEvents,
    AnalyticsSecondaryAdapterPostgresQueries,
)
from naas_abi.apps.nexus.apps.api.app.services.analytics.periods import resolve_period
from naas_abi.apps.nexus.apps.api.app.services.analytics.port import (
    AnalyticsScope,
    RecordedEvent,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

NOW = datetime(2026, 11, 19, 10, 30, tzinfo=UTC)
T0 = datetime(2026, 11, 19, 9, 0)
LONG_AGO = datetime(2026, 1, 1)


# The same tests on PostgreSQL when a database is given (it is emptied):
# ANALYTICS_TEST_POSTGRES_DSN=postgresql+asyncpg://user:pass@host:5432/db
POSTGRES_DSN = os.environ.get("ANALYTICS_TEST_POSTGRES_DSN")


@pytest_asyncio.fixture(params=["sqlite", "postgresql"])
async def db(request):
    if request.param == "postgresql" and not POSTGRES_DSN:
        pytest.skip("ANALYTICS_TEST_POSTGRES_DSN is not set")
    engine = create_async_engine(
        "sqlite+aiosqlite://" if request.param == "sqlite" else POSTGRES_DSN
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as session:
        for uid in ("alice", "bob", "eve"):
            session.add(UserModel(id=uid, email=f"{uid}@example.com", name=uid.title()))
        session.add(OrganizationModel(id="org-a", name="A", slug="a", owner_id="alice"))
        session.add(
            OrganizationModel(
                id="org-b", name="B", slug="b", owner_id="eve", timezone="Europe/Paris"
            )
        )
        for wid, org in (("ws-1", "org-a"), ("ws-2", "org-a"), ("ws-x", "org-b")):
            session.add(
                WorkspaceModel(
                    id=wid, name=f"Space {wid}", slug=wid, owner_id="alice", organization_id=org
                )
            )
        await session.commit()
        yield session
    await engine.dispose()


def event(
    event_id: str,
    *,
    at: datetime = T0,
    user: str = "alice",
    workspace: str | None = "ws-1",
    session: str = "s-1",
    name: str = "page_viewed",
    path: str | None = "/workspace/ws-1/home",
    title: str | None = "Home",
    organization: str | None = None,
) -> RecordedEvent:
    return RecordedEvent(
        event_id=event_id,
        timestamp=at,
        session_id=session,
        event_name=name,
        user_id=user,
        workspace_id=workspace,
        organization_id=organization,
        page_path=path,
        page_title=title,
        device="desktop",
        browser="firefox",
        payload={
            "event_id": event_id,
            "timestamp": at.isoformat() + "Z",
            "session_id": session,
            "event_name": name,
            "user_id": user,
            "workspace_id": workspace,
            "page_path": path,
        },
    )


ORG_A = AnalyticsScope("organization", "org-a", ("ws-1", "ws-2"), ("alice", "bob"))
WS_1 = AnalyticsScope("workspace", "org-a", ("ws-1",), ("alice", "bob"))
TODAY = resolve_period("today", "UTC", NOW)


async def _count(db: AsyncSession, model) -> int:
    return (await db.execute(select(func.count()).select_from(model))).scalar_one()


# -- writes ------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_an_event_is_applied_once_however_often_it_is_handed_over(db) -> None:
    port = AnalyticsSecondaryAdapterPostgresEvents(db)
    batch = [event("e-1"), event("e-2", at=T0 + timedelta(minutes=5)), event("e-1")]
    assert await port.apply_events(batch, not_before=LONG_AGO) == 2
    assert await port.apply_events(batch, not_before=LONG_AGO) == 0

    hourly = (await db.execute(select(AnalyticsHourlyModel))).scalars().all()
    assert [(h.bucket_hour, h.organization_id, h.workspace_id, h.count) for h in hourly] == [
        (T0, "org-a", "ws-1", 2)
    ]
    session = (await db.execute(select(AnalyticsSessionModel))).scalar_one()
    assert (session.started_at, session.ended_at, session.page_views, session.events) == (
        T0,
        T0 + timedelta(minutes=5),
        2,
        2,
    )


@pytest.mark.asyncio
async def test_the_same_tracker_id_from_two_users_is_two_events(db) -> None:
    port = AnalyticsSecondaryAdapterPostgresEvents(db)
    assert (
        await port.apply_events(
            [event("e-1"), event("e-1", user="bob", session="s-2")], not_before=LONG_AGO
        )
        == 2
    )


@pytest.mark.asyncio
async def test_sessions_grow_across_batches(db) -> None:
    port = AnalyticsSecondaryAdapterPostgresEvents(db)
    await port.apply_events([event("e-1", at=T0 + timedelta(minutes=10))], not_before=LONG_AGO)
    await port.apply_events(
        [event("e-2", at=T0), event("e-3", at=T0 + timedelta(minutes=30), name="button_clicked")],
        not_before=LONG_AGO,
    )
    session = (await db.execute(select(AnalyticsSessionModel))).scalar_one()
    assert (session.started_at, session.ended_at, session.page_views, session.events) == (
        T0,
        T0 + timedelta(minutes=30),
        2,
        3,
    )


@pytest.mark.asyncio
async def test_the_organization_is_stamped_from_the_workspace(db) -> None:
    port = AnalyticsSecondaryAdapterPostgresEvents(db)
    await port.apply_events(
        [event("e-1", workspace="ws-x"), event("e-2", workspace=None, path="/home")],
        not_before=LONG_AGO,
    )
    rows = {
        r.workspace_id: r for r in (await db.execute(select(AnalyticsEventModel))).scalars().all()
    }
    assert rows["ws-x"].organization_id == "org-b"
    assert json.loads(rows["ws-x"].payload)["organization_id"] == "org-b"
    assert rows[""].organization_id == ""


@pytest.mark.asyncio
async def test_events_past_retention_are_not_applied(db) -> None:
    port = AnalyticsSecondaryAdapterPostgresEvents(db)
    assert await port.apply_events([event("e-1", at=LONG_AGO)], not_before=T0) == 0
    assert await _count(db, AnalyticsEventModel) == 0


@pytest.mark.asyncio
async def test_the_purge_deletes_raw_events_and_keeps_the_rollups(db) -> None:
    port = AnalyticsSecondaryAdapterPostgresEvents(db)
    await port.apply_events(
        [event("old", at=T0 - timedelta(days=50)), event("new")], not_before=LONG_AGO
    )
    assert await port.purge_events(T0 - timedelta(days=45)) == 1
    assert await _count(db, AnalyticsEventModel) == 1
    assert await _count(db, AnalyticsHourlyModel) == 2
    assert await _count(db, AnalyticsUserHourlyModel) == 2
    assert await _count(db, AnalyticsSessionModel) == 1


@pytest.mark.asyncio
async def test_legacy_events_are_counted_whatever_their_age_and_once(db) -> None:
    """Past retention a legacy event has no raw row, only rollups; replayed again
    (the cleanup's replay) nothing is counted twice, nor an event the log counted."""
    port = AnalyticsSecondaryAdapterPostgresEvents(db)
    raw_since = T0 - timedelta(days=45)
    assert await port.apply_events([event("logged")], not_before=raw_since) == 1
    legacy = [
        event("recent", at=T0 - timedelta(days=1)),
        event("old", at=T0 - timedelta(days=60)),
        event("ancient", at=LONG_AGO - timedelta(days=700)),
        event("logged"),
    ]
    assert await port.apply_legacy_events(legacy, raw_since=raw_since) == 3
    assert await port.apply_legacy_events(legacy, raw_since=raw_since) == 0
    # A day later "recent" is still within retention, "old" long past it.
    assert await port.apply_legacy_events(legacy, raw_since=raw_since + timedelta(days=30)) == 0
    assert await _count(db, AnalyticsEventModel) == 2  # logged, recent
    total = (await db.execute(select(func.sum(AnalyticsHourlyModel.count)))).scalar_one()
    assert total == 4
    assert (await db.execute(select(func.sum(AnalyticsUserHourlyModel.events)))).scalar_one() == 4


@pytest.mark.asyncio
async def test_a_page_title_shows_only_in_the_scope_it_was_recorded_in(db) -> None:
    """A user of org-b sends a page_viewed for a path org-a's members visit, with a
    misleading title: org-a's pages keep their own."""
    port = AnalyticsSecondaryAdapterPostgresEvents(db)
    await port.apply_events([event("a1", title="Home")], not_before=LONG_AGO)
    await port.apply_events(
        [
            event(
                "spoof",
                at=T0 + timedelta(minutes=5),
                user="eve",
                workspace="ws-x",
                path="/workspace/ws-1/home",
                title="Session expired, sign in at evil.example",
            ),
            event(
                "nobody",
                at=T0 + timedelta(minutes=6),
                user="eve",
                workspace=None,
                path="/workspace/ws-1/home",
                title="Also evil",
            ),
        ],
        not_before=LONG_AGO,
    )
    queries = AnalyticsSecondaryAdapterPostgresQueries(db)
    pages = await queries.pages(ORG_A, TODAY)
    assert [(p.page_path, p.page_title) for p in pages] == [("/workspace/ws-1/home", "Home")]
    org_b = AnalyticsScope("organization", "org-b", ("ws-x",), ("eve",))
    assert [p.page_title for p in await queries.pages(org_b, TODAY)] == [
        "Session expired, sign in at evil.example"
    ]


@pytest.mark.asyncio
async def test_control_characters_never_reach_a_text_column(db) -> None:
    """PostgreSQL refuses a NUL in text: an event read from the log or the legacy
    storage with one is applied without it, not refused with its whole batch."""
    from naas_abi.apps.nexus.apps.api.app.services.analytics.rollups import (
        recorded_from_payload,
    )

    recorded = recorded_from_payload(
        {
            "event_id": "e-\u0000nul",
            "timestamp": T0.isoformat() + "Z",
            "session_id": "s-\u00001",
            "event_name": "page\u0000viewed",
            "user_id": "alice",
            "workspace_id": "ws-1",
            "page_path": "/workspace/ws-1/\u0000home",
            "page_title": "Ho\u0000me",
            "browser": "fire\u0000fox",
            "properties": {"k\u0000": "v\u0000"},
        }
    )
    assert recorded is not None
    port = AnalyticsSecondaryAdapterPostgresEvents(db)
    assert await port.apply_events([recorded, event("ok")], not_before=LONG_AGO) == 2
    await db.commit()
    rows = (await db.execute(select(AnalyticsEventModel))).scalars().all()
    assert sorted(r.event_name for r in rows) == ["page_viewed", "pageviewed"]
    assert all("\x00" not in r.page_path and "\\u0000" not in r.payload for r in rows)


@pytest.mark.asyncio
async def test_a_periodic_job_is_claimed_once_per_period(db) -> None:
    port = AnalyticsSecondaryAdapterPostgresEvents(db)
    assert await port.claim_job("purge", now=T0, every=3600)
    assert not await port.claim_job("purge", now=T0 + timedelta(minutes=5), every=3600)
    assert await port.claim_job("purge", now=T0 + timedelta(hours=2), every=3600)
    assert await port.job_last_run("once") is None
    await port.record_job_run("once", T0)
    assert await port.job_last_run("once") == T0


# -- reads -------------------------------------------------------------------------


async def _seed(db: AsyncSession) -> None:
    port = AnalyticsSecondaryAdapterPostgresEvents(db)
    await port.apply_events(
        [
            event("a1", at=T0, path="/workspace/ws-1/home"),
            event(
                "a2",
                at=T0 + timedelta(minutes=20),
                path="/workspace/ws-1/chat/conv-1",
                title="Chat",
            ),
            event(
                "a3",
                at=T0 + timedelta(minutes=40),
                workspace="ws-2",
                session="s-1",
                path="/workspace/ws-2/home",
            ),
            event(
                "a4", at=T0 - timedelta(hours=2), session="s-0", name="button_clicked", path=None
            ),
            event("b1", at=T0 + timedelta(minutes=1), user="bob", session="s-2"),
            # Not in the scope: a stranger in ws-1, alice in another org, no workspace.
            event("x1", user="eve", session="s-9"),
            event("x2", workspace="ws-x", session="s-8", path="/workspace/ws-x/home"),
            event("x3", workspace=None, session="s-7", path="/home"),
            # Yesterday.
            event("y1", at=T0 - timedelta(days=1), session="s-6"),
        ],
        not_before=LONG_AGO,
    )


@pytest.mark.asyncio
async def test_the_overview_counts_members_in_the_scope_only(db) -> None:
    await _seed(db)
    queries = AnalyticsSecondaryAdapterPostgresQueries(db)
    found = await queries.overview(ORG_A, TODAY)
    users = await queries.users(ORG_A, TODAY)
    assert len(users) == 2
    assert sum(u.page_views for u in users) == 4  # a1, a2, a3, b1
    assert len(await queries.workspaces(ORG_A, TODAY)) == 2
    assert found.total_sessions == 3  # s-0, s-1 (two workspaces, one session), s-2
    assert found.returning_users == 1  # alice: s-0 and s-1
    assert found.avg_session_duration_seconds == (40 * 60) // 3
    assert sum(found.sessions_per_slot) == 3
    assert found.users_per_slot[9] == 2 and found.users_per_slot[7] == 1

    assert len(await queries.workspaces(WS_1, TODAY)) == 1
    assert sum(u.page_views for u in await queries.users(WS_1, TODAY)) == 3


@pytest.mark.asyncio
async def test_users_pages_sessions_and_workspaces_of_a_scope(db) -> None:
    await _seed(db)
    queries = AnalyticsSecondaryAdapterPostgresQueries(db)

    users = {u.user_id: u for u in await queries.users(ORG_A, TODAY)}
    assert set(users) == {"alice", "bob"}
    assert (users["alice"].page_views, users["alice"].total_events, users["alice"].sessions) == (
        3,
        4,
        2,
    )
    assert users["alice"].workspaces == 2

    pages = await queries.pages(ORG_A, TODAY)
    assert pages[0].page_path == "/workspace/ws-1/home"
    assert (pages[0].views, pages[0].unique_users) == (2, 2)
    assert {p.page_path: p.page_title for p in pages}["/workspace/ws-1/chat/conv-1"] == "Chat"

    sessions = await queries.sessions(ORG_A, TODAY, limit=10)
    assert [s.session_id for s in sessions] == ["s-2", "s-1", "s-0"]
    assert sessions[1].events == 3 and sessions[1].page_views == 3

    workspaces = {w.workspace_id: w for w in await queries.workspaces(ORG_A, TODAY)}
    assert set(workspaces) == {"ws-1", "ws-2"}
    assert (workspaces["ws-1"].active_users, workspaces["ws-1"].sessions) == (2, 3)

    assert await queries.chat_page_views(ORG_A, TODAY) == {"conv-1": 1}


@pytest.mark.asyncio
async def test_the_events_of_a_scope_newest_first(db) -> None:
    await _seed(db)
    queries = AnalyticsSecondaryAdapterPostgresQueries(db)
    found = await queries.events(ORG_A, TODAY, limit=3)
    assert [e["event_id"] for e in found] == ["a3", "a2", "b1"]
    narrowed = ORG_A.narrowed(user_id="bob")
    assert [e["event_id"] for e in await queries.events(narrowed, TODAY, limit=10)] == ["b1"]


@pytest.mark.asyncio
async def test_an_event_stamped_with_another_organization_stays_there(db) -> None:
    port = AnalyticsSecondaryAdapterPostgresEvents(db)
    # Recorded while ws-1 belonged to org-b.
    await port.apply_events([event("moved", organization="org-b")], not_before=LONG_AGO)
    queries = AnalyticsSecondaryAdapterPostgresQueries(db)
    assert await queries.users(ORG_A, TODAY) == []
    assert len(await queries.users(WS_1, TODAY)) == 1


@pytest.mark.asyncio
async def test_an_empty_scope_reads_nothing(db) -> None:
    await _seed(db)
    queries = AnalyticsSecondaryAdapterPostgresQueries(db)
    nobody = AnalyticsScope("organization", "org-a", ("ws-1",), ())
    assert (await queries.overview(nobody, TODAY)).total_sessions == 0
    assert await queries.users(nobody, TODAY) == []


@pytest.mark.asyncio
async def test_periods_follow_the_time_zone(db) -> None:
    port = AnalyticsSecondaryAdapterPostgresEvents(db)
    # 23:30 UTC on the 18th is 00:30 on the 19th in Paris.
    await port.apply_events([event("late", at=datetime(2026, 11, 18, 23, 30))], not_before=LONG_AGO)
    queries = AnalyticsSecondaryAdapterPostgresQueries(db)
    paris = AnalyticsScope("workspace", "org-a", ("ws-1",), ("alice",), "Europe/Paris")
    utc = AnalyticsScope("workspace", "org-a", ("ws-1",), ("alice",), "UTC")
    in_paris = await queries.overview(paris, resolve_period("today", "Europe/Paris", NOW))
    in_utc = await queries.overview(utc, resolve_period("today", "UTC", NOW))
    assert in_paris.users_per_slot[0] == 1
    assert sum(in_utc.users_per_slot) == 0
    assert await queries.users(utc, resolve_period("yesterday", "UTC", NOW))


# -- chats -------------------------------------------------------------------------


async def _chats(db: AsyncSession) -> None:
    created = T0 - timedelta(minutes=30)
    for cid, ws, user in (
        ("conv-1", "ws-1", "alice"),
        ("conv-2", "ws-2", "bob"),
        ("conv-x", "ws-x", "eve"),
    ):
        db.add(
            ConversationModel(
                id=cid,
                workspace_id=ws,
                user_id=user,
                title=f"T {cid}",
                agent="agent-1",
                created_at=created,
                updated_at=T0,
            )
        )
    rows = [
        ("m1", "conv-1", "user", None, None),
        ("m2", "conv-1", "assistant", "like", None),
        ("m3", "conv-1", "assistant", "dislike", "wrong"),
        ("m4", "conv-2", "assistant", "dislike", "slow"),
        ("m5", "conv-x", "assistant", "like", None),
    ]
    for mid, cid, role, feedback, kind in rows:
        db.add(
            MessageModel(
                id=mid,
                conversation_id=cid,
                role=role,
                content="…",
                agent="agent-1" if role == "assistant" else None,
                feedback=feedback,
                feedback_type=kind,
                created_at=T0,
            )
        )
    await db.flush()
    db.add(MessageToolModel(message_id="m2", tool_name="search", uses=2))
    db.add(MessageToolModel(message_id="m4", tool_name="search", uses=1))
    db.add(MessageToolModel(message_id="m5", tool_name="secret_tool", uses=9))
    await db.flush()


@pytest.mark.asyncio
async def test_chat_figures_are_sql_aggregates_of_the_scope(db) -> None:
    await _chats(db)
    queries = AnalyticsSecondaryAdapterPostgresQueries(db)
    found = await queries.chat_analytics(ORG_A, TODAY, top=10)
    assert (found.num_chats, found.num_messages, found.likes, found.dislikes) == (2, 4, 1, 2)
    assert found.tools == (("search", 3),)
    assert dict(found.feedback_types) == {"slow": 1, "wrong": 1}
    assert found.agents == (("agent-1", 4, 2),)
    assert [c.conversation_id for c in found.top_chats] == ["conv-1", "conv-2"]
    assert found.top_chats[0].tools == ("search",)
    assert sum(found.messages_per_slot) == 4

    chats = await queries.conversations(WS_1, TODAY, limit=10)
    assert [(c.conversation_id, c.message_count) for c in chats] == [("conv-1", 3)]
    assert await queries.conversation_in_scope(ORG_A, "conv-x") is None
    assert (await queries.conversation_in_scope(ORG_A, "conv-2")).user_id == "bob"


@pytest.mark.asyncio
async def test_the_directory_of_a_scope(db) -> None:
    queries = AnalyticsSecondaryAdapterPostgresQueries(db)
    assert await queries.organization_timezone("org-b") == "Europe/Paris"
    assert await queries.organization_timezone("org-a") == "UTC"
    assert await queries.organization_timezone("nope") is None
    assert await queries.organization_workspaces("org-a") == ["ws-1", "ws-2"]
    assert await queries.workspace_organization("ws-x") == (True, "org-b")
    assert await queries.workspace_organization("nope") == (False, None)
    assert await queries.user_emails(["bob"]) == {"bob": "bob@example.com"}
