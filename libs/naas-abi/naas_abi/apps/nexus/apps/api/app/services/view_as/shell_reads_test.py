"""What the shell and the pages of a workspace ask that names no workspace, answered in a view
and held to the viewed one: the organization's record, the model catalog, a policy by id, the
groups of a person. Everything of another workspace or organization stays outside.

The real routes of the application over the test world of ``view_as_http_test``.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from naas_abi.apps.nexus.apps.api.app.models import OrganizationModel
from naas_abi.apps.nexus.apps.api.app.services.iam.names import org_container
from naas_abi.apps.nexus.apps.api.app.services.view_as.full_app_testing import (
    bind_database,
    build_full_app,
    engine_iam_installed,
    services_installed,
)
from naas_abi.apps.nexus.apps.api.app.services.view_as.view_as_http_test import (  # noqa: F401
    ALPHA,
    ORG,
    start,
)
from naas_abi_core.engine.call_context import as_service_account

OUTSIDE = "Outside this view: you are viewing as Olivia in Alpha"
DOCUMENT = {
    "version": "2026-10-13",
    "statements": [
        {"effect": "Allow", "actions": ["nexus:GetWorkspace"], "resources": ["${scope}/*"]}
    ],
}


@pytest_asyncio.fixture
async def full(world, monkeypatch):
    app = build_full_app()
    bind_database(monkeypatch)
    async with world.sessions() as db:
        db.add(OrganizationModel(id="zeta", name="Zeta", slug="zeta", owner_id="owner"))
        await db.commit()
    zeta = world.nexus.org("zeta")
    # Olivia administers both organizations: she may read what the view must still keep out.
    world.nexus.grant("olivia", "admin", zeta)
    world.app = app
    with services_installed(), engine_iam_installed(world.iam):
        yield world


def _policy(world, name: str, scope: str | None) -> str:
    with as_service_account("engine"):
        return world.iam.create_policy(name, DOCUMENT, scope=scope).id


@pytest.mark.asyncio
async def test_the_shell_reads_the_organization_of_the_viewed_workspace_and_no_other(full) -> None:
    root = await full.sign_in("root")
    assert (await start(root, full, "olivia")).status_code == 200

    own = await root.get(f"/api/organizations/{ORG}")
    assert own.status_code == 200, own.text
    assert own.json()["id"] == ORG

    other = await root.get("/api/organizations/zeta")
    assert other.status_code == 403
    assert other.json()["detail"] == OUTSIDE
    # What lists the organization's people and workspaces stays outside: the web does not ask.
    for path in (f"/api/organizations/{ORG}/members", f"/api/organizations/{ORG}/workspaces"):
        refused = await root.get(path)
        assert refused.status_code == 403, path
        assert refused.json()["detail"] == OUTSIDE, path


@pytest.mark.asyncio
async def test_the_organization_is_read_as_before_outside_a_view(full) -> None:
    root = await full.sign_in("root")
    assert (await root.get("/api/organizations/zeta")).status_code == 200
    await start(root, full, "olivia")
    await root.delete("/api/iam/view-as")
    assert (await root.get("/api/organizations/zeta")).status_code == 200


@pytest.mark.asyncio
async def test_a_person_who_may_not_read_the_organization_is_refused_as_they_are(full) -> None:
    """The view decides as the person: Carol has no right on Acme itself, so the shell's read is
    the refusal she would get (not the view's notice)."""
    root = await full.sign_in("root")
    await start(root, full, "carol")
    refused = await root.get(f"/api/organizations/{ORG}")
    assert refused.status_code == 403
    assert not refused.json()["detail"].startswith("Outside this view")


@pytest.mark.asyncio
async def test_the_model_catalog_is_answered_in_a_view(full) -> None:
    root = await full.sign_in("root")
    await start(root, full, "olivia")

    answered = await root.get("/api/providers/models")

    assert answered.status_code == 200, answered.text
    assert isinstance(answered.json(), list)


@pytest.mark.asyncio
async def test_a_policy_is_read_by_id_inside_the_view_only(full) -> None:
    mine = _policy(full, "alpha-policy", full.alpha)
    org = _policy(full, "acme-policy", org_container(ORG))
    bravo = _policy(full, "bravo-policy", full.bravo)
    zeta = _policy(full, "zeta-policy", org_container("zeta"))
    root = await full.sign_in("root")
    await start(root, full, "olivia")

    for name, allowed in (("mine", mine), ("org", org)):
        answered = await root.get(f"/api/iam/admin/policies/{allowed}")
        assert answered.status_code == 200, (name, answered.text)
        assert answered.json()["id"] == allowed
    for outside in (bravo, zeta):
        refused = await root.get(f"/api/iam/admin/policies/{outside}")
        assert refused.status_code == 403, outside
        assert refused.json()["detail"] == OUTSIDE
    # Outside a view the platform admin reads them all.
    await root.delete("/api/iam/view-as")
    assert (await root.get(f"/api/iam/admin/policies/{bravo}")).status_code == 200


@pytest.mark.asyncio
async def test_the_groups_of_a_person_are_the_viewed_workspaces_only(full) -> None:
    with as_service_account("engine"):
        mine = full.iam.create_group("alpha-team", scope=full.alpha)
        theirs = full.iam.create_group("bravo-team", scope=full.bravo)
        platform = full.iam.create_group("everyone")
        for group in (mine, theirs, platform):
            full.iam.add_group_member(group.id, full.principals["carol"])
    root = await full.sign_in("root")
    await start(root, full, "olivia")
    path = f"/api/iam/admin/principals/{full.principals['carol']}/groups"

    seen = (await root.get(path)).json()["items"]
    assert [g["id"] for g in seen] == [mine.id]

    await root.delete("/api/iam/view-as")
    every = {g["id"] for g in (await root.get(path)).json()["items"]}
    assert {mine.id, theirs.id, platform.id} <= every


@pytest.mark.asyncio
async def test_a_person_is_still_not_read_by_id_in_a_view(full) -> None:
    root = await full.sign_in("root")
    await start(root, full, "olivia")
    for path in (
        f"/api/iam/admin/principals/{full.principals['dave']}",
        "/api/iam/admin/principals",
    ):
        refused = await root.get(path)
        assert refused.status_code == 403, path
        assert refused.json()["detail"] == OUTSIDE
