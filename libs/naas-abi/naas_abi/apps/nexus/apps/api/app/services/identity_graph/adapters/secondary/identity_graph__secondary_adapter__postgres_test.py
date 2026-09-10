from __future__ import annotations

import datetime
import json

import pytest
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
from naas_abi.apps.nexus.apps.api.app.services.identity_graph.adapters.secondary.identity_graph__secondary_adapter__postgres import (  # noqa: E501
    IdentitySourceSecondaryAdapterPostgres,
)
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

T0 = datetime.datetime(2026, 5, 1, 9, 30)
T1 = datetime.datetime(2026, 5, 2, 9, 30)

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


@pytest.mark.asyncio
async def test_load_snapshot_reads_every_identity_table(tmp_path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'nexus.db'}")
    async with engine.begin() as conn:
        for model in _TABLES:
            await conn.run_sync(model.__table__.create)
    session = async_sessionmaker(engine, expire_on_commit=False)()
    session.add_all(
        [
            UserModel(
                id="usr-1",
                email="alice@example.com",
                name="Alice",
                hashed_password="x",
                company="Acme",
                role="CTO",
                is_superadmin=True,
                created_at=T0,
            ),
            UserModel(
                id="usr-2", email="bob@example.com", name="Bob", hashed_password="x", created_at=T1
            ),
            OrganizationModel(
                id="org-1",
                name="Acme Group",
                slug="acme-group",
                owner_id="usr-1",
                primary_color="#0057B8",
                created_at=T0,
            ),
            OrganizationMemberModel(
                id="om-1", organization_id="org-1", user_id="usr-2", role="admin", created_at=T1
            ),
            OrganizationRoleFeaturesModel(
                organization_id="org-1", role_baseline=json.dumps({"viewer": ["chat"]})
            ),
            WorkspaceModel(
                id="ws-1",
                name="Acme",
                slug="acme",
                owner_id="usr-1",
                organization_id="org-1",
                background_image_url="bg.webp",
                created_at=T0,
            ),
            WorkspaceMemberModel(
                id="mem-1", workspace_id="ws-1", user_id="usr-2", role="admin", created_at=T1
            ),
            AppConfigModel(
                id="app-1", workspace_id="ws-1", app_id="external.acme:web", enabled=True
            ),
            AgentConfigModel(
                id="agc-1",
                workspace_id="ws-1",
                name="Bob",
                class_name="BobAgent",
                module_path="bob",
                enabled=True,
                is_default=1,
            ),
        ]
    )
    await session.commit()

    snapshot = await IdentitySourceSecondaryAdapterPostgres(session).load_snapshot()
    await session.close()
    await engine.dispose()

    alice = snapshot.users[0]
    assert (alice.id, alice.name, alice.email, alice.created_at) == (
        "usr-1",
        "Alice",
        "alice@example.com",
        T0,
    )
    assert (alice.company, alice.job_title, alice.is_superadmin) == ("Acme", "CTO", True)
    assert [u.id for u in snapshot.users] == ["usr-1", "usr-2"]

    [org] = snapshot.organizations
    assert (org.id, org.slug, org.owner_id, org.profile["primary_color"]) == (
        "org-1",
        "acme-group",
        "usr-1",
        "#0057B8",
    )
    assert [(m.organization_id, m.user_id, m.role) for m in snapshot.organization_memberships] == [
        ("org-1", "usr-2", "admin")
    ]
    assert snapshot.organization_role_features == {"org-1": {"viewer": ["chat"]}}

    [ws] = snapshot.workspaces
    assert (ws.id, ws.slug, ws.organization_id, ws.owner_id) == ("ws-1", "acme", "org-1", "usr-1")
    assert ws.settings["background_image_url"] == "bg.webp"
    assert [(m.workspace_id, m.user_id, m.role) for m in snapshot.memberships] == [
        ("ws-1", "usr-2", "admin")
    ]
    assert [(a.workspace_id, a.app_id, a.enabled) for a in snapshot.app_configs] == [
        ("ws-1", "external.acme:web", True)
    ]
    [agent] = snapshot.agent_configs
    assert (agent.id, agent.class_name, agent.enabled, agent.is_default) == (
        "agc-1",
        "BobAgent",
        True,
        True,
    )


@pytest.mark.asyncio
async def test_unparseable_role_features_are_skipped(tmp_path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'nexus.db'}")
    async with engine.begin() as conn:
        for model in _TABLES:
            await conn.run_sync(model.__table__.create)
    session = async_sessionmaker(engine, expire_on_commit=False)()
    session.add(OrganizationRoleFeaturesModel(organization_id="org-1", role_baseline="{not json"))
    await session.commit()

    snapshot = await IdentitySourceSecondaryAdapterPostgres(session).load_snapshot()
    await session.close()
    await engine.dispose()

    assert snapshot.organization_role_features == {}
