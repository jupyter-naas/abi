"""Organization and workspace analytics: who reads them, and what their scope holds.

A real IAM (``team``: ``ws-1`` of ``org-1`` with an owner, an admin, a member and a
viewer, and ``stranger``) decides; the figures are read from SQLite rollups.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from naas_abi.apps.nexus.apps.api.app.core.database import get_db
from naas_abi.apps.nexus.apps.api.app.models import (
    ConversationModel,
    MessageModel,
    OrganizationModel,
    UserModel,
    WorkspaceModel,
)
from naas_abi.apps.nexus.apps.api.app.services.analytics.adapters.primary import (
    analytics__primary_adapter__scoped as scoped,
)
from naas_abi.apps.nexus.apps.api.app.services.analytics.adapters.secondary.analytics__secondary_adapter__postgres import (  # noqa: E501
    AnalyticsSecondaryAdapterPostgresEvents,
)
from naas_abi.apps.nexus.apps.api.app.services.analytics.port import RecordedEvent
from naas_abi.apps.nexus.apps.api.app.services.analytics.scoped_service import (
    ScopedAnalyticsService,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (  # noqa: E501
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.services.chat.adapters.secondary.postgres import (
    ChatSecondaryAdapterPostgres,
)
from naas_abi.apps.nexus.apps.api.app.services.registry import get_service_registry

NOW = datetime(2026, 11, 19, 10, 30, tzinfo=UTC)
T0 = datetime(2026, 11, 19, 9, 0)
USERS = ("owner", "admin", "member", "viewer", "stranger", "outsider")
ORG = "/api/organizations/org-1/analytics"
WS = "/api/workspaces/ws-1/analytics"


@pytest.fixture(autouse=True)
def fresh_members():
    """Each test's IAM is its own: forget the members another test's resolved."""
    scoped._members_cache.clear()
    yield
    scoped._members_cache.clear()


@pytest_asyncio.fixture
async def world(team, nexus_db):
    """``org-1`` (Europe/Paris) holds ``ws-1`` and ``ws-2``; ``outsider`` is a member of
    ``ws-9`` in ``org-2`` only. Everyone was active this morning."""
    team.workspace("org-1", "ws-2")
    team.grant("member", "member", team.workspace("org-1", "ws-2"))
    team.grant("outsider", "member", team.workspace("org-2", "ws-9"))
    team.grant("outsider", "member", team.org("org-2"))
    async with nexus_db() as db:
        for uid in USERS:
            db.add(UserModel(id=uid, email=f"{uid}@example.com", name=uid))
        db.add(
            OrganizationModel(
                id="org-1", name="One", slug="one", owner_id="owner", timezone="Europe/Paris"
            )
        )
        db.add(OrganizationModel(id="org-2", name="Two", slug="two", owner_id="outsider"))
        for wid, org in (("ws-1", "org-1"), ("ws-2", "org-1"), ("ws-9", "org-2")):
            db.add(
                WorkspaceModel(
                    id=wid, name=f"Space {wid}", slug=wid, owner_id="owner", organization_id=org
                )
            )
        await db.flush()
        events = [
            ("e-member", "member", "ws-1", "s-m", "/workspace/ws-1/home"),
            ("e-member-2", "member", "ws-2", "s-m", "/workspace/ws-2/home"),
            ("e-viewer", "viewer", "ws-1", "s-v", "/workspace/ws-1/chat/conv-1"),
            # In ws-1 but no member of org-1: a platform admin passing through.
            ("e-stranger", "stranger", "ws-1", "s-s", "/workspace/ws-1/home"),
            ("e-outsider", "outsider", "ws-9", "s-o", "/workspace/ws-9/home"),
        ]
        await AnalyticsSecondaryAdapterPostgresEvents(db).apply_events(
            [
                RecordedEvent(
                    event_id=eid,
                    timestamp=T0,
                    session_id=sid,
                    event_name="page_viewed",
                    user_id=uid,
                    workspace_id=ws,
                    page_path=path,
                    page_title="Home",
                    payload={
                        "event_id": eid,
                        "timestamp": T0.isoformat() + "Z",
                        "session_id": sid,
                        "event_name": "page_viewed",
                        "user_id": uid,
                        "workspace_id": ws,
                        "page_path": path,
                    },
                )
                for eid, uid, ws, sid, path in events
            ],
            not_before=datetime(2026, 1, 1),
        )
        db.add(
            ConversationModel(
                id="conv-1",
                workspace_id="ws-1",
                user_id="viewer",
                title="Plans",
                agent="aia",
                created_at=T0,
                updated_at=T0,
            )
        )
        db.add(
            ConversationModel(
                id="conv-9",
                workspace_id="ws-9",
                user_id="outsider",
                title="Secret",
                agent="aia",
                created_at=T0,
                updated_at=T0,
            )
        )
        await db.flush()
        db.add(
            MessageModel(
                id="m-1", conversation_id="conv-1", role="user", content="hello", created_at=T0
            )
        )
        db.add(
            MessageModel(
                id="m-2",
                conversation_id="conv-1",
                role="assistant",
                content="hi",
                feedback="like",
                created_at=T0,
            )
        )
        db.add(
            MessageModel(
                id="m-9", conversation_id="conv-9", role="user", content="secret", created_at=T0
            )
        )
        await db.commit()
    return team


def _client(nexus_db, user: str) -> TestClient:
    app = FastAPI()
    app.include_router(scoped.organization_router, prefix="/api/organizations")
    app.include_router(scoped.workspace_router, prefix="/api/workspaces")

    async def db() -> AsyncIterator:
        async with nexus_db() as session:
            yield session

    def service(queries=scoped.Depends(scoped.get_analytics_queries)) -> ScopedAnalyticsService:
        return ScopedAnalyticsService(queries, now=lambda: NOW)

    async def registry(session=scoped.Depends(get_db)):
        return SimpleNamespace(chat=SimpleNamespace(adapter=ChatSecondaryAdapterPostgres(session)))

    app.dependency_overrides[get_db] = db
    app.dependency_overrides[get_current_user_required] = lambda: SimpleNamespace(
        id=user, email=f"{user}@example.com"
    )
    app.dependency_overrides[scoped.get_scoped_analytics] = service
    app.dependency_overrides[get_service_registry] = registry
    return TestClient(app)


READS = (
    "overview",
    "users",
    "users/member",
    "sessions",
    "pages",
    "events",
    "chats",
    "chat-analytics",
)


@pytest.mark.parametrize("user", ["member", "viewer", "stranger", "outsider"])
def test_only_admins_read_an_organization_s_analytics(world, nexus_db, user: str) -> None:
    client = _client(nexus_db, user)
    for path in (*READS, "workspaces"):
        assert client.get(f"{ORG}/{path}").status_code == 403, path
    for path in READS:
        assert client.get(f"{WS}/{path}").status_code == 403, path
    access = client.get(f"{ORG}/access")
    assert access.status_code == 200
    assert access.json() == {"can_read": False, "can_read_conversations": False, "timezone": "UTC"}


@pytest.mark.parametrize("user", ["owner", "admin"])
def test_owners_and_admins_read_both_scopes(world, nexus_db, user: str) -> None:
    client = _client(nexus_db, user)
    for path in (*READS, "workspaces"):
        assert client.get(f"{ORG}/{path}").status_code == 200, path
    for path in READS:
        assert client.get(f"{WS}/{path}").status_code == 200, path
    assert client.get(f"{ORG}/access").json() == {
        "can_read": True,
        "can_read_conversations": False,
        "timezone": "Europe/Paris",
    }
    assert client.get(f"{WS}/access").json()["can_read"] is True


def test_the_organization_counts_its_members_in_its_workspaces_only(world, nexus_db) -> None:
    client = _client(nexus_db, "admin")
    overview = client.get(f"{ORG}/overview", params={"period": "today"}).json()
    assert overview["kpi"]["active_users"] == 2  # member, viewer: not stranger nor outsider
    assert overview["kpi"]["workspaces_used"] == 2
    assert overview["period"]["timezone"] == "Europe/Paris"
    assert overview["period"]["granularity"] == "hour"
    assert overview["period"]["date_start"] == "2026-11-19T00:00:00+01:00"
    assert overview["active_users_over_time"][10] == {"date": "2026-11-19T10", "value": 2}

    users = client.get(f"{ORG}/users").json()
    assert {u["user_id"] for u in users["users"]} == {"member", "viewer"}
    directory = {d["user_id"]: d for d in users["directory"]}
    assert set(directory) == {"owner", "admin", "member", "viewer"}
    assert directory["member"]["user_email"] == "member@example.com"
    assert sorted(directory["member"]["workspace_ids"]) == ["ws-1", "ws-2"]
    assert sorted(directory["owner"]["workspace_ids"]) == ["ws-1", "ws-2"]

    workspaces = client.get(f"{ORG}/workspaces").json()
    assert {w["workspace_id"] for w in workspaces["directory"]} == {"ws-1", "ws-2"}
    assert {w["workspace_id"] for w in workspaces["workspaces"]} == {"ws-1", "ws-2"}

    events = client.get(f"{ORG}/events").json()["events"]
    assert {e["user_id"] for e in events} == {"member", "viewer"}
    assert {e["user_email"] for e in events} == {"member@example.com", "viewer@example.com"}


def test_the_workspace_counts_that_workspace_only(world, nexus_db) -> None:
    client = _client(nexus_db, "admin")
    overview = client.get(f"{WS}/overview").json()
    assert overview["kpi"]["active_users"] == 2
    assert overview["kpi"]["workspaces_used"] == 1
    pages = client.get(f"{WS}/pages").json()["pages"]
    assert "/workspace/ws-2/home" not in {p["page_path"] for p in pages}
    sessions = client.get(f"{WS}/sessions").json()["sessions"]
    assert {s["user_id"] for s in sessions} == {"member", "viewer"}
    assert client.get(f"{WS}/workspaces").status_code in (404, 405)


def test_filters_outside_the_scope_are_not_found(world, nexus_db) -> None:
    client = _client(nexus_db, "admin")
    assert client.get(f"{ORG}/overview", params={"workspace_id": "ws-9"}).status_code == 404
    assert client.get(f"{ORG}/overview", params={"user_id": "outsider"}).status_code == 404
    assert client.get(f"{ORG}/users/stranger").status_code == 404
    assert client.get(f"{WS}/users/outsider").status_code == 404
    assert client.get(f"{ORG}/chats/conv-9").status_code == 404
    assert client.get(f"{ORG}/chats/conv-9/export").status_code == 404
    assert client.get(f"{ORG}/overview", params={"period": "last_7_days"}).status_code == 422

    narrowed = client.get(f"{ORG}/overview", params={"workspace_id": "ws-2"}).json()
    assert narrowed["kpi"]["active_users"] == 1
    member = client.get(f"{ORG}/users/member").json()
    assert member["user_email"] == "member@example.com"
    assert member["total_page_views"] == 2
    assert {w["id"] for w in member["workspaces_used"]} == {"ws-1", "ws-2"}


def test_an_unknown_scope_is_refused(world, nexus_db) -> None:
    client = _client(nexus_db, "admin")
    assert client.get("/api/organizations/org-2/analytics/overview").status_code == 403
    assert client.get("/api/workspaces/ws-9/analytics/overview").status_code == 403


def test_conversations_show_metadata_and_need_the_policy_for_messages(world, nexus_db) -> None:
    client = _client(nexus_db, "admin")
    chats = client.get(f"{ORG}/chats").json()
    assert chats["can_read_messages"] is False
    assert [
        (c["conversation_id"], c["message_count"], c["user_id"], c["page_views"])
        for c in chats["chats"]
    ] == [("conv-1", 2, "viewer", 1)]
    analytics = client.get(f"{ORG}/chat-analytics").json()
    assert analytics["kpi"]["num_chats"] == 1
    assert analytics["kpi"]["messages_liked"] == 1

    assert client.get(f"{ORG}/chats/conv-1").status_code == 403
    assert client.get(f"{ORG}/chats/conv-1/export").status_code == 403
    assert client.get(f"{WS}/chats/conv-1").status_code == 403

    # A policy grants it in ws-1 (no role does).
    container = world.workspace("org-1", "ws-1")
    world.allow(
        "admin",
        ["nexus:ReadAnalyticsConversation"],
        ["${scope}/nexus:analytics_conversation/*"],
        container,
    )
    detail = client.get(f"{ORG}/chats/conv-1")
    assert detail.status_code == 200
    assert [m["content"] for m in detail.json()["messages"]] == ["hello", "hi"]
    assert client.get(f"{WS}/chats/conv-1/export", params={"format": "md"}).status_code == 200
    assert client.get(f"{ORG}/chats").json()["can_read_messages"] is True
    assert client.get(f"{ORG}/access").json()["can_read_conversations"] is True


def test_yesterday_is_empty_and_daily_periods_have_days(world, nexus_db) -> None:
    client = _client(nexus_db, "owner")
    assert (
        client.get(f"{ORG}/overview", params={"period": "yesterday"}).json()["kpi"]["active_users"]
        == 0
    )
    week = client.get(f"{ORG}/overview", params={"period": "this_week"}).json()
    assert week["period"]["granularity"] == "day"
    assert [p["date"] for p in week["sessions_over_time"]] == [
        "2026-11-16",
        "2026-11-17",
        "2026-11-18",
        "2026-11-19",
    ]
    assert sum(p["value"] for p in week["sessions_over_time"]) == 2
