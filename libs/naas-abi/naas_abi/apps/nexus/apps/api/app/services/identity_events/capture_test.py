"""Identity changes committed through the ORM become identity events.

Runs against a real SQLite session and a real EventService so the whole path
(flush → commit → publish → stored payload) is exercised.
"""

from __future__ import annotations

import datetime
import json

import pytest
import pytest_asyncio
from naas_abi.apps.nexus.apps.api.app.models import (
    AgentConfigModel,
    AppConfigModel,
    OrganizationMemberModel,
    OrganizationModel,
    OrganizationRoleFeaturesModel,
    UserModel,
    WorkspaceMemberModel,
    WorkspaceModel,
)
from naas_abi.apps.nexus.apps.api.app.services.identity_events.capture import (
    IdentityEventCapture,
)
from naas_abi.apps.nexus.apps.api.app.services.identity_graph.iris import (
    deployment_site_iri,
    person_iri,
    user_account_iri,
    workspace_iri,
    workspace_membership_iri,
)
from naas_abi_core.services.event.adapters.secondary.EventSQLiteAdapter import (
    EventSQLiteAdapter,
)
from naas_abi_core.services.event.context import (
    event_actor_user_id,
    event_actor_workspace_id,
    event_triggered_via,
)
from naas_abi_core.services.event.EventService import EventService
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

T0 = datetime.datetime(2026, 5, 1, 9, 30)
SITE = str(deployment_site_iri("bob.example.com"))

_TABLES = (
    UserModel,
    OrganizationModel,
    OrganizationMemberModel,
    OrganizationRoleFeaturesModel,
    WorkspaceModel,
    WorkspaceMemberModel,
    AppConfigModel,
    AgentConfigModel,
)


@pytest_asyncio.fixture
async def env(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'nexus.db'}")
    async with engine.begin() as conn:
        for model in _TABLES:
            await conn.run_sync(model.__table__.create)
    events = EventService(adapter=EventSQLiteAdapter(str(tmp_path / "events.sqlite")))
    published: list[int] = []
    capture = IdentityEventCapture(
        publish=events.publish,
        site_iri=SITE,
        on_published=lambda count: published.append(count),
    )
    capture.install()
    maker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield maker, events, published
    finally:
        capture.uninstall()
        await engine.dispose()


def _payloads(events: EventService) -> list[dict]:
    from naas_abi_core.services.event import EventCodec

    return [json.loads(EventCodec.serialize(e)) for e in events.query()]


def _kind(payload: dict) -> str:
    return payload["_class_uri"].rsplit("/", 1)[-1]


async def _seed_user(maker, user_id="usr-1", **extra) -> None:
    async with maker() as session:
        session.add(
            UserModel(
                id=user_id,
                email=f"{user_id}@example.com",
                name="Alice",
                hashed_password="x",
                **extra,
            )
        )
        await session.commit()


@pytest.mark.asyncio
async def test_creating_a_user_logs_create_user_with_the_graph_iris(env) -> None:
    maker, events, published = env

    await _seed_user(maker)

    [event] = _payloads(events)
    assert _kind(event) == "CreateUser"
    assert event["target_user_id"] == "usr-1"
    assert event["creates"] == [str(user_account_iri("usr-1"))]
    assert event["created_for"] == [str(person_iri("usr-1"))]
    assert event["occurs_in"] == [SITE]
    assert published == [1]


@pytest.mark.asyncio
async def test_the_actor_comes_from_the_request_context(env) -> None:
    maker, events, _ = env
    tokens = (event_actor_user_id.set("usr-admin"), event_triggered_via.set("api"))
    try:
        await _seed_user(maker, "usr-9")
    finally:
        event_actor_user_id.reset(tokens[0])
        event_triggered_via.reset(tokens[1])

    [event] = _payloads(events)
    assert event["created_by"] == [str(person_iri("usr-admin"))]
    assert (event["actor_user_id"], event["triggered_via"]) == ("usr-admin", "api")


@pytest.mark.asyncio
async def test_profile_changes_name_the_fields_but_never_log_personal_values(env) -> None:
    maker, events, _ = env
    await _seed_user(maker)
    async with maker() as session:
        user = await session.get(UserModel, "usr-1")
        user.name = "Alice Martin"
        user.email = "alice.martin@example.com"
        user.hashed_password = "y"
        await session.commit()

    event = _payloads(events)[-1]
    assert _kind(event) == "UpdateUser"
    assert sorted(event["changed_fields"]) == ["email", "name", "password"]
    raw = json.dumps(event)
    assert "Alice Martin" not in raw and "alice.martin@" not in raw
    assert event["updates"] == [str(user_account_iri("usr-1"))]


@pytest.mark.asyncio
async def test_superadmin_changes_keep_their_before_and_after(env) -> None:
    maker, events, _ = env
    await _seed_user(maker)
    async with maker() as session:
        (await session.get(UserModel, "usr-1")).is_superadmin = True
        await session.commit()

    event = _payloads(events)[-1]
    assert json.loads(event["changes_json"]) == {"is_superadmin": {"from": False, "to": True}}


@pytest.mark.asyncio
async def test_workspace_membership_lifecycle(env) -> None:
    maker, events, _ = env
    await _seed_user(maker)
    async with maker() as session:
        session.add(WorkspaceModel(id="ws-1", name="Acme", slug="acme", owner_id="usr-1"))
        session.add(
            WorkspaceMemberModel(id="m-1", workspace_id="ws-1", user_id="usr-1", role="member")
        )
        await session.commit()
    async with maker() as session:
        (await session.get(WorkspaceMemberModel, "m-1")).role = "admin"
        await session.commit()
    async with maker() as session:
        await session.delete(await session.get(WorkspaceMemberModel, "m-1"))
        await session.commit()

    kinds = [_kind(e) for e in _payloads(events)]
    assert kinds == [
        "CreateUser",
        "CreateWorkspace",
        "AddUserToWorkspace",
        "ChangeWorkspaceMemberRole",
        "RemoveUserFromWorkspace",
    ]
    added, changed, removed = _payloads(events)[2:]
    membership = str(workspace_membership_iri("ws-1", "usr-1"))
    assert added["creates"] == [membership]
    assert set(added["updates"]) == {str(user_account_iri("usr-1")), str(workspace_iri("ws-1"))}
    assert (added["membership_role"], added["target_workspace_id"]) == ("member", "ws-1")
    assert (changed["previous_membership_role"], changed["membership_role"]) == ("member", "admin")
    assert changed["updates"] == [membership]
    assert removed["deletes"] == [membership]


@pytest.mark.asyncio
async def test_workspace_updates_keep_non_personal_before_and_after(env) -> None:
    maker, events, _ = env
    await _seed_user(maker)
    async with maker() as session:
        session.add(WorkspaceModel(id="ws-1", name="Acme", slug="acme", owner_id="usr-1"))
        await session.commit()
    async with maker() as session:
        ws = await session.get(WorkspaceModel, "ws-1")
        ws.primary_color = "#0057B8"
        await session.commit()

    event = _payloads(events)[-1]
    assert _kind(event) == "UpdateWorkspace"
    assert event["target_workspace_id"] == "ws-1"
    assert json.loads(event["changes_json"])["primary_color"]["to"] == "#0057B8"


@pytest.mark.asyncio
async def test_organization_member_and_role_features(env) -> None:
    maker, events, _ = env
    await _seed_user(maker)
    async with maker() as session:
        session.add(
            OrganizationModel(id="org-1", name="Acme Group", slug="acme-group", owner_id="usr-1")
        )
        session.add(
            OrganizationMemberModel(
                id="om-1", organization_id="org-1", user_id="usr-1", role="owner"
            )
        )
        session.add(
            OrganizationRoleFeaturesModel(
                organization_id="org-1", role_baseline='{"viewer": ["chat"]}'
            )
        )
        await session.commit()

    kinds = [_kind(e) for e in _payloads(events)][1:]
    assert kinds == [
        "CreateOrganization",
        "AddUserToOrganization",
        "ConfigureOrganizationRoleFeatures",
    ]
    assert all(e["target_organization_id"] == "org-1" for e in _payloads(events)[1:])


@pytest.mark.asyncio
async def test_app_and_agent_configuration(env) -> None:
    maker, events, _ = env
    await _seed_user(maker)
    async with maker() as session:
        session.add(WorkspaceModel(id="ws-1", name="Acme", slug="acme", owner_id="usr-1"))
        session.add(
            AppConfigModel(id="a-1", workspace_id="ws-1", app_id="external.acme:web", enabled=True)
        )
        session.add(
            AgentConfigModel(
                id="g-1",
                workspace_id="ws-1",
                name="Bob",
                class_name="BobAgent",
                system_prompt="secret sauce",
            )
        )
        await session.commit()

    app, agent = _payloads(events)[2:]
    assert _kind(app) == "ConfigureWorkspaceApp"
    assert json.loads(app["changes_json"])["app_id"]["to"] == "external.acme:web"
    assert _kind(agent) == "ConfigureWorkspaceAgent"
    assert "system_prompt" in agent["changed_fields"]
    assert "secret sauce" not in json.dumps(agent)


@pytest.mark.asyncio
async def test_rolled_back_changes_log_nothing(env) -> None:
    maker, events, published = env
    async with maker() as session:
        session.add(UserModel(id="usr-1", email="a@example.com", name="A", hashed_password="x"))
        await session.flush()
        await session.rollback()

    assert events.query() == []
    assert published == []


@pytest.mark.asyncio
async def test_touching_only_bookkeeping_columns_logs_nothing(env) -> None:
    maker, events, _ = env
    await _seed_user(maker)
    async with maker() as session:
        user = await session.get(UserModel, "usr-1")
        user.updated_at = datetime.datetime(2030, 1, 1)
        user.name = "Alice"  # same value
        await session.commit()

    assert [_kind(e) for e in _payloads(events)] == ["CreateUser"]


@pytest.mark.asyncio
async def test_workspace_context_is_stamped(env) -> None:
    maker, events, _ = env
    await _seed_user(maker)
    token = event_actor_workspace_id.set("ws-ctx")
    try:
        async with maker() as session:
            (await session.get(UserModel, "usr-1")).company = "Acme"
            await session.commit()
    finally:
        event_actor_workspace_id.reset(token)

    assert _payloads(events)[-1]["actor_workspace_id"] == "ws-ctx"


@pytest.mark.asyncio
async def test_a_failing_publisher_never_breaks_the_commit(env, tmp_path) -> None:
    maker, events, _ = env

    def broken(_event):
        raise RuntimeError("event log down")

    capture = IdentityEventCapture(publish=broken, site_iri=SITE)
    capture.install()
    try:
        await _seed_user(maker, "usr-7")
    finally:
        capture.uninstall()

    async with maker() as session:
        assert await session.get(UserModel, "usr-7") is not None


@pytest.mark.asyncio
async def test_bulk_statements_on_identity_tables_are_reported(env) -> None:
    """Bulk UPDATE/DELETE bypass the ORM: they cannot be logged, so they are flagged."""
    from sqlalchemy import delete, update

    maker, events, _ = env
    await _seed_user(maker)
    bypassed: list[str] = []
    capture = IdentityEventCapture(publish=lambda _e: None, on_bypass=bypassed.append)
    capture.install()
    try:
        async with maker() as session:
            await session.execute(
                update(UserModel).where(UserModel.id == "usr-1").values(company="Acme")
            )
            await session.execute(
                delete(AppConfigModel).where(AppConfigModel.workspace_id == "ws-x")
            )
            await session.commit()
    finally:
        capture.uninstall()

    assert bypassed == ["UPDATE users", "DELETE app_configs"]
