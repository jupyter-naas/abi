"""Seeding binds the configuration to the rows it made, never to a person's of the
same slug; configured slugs are reserved. Real seeding, routes, adapters (SQLite)
and IAM."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import get_current_user_required
from naas_abi.apps.nexus.apps.api.app.core import config as nexus_config
from naas_abi.apps.nexus.apps.api.app.core import org_seed
from naas_abi.apps.nexus.apps.api.app.core.config import (
    OrganizationSeedConfig,
    WorkspaceSeedConfig,
)
from naas_abi.apps.nexus.apps.api.app.core.database import get_db
from naas_abi.apps.nexus.apps.api.app.models import (
    OrganizationModel,
    UserModel,
    WorkspaceModel,
)
from naas_abi.apps.nexus.apps.api.app.services.iam import authz
from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import MEMBERSHIPS
from naas_abi.apps.nexus.apps.api.app.services.iam.names import org_container
from naas_abi.apps.nexus.apps.api.app.services.iam.testing import NexusIam
from naas_abi.apps.nexus.apps.api.app.services.organizations.adapters.primary import (
    organizations__primary_adapter__FastAPI as org_api,
)
from naas_abi.apps.nexus.apps.api.app.services.workspaces.adapters.secondary import (
    resource_access_postgres,
)
from naas_abi.apps.nexus.apps.api.app.services.workspaces.adapters.secondary.postgres import (
    WorkspaceSecondaryAdapterPostgres,
)
from naas_abi.apps.nexus.apps.api.app.services.workspaces.port import WorkspaceCreateInput
from naas_abi.apps.nexus.apps.api.app.services.workspaces.service import (
    WorkspaceService,
    WorkspaceSlugAlreadyExistsError,
)
from sqlalchemy import select, text

SHARED_GRAPH = "http://ontology.naas.ai/graph/acme-deals"


def _acme(*workspaces: WorkspaceSeedConfig) -> OrganizationSeedConfig:
    return OrganizationSeedConfig(
        name="Acme", slug="acme", owner_email="ops@acme.example", workspaces=list(workspaces)
    )


async def _seed(factory, cfg: OrganizationSeedConfig) -> None:
    """What ``apply_configuration_seeds`` does for one organization."""
    roles = org_seed._declared_roles.set([])
    scopes = org_seed._declared_scopes.set([])
    try:
        async with factory() as session:
            async with session.begin():
                users = {u.email: u for u in (await session.execute(select(UserModel))).scalars()}
                await org_seed._upsert_organization(session, cfg, users)
        await org_seed._apply_declared_roles(
            org_seed._declared_scopes.get() or [], org_seed._declared_roles.get() or []
        )
    finally:
        org_seed._declared_roles.reset(roles)
        org_seed._declared_scopes.reset(scopes)


async def _rows(factory, model, **where):
    async with factory() as db:
        query = select(model)
        for column, value in where.items():
            query = query.where(getattr(model, column) == value)
        return list((await db.execute(query)).scalars())


@pytest.fixture
def people(nexus_db, nexus_iam: NexusIam, monkeypatch: pytest.MonkeyPatch):
    async def add() -> None:
        async with nexus_db() as db:
            for uid in ("pat", "ops"):
                db.add(UserModel(id=uid, email=f"{uid}@acme.example", name=uid.title()))
            await db.commit()

    for uid in ("pat", "ops"):
        nexus_iam.user(uid)
    monkeypatch.setattr(nexus_config.settings, "organizations", [])
    return add


def _org_routes(nexus_db, user: str) -> TestClient:
    async def db_dep():
        async with nexus_db() as session:
            yield session
            await session.commit()

    app = FastAPI()
    app.include_router(org_api.router, prefix="/organizations")
    app.dependency_overrides[get_db] = db_dep
    app.dependency_overrides[get_current_user_required] = lambda: SimpleNamespace(
        id=user, name=user.title(), is_superadmin=False
    )
    return TestClient(app)


async def _personal_workspace(nexus_db, slug: str) -> str:
    async with nexus_db() as db:
        service = WorkspaceService(adapter=WorkspaceSecondaryAdapterPostgres(db=db))
        record = await service.create_workspace(
            WorkspaceCreateInput(name="mine", slug=slug, owner_id="pat")
        )
        await db.commit()
        return record.id


@pytest.mark.asyncio
async def test_seeding_keeps_a_persons_organization_of_a_configured_slug(
    nexus_db, people, monkeypatch: pytest.MonkeyPatch
) -> None:
    await people()
    created = _org_routes(nexus_db, "pat").post(
        "/organizations", json={"name": "Acme too", "slug": "acme"}
    )
    assert created.status_code == 200, created.text
    mine = created.json()["id"]
    cfg = _acme(WorkspaceSeedConfig(slug="acme-finance"))
    monkeypatch.setattr(nexus_config.settings, "organizations", [cfg])

    await _seed(nexus_db, cfg)

    [org] = await _rows(nexus_db, OrganizationModel, slug="acme")
    assert (org.id, org.owner_id, org.name, org.seeded) == (mine, "pat", "Acme too", False)
    # None of the configuration lands in it: no workspace, no configured owner.
    assert await _rows(nexus_db, WorkspaceModel, slug="acme-finance") == []
    members = await MEMBERSHIPS.members(org_container(mine))
    assert [(m.user_id, m.role) for m in members] == [("pat", "owner")]


@pytest.mark.asyncio
async def test_seeding_keeps_a_persons_workspace_of_a_configured_slug(
    nexus_db, people, monkeypatch: pytest.MonkeyPatch
) -> None:
    await people()
    await _seed(nexus_db, _acme(WorkspaceSeedConfig(slug="acme-finance")))
    [acme] = await _rows(nexus_db, OrganizationModel, slug="acme")
    assert acme.seeded is True
    mine = await _personal_workspace(nexus_db, "acme-research")
    cfg = _acme(
        WorkspaceSeedConfig(slug="acme-finance"),
        WorkspaceSeedConfig(
            slug="acme-research", graphs={"read": [SHARED_GRAPH], "write": [SHARED_GRAPH]}
        ),
    )
    monkeypatch.setattr(nexus_config.settings, "organizations", [cfg])

    await _seed(nexus_db, cfg)

    [row] = await _rows(nexus_db, WorkspaceModel, id=mine)
    assert (row.organization_id, row.owner_id, row.seeded) == (None, "pat", False)
    async with nexus_db() as db:
        policy = await resource_access_postgres.load_resource_policy(db, mine, "graphs")
    assert SHARED_GRAPH not in policy.data["read"] + policy.data["write"]
    # The configured workspace before it in the same configuration still has its owner.
    [finance] = await _rows(nexus_db, WorkspaceModel, slug="acme-finance")
    assert await authz.AUTHZ.allowed("UpdateWorkspace", user="ops", workspace=finance.id)
    assert not await authz.AUTHZ.allowed("UpdateWorkspace", user="pat", workspace=finance.id)


@pytest.mark.asyncio
async def test_configured_slugs_keep_to_seeding_at_create_and_rename(
    nexus_db, people, monkeypatch: pytest.MonkeyPatch
) -> None:
    await people()
    monkeypatch.setattr(
        nexus_config.settings,
        "organizations",
        [_acme(WorkspaceSeedConfig(slug="acme-finance"))],
    )
    http = _org_routes(nexus_db, "pat")

    assert http.post("/organizations", json={"name": "A", "slug": "acme"}).status_code == 400
    own = http.post("/organizations", json={"name": "Mine", "slug": "mine"})
    assert own.status_code == 200, own.text
    org_id = own.json()["id"]
    assert http.patch(f"/organizations/{org_id}", json={"slug": "acme"}).status_code == 400
    assert http.patch(f"/organizations/{org_id}", json={"slug": "Not A Slug"}).status_code == 422
    assert http.patch(f"/organizations/{org_id}", json={"slug": "mine-two"}).status_code == 200
    with pytest.raises(WorkspaceSlugAlreadyExistsError):
        await _personal_workspace(nexus_db, "acme-finance")


@pytest.mark.asyncio
async def test_seeding_finds_its_rows_from_before_the_flag_where_it_left_them(
    nexus_db, people
) -> None:
    await people()
    async with nexus_db() as db:
        # Rows an earlier version seeded (no flag): the configured owner's organization,
        # its workspace inside it; and a person's organization of another configured slug.
        db.add(OrganizationModel(id="org-old", name="Acme", slug="acme", owner_id="ops"))
        db.add(
            WorkspaceModel(
                id="ws-old",
                name="Finance",
                slug="acme-finance",
                owner_id="ops",
                organization_id="org-old",
            )
        )
        db.add(OrganizationModel(id="org-p", name="Beta", slug="beta", owner_id="pat"))
        await db.flush()
        # The column of a database older than the flag: NULL.
        await db.execute(text("UPDATE organizations SET seeded = NULL"))
        await db.execute(text("UPDATE workspaces SET seeded = NULL"))
        await db.commit()

    await _seed(nexus_db, _acme(WorkspaceSeedConfig(slug="acme-finance")))
    await _seed(
        nexus_db,
        OrganizationSeedConfig(name="Beta", slug="beta", owner_email="ops@acme.example"),
    )

    [acme] = await _rows(nexus_db, OrganizationModel, id="org-old")
    [finance] = await _rows(nexus_db, WorkspaceModel, id="ws-old")
    [beta] = await _rows(nexus_db, OrganizationModel, id="org-p")
    assert (acme.seeded, finance.seeded) == (True, True)
    assert (beta.seeded, beta.owner_id) == (None, "pat")


@pytest.mark.asyncio
async def test_one_failing_configured_scope_keeps_the_others_roles(
    nexus_db, people, monkeypatch: pytest.MonkeyPatch
) -> None:
    await people()
    register = MEMBERSHIPS.register_workspace
    async with nexus_db() as db:
        db.add(OrganizationModel(id="org-1", name="Acme", slug="acme", owner_id="ops", seeded=True))
        await db.commit()

    async def failing(org_id, workspace_id):
        [row] = await _rows(nexus_db, WorkspaceModel, id=workspace_id)
        if row.slug == "acme-a":
            raise RuntimeError("refused")
        return await register(org_id, workspace_id)

    monkeypatch.setattr(MEMBERSHIPS, "register_workspace", failing)
    await _seed(
        nexus_db,
        _acme(WorkspaceSeedConfig(slug="acme-a"), WorkspaceSeedConfig(slug="acme-b")),
    )

    [b] = await _rows(nexus_db, WorkspaceModel, slug="acme-b")
    assert await authz.AUTHZ.allowed("UpdateWorkspace", user="ops", workspace=b.id)
