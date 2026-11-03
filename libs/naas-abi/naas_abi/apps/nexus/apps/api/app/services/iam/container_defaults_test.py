"""Each organization and workspace has its access policy and default groups
(``container_defaults``): made with it, kept in step with its roles, forgotten with
it, and given once to those that predate them, nobody gaining or losing access.

The real services and a SQLite database, with a real IAM: nothing about who may do
what is mocked."""

from __future__ import annotations

from datetime import datetime

import pytest
from naas_abi.apps.nexus.apps.api.app.models import UserModel
from naas_abi.apps.nexus.apps.api.app.services.iam import container_defaults
from naas_abi.apps.nexus.apps.api.app.services.iam import policy_tree_test as previous
from naas_abi.apps.nexus.apps.api.app.services.iam.container_defaults import (
    CONTAINER_DEFAULTS,
    NOTHING_SID,
    SqlDefaultsStore,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.membership_routes_test import (  # noqa: F401
    api,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import MEMBERSHIPS
from naas_abi.apps.nexus.apps.api.app.services.iam.names import (
    org_below,
    org_container,
    workspace_container,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.policy_tree_test import (  # noqa: F401
    _remote_agents,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.testing import NexusIam
from naas_abi.apps.nexus.apps.api.app.services.organizations.adapters.secondary.postgres import (  # noqa: E501
    OrganizationSecondaryAdapterPostgres,
)
from naas_abi.apps.nexus.apps.api.app.services.organizations.service import (
    OrganizationHasWorkspacesError,
    OrganizationService,
)
from naas_abi.apps.nexus.apps.api.app.services.workspaces.adapters.secondary.postgres import (  # noqa: E501
    WorkspaceSecondaryAdapterPostgres,
)
from naas_abi.apps.nexus.apps.api.app.services.workspaces.port import WorkspaceCreateInput
from naas_abi.apps.nexus.apps.api.app.services.workspaces.service import WorkspaceService
from naas_abi_core.engine.call_context import as_service_account, use_call_context
from naas_abi_core.services.iam import module_scopes
from naas_abi_core.services.iam.IAMPorts import IAMNotFoundError, PermissionDeniedError
from naas_abi_core.services.iam.names import PLATFORM

NOW = datetime(2026, 1, 1)
USE = "module:UseAgent"


@pytest.fixture(autouse=True)
def _fresh_defaults():
    CONTAINER_DEFAULTS.forget_all()
    CONTAINER_DEFAULTS.session_factory = None
    yield
    CONTAINER_DEFAULTS.forget_all()
    CONTAINER_DEFAULTS.session_factory = None


@pytest.fixture
def world():
    nexus = NexusIam(features_with_roles=False)
    with nexus.installed():
        yield nexus


def _agent(container: str, name: str) -> str:
    return module_scopes.scope_resource("agent", "people", name, container=container)


def _agents(*names: str) -> dict:
    return {
        "version": "2026-10-13",
        "statements": [
            {
                "effect": "Allow",
                "actions": [USE],
                "resources": [f"${{scope}}/module:agent/people/{n}" for n in names],
            }
        ],
    }


def _uses(nexus: NexusIam, user: str, resource: str) -> bool:
    with use_call_context(NexusIam.context(user)):
        return nexus.iam.authorize(USE, resource).allowed


def _members(nexus: NexusIam, group_id: str) -> set[str]:
    with as_service_account("api"):
        principals = nexus.iam.list_group_members(group_id)
        return {nexus.iam.get_principal(p).subject for p in principals}


async def _users(db, *ids: str) -> None:
    for user_id in ids:
        db.add(
            UserModel(
                id=user_id,
                email=f"{user_id}@example.com",
                name=user_id.title(),
                created_at=NOW,
                updated_at=NOW,
            )
        )
    await db.flush()


async def _acme(nexus_db):
    """Olivia creates Acme, then Alpha in it, as the routes do."""
    async with nexus_db() as db:
        await _users(db, "olivia", "bob", "carol", "dave", "root")
        orgs = OrganizationService(adapter=OrganizationSecondaryAdapterPostgres(db=db))
        org = await orgs.create_organization(
            name="Acme", slug="acme", owner_id="olivia", now=NOW, org_id="acme"
        )
        workspaces = WorkspaceService(adapter=WorkspaceSecondaryAdapterPostgres(db=db))
        ws = await workspaces.create_workspace(
            WorkspaceCreateInput(
                name="Alpha", slug="alpha", owner_id="olivia", organization_id="acme", id="alpha"
            )
        )
        await db.commit()
        store = SqlDefaultsStore(db)
        return org, ws, await store.get(org_container("acme")), await store.get(ALPHA)


ALPHA = workspace_container("acme", "alpha")


# -- made with the container ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_new_organization_and_workspace_get_their_access_and_groups(world, nexus_db):
    _org, _ws, org_record, ws_record = await _acme(nexus_db)
    assert org_record is not None and ws_record is not None
    with as_service_account("api"):
        org_access = world.iam.get_policy(org_record.access_policy_id)
        ws_access = world.iam.get_policy(ws_record.access_policy_id)
        org_groups = {g.id: g for g in world.iam.list_groups(scope=org_container("acme")).items}
        ws_groups = {
            g.id: g for g in world.iam.list_groups(scope=ALPHA).items if g.owner_scope == ALPHA
        }
        org_admins_hold = world.iam.list_attachments(principal_id=org_record.admins_group_id)
        ws_admins_hold = world.iam.list_attachments(principal_id=ws_record.admins_group_id)
    # "<O> access": the platform's, allowing nothing yet.
    assert (org_access.name, org_access.owner_scope) == ("Acme access", PLATFORM)
    assert [s.sid for s in org_access.document.statements] == [NOTHING_SID]
    # "<W> access": the workspace's, a sub-policy of the organization's.
    assert (ws_access.name, ws_access.owner_scope, ws_access.parent_id) == (
        "Alpha access",
        ALPHA,
        org_access.id,
    )
    assert {g.name for g in org_groups.values()} == {"Acme members", "Acme admins"}
    assert {g.name for g in ws_groups.values()} == {"Alpha members", "Alpha admins"}
    # The admins hold the access policy: the org's below it, the workspace's at it.
    assert [(a.policy_id, a.scope) for a in org_admins_hold] == [(org_access.id, org_below("acme"))]
    assert [(a.policy_id, a.scope) for a in ws_admins_hold] == [(ws_access.id, ALPHA)]
    # The creator, owner of both, is in both groups of each.
    for record in (org_record, ws_record):
        assert _members(world, record.members_group_id) == {"olivia"}
        assert _members(world, record.admins_group_id) == {"olivia"}


@pytest.mark.asyncio
async def test_the_groups_follow_the_roles(world, nexus_db):
    _org, _ws, org_record, ws_record = await _acme(nexus_db)
    await MEMBERSHIPS.grant("bob", "owner", ALPHA)
    await MEMBERSHIPS.grant("carol", "admin", ALPHA)
    await MEMBERSHIPS.grant("dave", "member", ALPHA)
    assert _members(world, ws_record.members_group_id) == {"olivia", "bob", "carol", "dave"}
    assert _members(world, ws_record.admins_group_id) == {"olivia", "bob", "carol"}
    # A role change, and a role taken.
    await MEMBERSHIPS.grant("carol", "member", ALPHA)
    await MEMBERSHIPS.revoke("dave", ALPHA)
    assert _members(world, ws_record.members_group_id) == {"olivia", "bob", "carol"}
    assert _members(world, ws_record.admins_group_id) == {"olivia", "bob"}
    # The organization's follow its own roles, not its workspaces'.
    assert _members(world, org_record.members_group_id) == {"olivia"}
    await MEMBERSHIPS.grant("dave", "viewer", org_container("acme"))
    assert _members(world, org_record.members_group_id) == {"olivia", "dave"}
    assert _members(world, org_record.admins_group_id) == {"olivia"}


@pytest.mark.asyncio
async def test_a_role_changed_in_another_process_is_followed_from_the_database(world, nexus_db):
    _org, _ws, _org_record, ws_record = await _acme(nexus_db)
    CONTAINER_DEFAULTS.forget_all()  # this process never saw Alpha made
    CONTAINER_DEFAULTS.session_factory = nexus_db
    await MEMBERSHIPS.grant("bob", "admin", ALPHA)
    assert "bob" in _members(world, ws_record.admins_group_id)


# -- the ceiling ----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_new_workspace_exposes_nothing_until_widened_and_narrows_below_it(world, nexus_db):
    """Zero trust: nothing until the platform admin widens Acme and whoever holds
    more widens Alpha. A member policy made in Alpha is a sub-policy of its access:
    narrowing Alpha narrows it at once."""
    _org, _ws, org_record, ws_record = await _acme(nexus_db)
    await MEMBERSHIPS.grant("bob", "owner", ALPHA)
    await MEMBERSHIPS.grant("dave", "member", ALPHA)
    assert not _uses(world, "olivia", _agent(ALPHA, "recruiter"))
    assert not _uses(world, "bob", _agent(ALPHA, "recruiter"))
    world.platform_admin("root")
    with use_call_context(NexusIam.context("root")):
        world.iam.update_policy(
            org_record.access_policy_id,
            expected_revision=1,
            document=_agents("recruiter", "scout", "coach"),
        )
    # Olivia, an admin of Acme, uses what Acme may in every workspace of it.
    assert _uses(world, "olivia", _agent(ALPHA, "coach"))
    assert not _uses(world, "bob", _agent(ALPHA, "recruiter"))
    # Pricer is outside Acme's: naming it in Alpha's is refused, never a silent no-op.
    with use_call_context(NexusIam.context("olivia")), pytest.raises(ValueError, match="pricer"):
        world.iam.update_policy(
            ws_record.access_policy_id,
            expected_revision=1,
            document=_agents("recruiter", "scout", "pricer"),
        )
    # Olivia makes Alpha expose two of them: its owners and admins use those.
    with use_call_context(NexusIam.context("olivia")):
        world.iam.update_policy(
            ws_record.access_policy_id,
            expected_revision=1,
            document=_agents("recruiter", "scout"),
        )
    assert _uses(world, "bob", _agent(ALPHA, "recruiter"))
    assert not _uses(world, "bob", _agent(ALPHA, "coach"))
    assert not _uses(world, "bob", _agent(ALPHA, "pricer"))
    # Bob makes "Alpha minimal" under Alpha's access, and gives it to Dave.
    with use_call_context(NexusIam.context("bob")):
        minimal = world.iam.create_policy(
            "Alpha minimal", _agents("*"), scope=ALPHA, parent=ws_record.access_policy_id
        )
        world.iam.attach_policy(minimal.id, world.principal("dave"), ALPHA)
    assert _uses(world, "dave", _agent(ALPHA, "scout"))
    # Bob hides Scout from Alpha: Dave loses it at once, and so does Bob.
    with use_call_context(NexusIam.context("bob")):
        world.iam.update_policy(
            ws_record.access_policy_id, expected_revision=2, document=_agents("recruiter")
        )
    assert not _uses(world, "dave", _agent(ALPHA, "scout"))
    assert _uses(world, "dave", _agent(ALPHA, "recruiter"))
    assert not _uses(world, "bob", _agent(ALPHA, "scout"))
    # Bob no longer holds Scout: he may not show it again. Olivia may.
    with use_call_context(NexusIam.context("bob")), pytest.raises(PermissionDeniedError):
        world.iam.update_policy(
            ws_record.access_policy_id,
            expected_revision=3,
            document=_agents("recruiter", "scout"),
        )
    with use_call_context(NexusIam.context("olivia")):
        world.iam.update_policy(
            ws_record.access_policy_id,
            expected_revision=3,
            document=_agents("recruiter", "scout"),
        )
    assert _uses(world, "dave", _agent(ALPHA, "scout"))
    # A plain member holds nothing by the members group.
    await MEMBERSHIPS.grant("carol", "member", ALPHA)
    assert not _uses(world, "carol", _agent(ALPHA, "recruiter"))


@pytest.mark.asyncio
async def test_a_workspace_admin_edits_its_access_within_the_organizations(world, nexus_db):
    """The builder of "<W> access" at W reads what may be granted within its parent,
    "<O> access", which W's admins may neither read nor derive from."""
    _org, _ws, org_record, ws_record = await _acme(nexus_db)
    world.platform_admin("root")
    with use_call_context(NexusIam.context("root")):
        world.iam.update_policy(
            org_record.access_policy_id, expected_revision=1, document=_agents("a", "b")
        )
        world.iam.update_policy(
            ws_record.access_policy_id, expected_revision=1, document=_agents("a", "b")
        )
    await MEMBERSHIPS.grant("carol", "admin", ALPHA)
    with use_call_context(NexusIam.context("carol")):
        offered = world.iam.grantable(ALPHA, parent=org_record.access_policy_id)
        with pytest.raises(PermissionDeniedError):
            world.iam.grantable(ALPHA, parent=org_record.access_policy_id, derive=True)
    agents = {r for c in offered for a in c.actions if a.action == USE for r in a.resources}
    assert agents == {"${scope}/module:agent/people/a", "${scope}/module:agent/people/b"}


# -- forgotten with it ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_an_organization_with_workspaces_is_not_deleted(world, nexus_db):
    _org, _ws, org_record, ws_record = await _acme(nexus_db)
    async with nexus_db() as db:
        orgs = OrganizationService(adapter=OrganizationSecondaryAdapterPostgres(db=db))
        with pytest.raises(OrganizationHasWorkspacesError, match=r"Alpha \(alpha\)"):
            await orgs.delete_organization("acme")
        workspaces = WorkspaceService(adapter=WorkspaceSecondaryAdapterPostgres(db=db))
        assert await workspaces.delete_workspace("alpha")
        await db.commit()
        assert await SqlDefaultsStore(db).get(ALPHA) is None
    with as_service_account("api"):
        # The workspace's own went with its container; the org's access stays.
        with pytest.raises(IAMNotFoundError):
            world.iam.get_policy(ws_record.access_policy_id)
        assert world.iam.get_policy(org_record.access_policy_id)
    async with nexus_db() as db:
        orgs = OrganizationService(adapter=OrganizationSecondaryAdapterPostgres(db=db))
        assert await orgs.delete_organization("acme")
        await db.commit()
        assert await SqlDefaultsStore(db).get(org_container("acme")) is None
    with as_service_account("api"):
        with pytest.raises(IAMNotFoundError):
            world.iam.get_policy(org_record.access_policy_id)
        assert world.iam.container("nexus", "organization", "acme") is None


@pytest.mark.asyncio
async def test_the_delete_route_is_the_owners_and_refuses_while_workspaces_remain(api, team):  # noqa: F811
    async with api("admin") as http:
        assert (await http.delete("/api/organizations/org-1")).status_code == 403
    async with api("member") as http:
        assert (await http.delete("/api/organizations/org-1")).status_code == 403
    async with api("owner") as http:
        refused = await http.delete("/api/organizations/org-1")
        assert refused.status_code == 409
        assert "WS (ws-1)" in refused.json()["detail"]
        assert (await http.delete("/api/workspaces/ws-1")).status_code in (200, 204)
        assert (await http.delete("/api/organizations/org-1")).status_code == 200
        assert (await http.delete("/api/organizations/org-1")).status_code in (403, 404)
    with as_service_account("api"):
        assert team.iam.container("nexus", "organization", "org-1") is None
    # The platform admin deletes one too.
    async with api("bob") as http:
        made = await http.post("/api/organizations", json={"name": "Beta Corp", "slug": "beta"})
        assert made.status_code == 200, made.text
        beta = made.json()["id"]
    team.platform_admin("stranger")
    async with api("stranger") as http:
        assert (await http.delete(f"/api/organizations/{beta}")).status_code == 200


# -- the upgrade --------------------------------------------------------------------------


async def _check_upgrade(nexus, nexus_db) -> None:
    """A database the sets' move and the names' move made (``policy_tree_test``'s
    world), plus an organization and a workspace made after them: each organization
    keeps its "<O> access", each workspace's "<W> access" becomes its own with what
    its organization owned below it, the later ones get new ones, groups are made and
    filled, and every decision stays the same."""
    from naas_abi.apps.nexus.apps.api.app.models import OrganizationModel, WorkspaceModel

    with nexus.installed():
        subjects = previous._subjects(nexus)
        await previous._upgrade(nexus, nexus_db)
        # Made after the sets' move, before this version: no access policy of its own.
        async with nexus_db() as db:
            db.add(
                OrganizationModel(
                    id="org-late",
                    name="Late",
                    slug="late",
                    owner_id="alice",
                    created_at=NOW,
                    updated_at=NOW,
                )
            )
            await db.flush()
            db.add(
                WorkspaceModel(
                    id="ws-late",
                    name="Late W",
                    slug="late-w",
                    owner_id="alice",
                    organization_id="org-late",
                    created_at=NOW,
                    updated_at=NOW,
                )
            )
            await db.commit()
        late = workspace_container("org-late", "ws-late")
        with as_service_account("api"):
            nexus.iam.register_container("nexus", "organization", "org-late")
            nexus.iam.register_container(
                "nexus", "workspace", "ws-late", parent=org_container("org-late")
            )
        nexus.grant("bob", "admin", late)
        late_agent = _agent(late, "recruiter")
        assert not _uses(nexus, "bob", late_agent)
        before = previous._iam_decisions(nexus, subjects)
        async with nexus_db() as db:
            report = await container_defaults.migrate(db)
            records = {r.container: r for r in await SqlDefaultsStore(db).all()}
            assert await _recorded(db)
        nexus.iam.invalidate()
        after = previous._iam_decisions(nexus, subjects)
        assert {k: v for k, v in after.items() if before[k] != v} == {}
        assert not _uses(nexus, "bob", late_agent)
        assert not report.failed
        assert sorted(report.made) == sorted([org_container("org-late"), late])
        assert set(report.adopted) | set(report.made) == set(records)
        with as_service_account("engine"):
            for ws, org in previous.WORKSPACES.items():
                record = records[workspace_container(org, ws)]
                access = nexus.iam.get_policy(record.access_policy_id)
                assert access.owner_scope == record.container
                # What its organization (or the platform) owned below it is its own.
                for sub in nexus.iam.list_sub_policies(access.id):
                    assert sub.owner_scope.startswith(record.container)
                if org:
                    assert access.parent_id == records[org_container(org)].access_policy_id
                # Not attached to the admins group: that would give what the move kept.
                assert nexus.iam.list_attachments(principal_id=record.admins_group_id) == []
            # The later workspace's, made now, is attached: it allows nothing.
            made = records[late]
            assert [
                a.policy_id for a in nexus.iam.list_attachments(principal_id=made.admins_group_id)
            ] == [made.access_policy_id]
            assert (
                nexus.iam.get_policy(made.access_policy_id).parent_id
                == records[org_container("org-late")].access_policy_id
            )
            # The groups hold the role holders.
            alpha = records[workspace_container("org-1", "ws-a")]
            holders = container_defaults.role_holders(nexus.iam, alpha.container)
            assert set(nexus.iam.list_group_members(alpha.members_group_id)) == set(holders)
            assert nexus.principal("bob") in set(nexus.iam.list_group_members(made.admins_group_id))
        # Again: nothing more.
        async with nexus_db() as db:
            again = await container_defaults.migrate(db)
        assert again.made == again.adopted == []


@pytest.mark.asyncio
async def test_the_upgrade_gives_each_its_defaults_and_nobody_gains_or_loses(nexus_db):
    await _check_upgrade(previous._world(), nexus_db)


@pytest.mark.asyncio
async def test_the_upgrade_on_the_sqlite_store(nexus_db, tmp_path):
    from naas_abi_core.services.iam.adapters.secondary.IAMStoreSQLite import IAMStoreSQLite

    await _check_upgrade(previous._world(IAMStoreSQLite(str(tmp_path / "iam.sqlite"))), nexus_db)


async def _recorded(db) -> bool:
    from naas_abi.apps.nexus.apps.api.app.services.iam.container_names import recorded

    return await recorded(db, container_defaults.MIGRATION_NAME)


# -- review: failures, idempotency, races ------------------------------------------------


async def _moves_recorded(nexus_db, *names: str) -> None:
    from sqlalchemy import text

    async with nexus_db() as db:
        await db.execute(
            text(
                "CREATE TABLE IF NOT EXISTS iam_migrations (name VARCHAR(128) PRIMARY KEY, "
                "applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, report TEXT)"
            )
        )
        for name in names:
            await db.execute(
                text("INSERT INTO iam_migrations (name, report) VALUES (:n, '{}')"), {"n": name}
            )
        await db.commit()


async def _unrecorded_org(world, nexus_db, org_id: str = "acme") -> None:
    """An organization and a workspace with no record (made before this version)."""
    from naas_abi.apps.nexus.apps.api.app.models import OrganizationModel, WorkspaceModel

    async with nexus_db() as db:
        await _users(db, "olivia")
        db.add(OrganizationModel(id=org_id, name="Acme", slug=org_id, owner_id="olivia"))
        await db.flush()
        db.add(
            WorkspaceModel(
                id="alpha", name="Alpha", slug="alpha", owner_id="olivia", organization_id=org_id
            )
        )
        await db.commit()
    world.workspace(org_id, "alpha")


def _named(nexus: NexusIam, name: str) -> list:
    with as_service_account("engine"):
        return [p for p in nexus.iam._all_policies() if p.name == name]


def _groups_of(nexus: NexusIam, container: str) -> list[str]:
    with as_service_account("api"):
        return sorted(
            g.name
            for g in nexus.iam.list_groups(scope=container, limit=500).items
            if g.owner_scope == container and g.status != "deleted"
        )


@pytest.mark.asyncio
async def test_records_of_an_organization_are_forgotten_by_prefix_not_pattern(nexus_db):
    """``_`` and ``%`` in an id are characters, never wildcards."""
    from naas_abi.apps.nexus.apps.api.app.services.iam.container_defaults import DefaultsRecord

    async with nexus_db() as db:
        store = SqlDefaultsStore(db)
        for org in ("my_org", "myXorg", "my%org"):
            await store.put(DefaultsRecord(org_container(org), "p", "m", "a"))
            await store.put(DefaultsRecord(workspace_container(org, "w"), "p", "m", "a"))
        await store.delete_within(org_container("my_org"))
        left = sorted(r.container for r in await store.all())
    assert left == sorted(
        [
            org_container("myXorg"),
            workspace_container("myXorg", "w"),
            org_container("my%org"),
            workspace_container("my%org", "w"),
        ]
    )


@pytest.mark.asyncio
async def test_a_failure_part_way_leaves_nothing_and_the_next_start_makes_it_once(
    world, nexus_db, monkeypatch
):
    await _unrecorded_org(world, nexus_db)
    await _moves_recorded(nexus_db, *container_defaults.MOVES)
    calls = {"n": 0}
    real = world.iam.create_group

    def failing(name, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("the store went away")
        return real(name, **kwargs)

    monkeypatch.setattr(world.iam, "create_group", failing)
    async with nexus_db() as db:
        report = await container_defaults.migrate(db)
        assert report.failed and not await _recorded(db)
    # The organization's attempt took back its "Acme access" and its first group.
    assert _named(world, "Acme access") == []
    assert _groups_of(world, org_container("acme")) == []
    monkeypatch.setattr(world.iam, "create_group", real)
    async with nexus_db() as db:
        report = await container_defaults.migrate(db)
        assert not report.failed and await _recorded(db)
    assert len(_named(world, "Acme access")) == 1 and len(_named(world, "Alpha access")) == 1
    assert _groups_of(world, ALPHA) == ["Alpha admins", "Alpha members"]


@pytest.mark.asyncio
async def test_what_a_start_made_and_did_not_record_is_found_again(world, nexus_db):
    """A start that stopped between IAM's writes and its record: the next one finds
    the policies and groups by name and makes none twice."""
    await _unrecorded_org(world, nexus_db)
    await _moves_recorded(nexus_db, *container_defaults.MOVES)
    with as_service_account("api"):
        container_defaults.plan_and_apply(
            world.iam, {"acme": "Acme"}, {"alpha": ("acme", "Alpha")}, {}
        )
    async with nexus_db() as db:
        report = await container_defaults.migrate(db)
        records = {r.container: r for r in await SqlDefaultsStore(db).all()}
    assert not report.failed
    assert len(_named(world, "Acme access")) == 1 and len(_named(world, "Alpha access")) == 1
    assert _groups_of(world, org_container("acme")) == ["Acme admins", "Acme members"]
    assert _groups_of(world, ALPHA) == ["Alpha admins", "Alpha members"]
    assert records[ALPHA].access_policy_id == _named(world, "Alpha access")[0].id


@pytest.mark.asyncio
async def test_nothing_is_made_while_a_move_is_not_recorded(world, nexus_db, monkeypatch):
    """The sets' move makes the access policies: before it, neither the start nor a
    route makes any (it would leave the move's to no one)."""
    from naas_abi.apps.nexus.apps.api.app.services.iam import policy_tree

    await _unrecorded_org(world, nexus_db)
    await _moves_recorded(nexus_db, "policy_tree_v1")
    async with nexus_db() as db:
        report = await container_defaults.migrate(db)
        assert report.made == [] and not await _recorded(db)
    assert _named(world, "Acme access") == []
    monkeypatch.setattr(policy_tree, "_pending", True)
    async with nexus_db() as db:
        await _users(db, "bob")
        orgs = OrganizationService(adapter=OrganizationSecondaryAdapterPostgres(db=db))
        await orgs.create_organization(
            name="Later", slug="later", owner_id="bob", now=NOW, org_id="later"
        )
        assert await SqlDefaultsStore(db).get(org_container("later")) is None
    assert _named(world, "Later access") == []


@pytest.mark.asyncio
async def test_a_failed_creation_leaves_no_access_policy(world, nexus_db, monkeypatch):
    real = world.iam.create_group

    def failing(name, **kwargs):
        if name.endswith("admins"):
            raise RuntimeError("the store went away")
        return real(name, **kwargs)

    monkeypatch.setattr(world.iam, "create_group", failing)
    async with nexus_db() as db:
        await _users(db, "olivia")
        orgs = OrganizationService(adapter=OrganizationSecondaryAdapterPostgres(db=db))
        with pytest.raises(RuntimeError):
            await orgs.create_organization(
                name="Acme", slug="acme", owner_id="olivia", now=NOW, org_id="acme"
            )
    assert _named(world, "Acme access") == []
    with as_service_account("api"):
        assert world.iam.container("nexus", "organization", "acme") is None


@pytest.mark.asyncio
async def test_an_organization_holding_a_container_in_iam_is_not_deleted(world, nexus_db):
    """A workspace IAM registers in it (made meanwhile, or a module's container)
    would go with it: refused, naming it."""
    await _acme(nexus_db)
    async with nexus_db() as db:
        workspaces = WorkspaceService(adapter=WorkspaceSecondaryAdapterPostgres(db=db))
        assert await workspaces.delete_workspace("alpha")
        await db.commit()
    stray = world.workspace("acme", "stray")  # in IAM, no row
    async with nexus_db() as db:
        orgs = OrganizationService(adapter=OrganizationSecondaryAdapterPostgres(db=db))
        with pytest.raises(OrganizationHasWorkspacesError, match="stray"):
            await orgs.delete_organization("acme")
    assert stray
