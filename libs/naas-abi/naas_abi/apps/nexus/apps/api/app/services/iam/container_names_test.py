"""The move of IAM's names to container paths keeps every decision.

``tests/artifacts/names_v1`` is an IAM store the code before container paths
made (commit 713f9ef47, ``generate.py.txt``), with the decisions that code took
on it: platform, organization, org-wide, workspace and orgless roles, an org's
group, a platform policy attached org-wide, a sub-policy, a workspace policy
with a Deny, absolute patterns of every shape, a service account, invitations, a
binding, placements and a narrowed key. The test opens it with the code of
today (schema 6), rewrites its names and asks every decision again on the same
resources, named as paths.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

import pytest
from naas_abi.apps.nexus.apps.api.app import models  # noqa: F401 - the Nexus tables
from naas_abi.apps.nexus.apps.api.app.models import (
    OrganizationModel,
    UserModel,
    WorkspaceModel,
)
from naas_abi.apps.nexus.apps.api.app.services.iam import bootstrap, container_names
from naas_abi.apps.nexus.apps.api.app.services.iam.bootstrap import shared_repo_grants
from naas_abi.apps.nexus.apps.api.app.services.iam.catalog import NEXUS_CATALOG
from naas_abi.apps.nexus.apps.api.app.services.iam.container_names import (
    LegacyNames,
    derive,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.testing import LegacyNexusIam
from naas_abi_core.engine.call_context import (
    CallContext,
    Principal,
    as_service_account,
    service_account,
    use_call_context,
)
from naas_abi_core.services.iam.adapters.secondary.IAMStoreSQLite import IAMStoreSQLite
from naas_abi_core.services.iam.catalog import (
    ActionCatalog,
    ActionSpec,
    CatalogRegistry,
    ResourceType,
)
from naas_abi_core.services.iam.guard import ServiceGuard
from naas_abi_core.services.iam.IAMService import LEGACY_NEXUS_ISSUER, IAMService
from naas_abi_core.services.iam.kernel_catalogs import register_kernel_catalogs
from naas_abi_core.services.iam.names import (
    UNRESOLVED,
    container_name,
    parse_resource_name,
)
from naas_abi_core.services.triple_store.iam_catalog import (
    CATALOG as TRIPLE_STORE_CATALOG,
)
from sqlalchemy import text

ARTIFACTS = Path(__file__).parent / "tests" / "artifacts" / "names_v1"
O1, O2 = "org-aaaaaaaaaaa1", "org-bbbbbbbbbbb2"
WORKSPACES = {
    "ws-aaaaaaaaaaa1": O1,
    "ws-aaaaaaaaaaa2": O1,
    "ws-bbbbbbbbbbb3": O2,
    "ws-ccccccccccc4": None,
}
ORGS = [O1, O2]
CRM = ActionCatalog(
    service="crm",
    version=1,
    module="crm",
    resource_types=(ResourceType("deal", module_scope=True),),
    actions=(
        ActionSpec("ReadDeal", "read", ("deal",)),
        ActionSpec("CloseDeal", "write", ("deal",)),
    ),
)
# What a change of the rules makes different, on purpose (core AGENTS.md,
# "Resource names are container paths", Consequences): an attachment below an
# organization is named in it, so an admin of its own level may attach there
# (what it grants under it is still checked, "Grant only what you hold").
CHANGED = {
    (
        "oadminlevel",
        "iam:AttachPolicy",
        "abi:org-aaaaaaaaaaa1:%2A:iam:attachment/builtin.admin/usr_x",
    ),
}


def _org(org: str) -> str:
    return container_name("nexus", "organization", org)


def _workspace(workspace: str) -> str:
    org = WORKSPACES[workspace]
    return container_name("nexus", "workspace", workspace, parent=_org(org) if org else "abi:")


def new_name(action: str, old: str) -> str:
    """The name of today of a resource the old code named ``old``."""
    org, workspace, rest = old[len("abi:") :].split(":", 2)
    if rest == "nexus:organization/-":
        if action == "nexus:CreateOrganization":
            return container_name("nexus", "organization", "org-new")
        if action == "nexus:CreateWorkspace":
            return container_name("nexus", "workspace", "ws-new", parent=_org(org))
        return _org(org)
    if rest == "nexus:workspace/-":
        return _workspace(workspace)
    if (org, workspace) in (("-", "-"), ("%2A", "%2A")):
        return "abi:" + rest
    if workspace in ("-", "%2A"):
        return f"{_org(org)}/{rest}"
    return f"{_workspace(workspace)}/{rest}"


def _open(tmp_path: Path, *extra: str) -> IAMService:
    path = tmp_path / "iam.sqlite"
    connection = sqlite3.connect(path)
    connection.executescript((ARTIFACTS / "iam.sql").read_text())
    for statement in extra:
        connection.execute(statement)
    connection.commit()
    connection.close()
    iam = IAMService(IAMStoreSQLite(str(path)))
    iam.bootstrap()
    register_kernel_catalogs(iam)
    with as_service_account("engine"):
        iam.register_catalog(NEXUS_CATALOG)
        iam.register_catalog(CRM)
        iam.set_platform_grants(shared_repo_grants("abi/monorepo"))
    return iam


def _decisions(iam: IAMService, fixture: dict) -> dict[tuple[str, str, str], bool]:
    found: dict[tuple[str, str, str], bool] = {}
    for user, principal_id in fixture["users"].items():
        if user == "ci":
            ctx = CallContext(
                principal=Principal(id=principal_id, kind="service_account", name="ci/export")
            )
        else:
            ctx = CallContext(
                principal=service_account("api"),
                on_behalf_of=Principal(id=principal_id, kind="user"),
            )
        with use_call_context(ctx):
            for action, old in fixture["grid"]:
                found[(user, action, old)] = iam.authorize(action, new_name(action, old)).allowed
    return found


def _before(fixture: dict) -> dict[tuple[str, str, str], bool]:
    return {
        (user, action, old): index in set(fixture["allowed"][user])
        for user in fixture["users"]
        for index, (action, old) in enumerate(fixture["grid"])
    }


@pytest.fixture
def fixture() -> dict:
    return json.loads((ARTIFACTS / "decisions.json").read_text())


def test_nobody_gains_or_loses_access(tmp_path, fixture):
    iam = _open(tmp_path)
    before = _before(fixture)
    # Until the move, the old names decide nothing more than before.
    waiting = _decisions(iam, fixture)
    assert not [k for k, v in waiting.items() if v and not before[k]]
    report = container_names.rewrite(iam, ORGS, WORKSPACES)
    assert report.counts["containers"] == 6
    after = _decisions(iam, fixture)
    changed = {k for k in before if before[k] != after[k]}
    assert changed == CHANGED, sorted(changed - CHANGED)
    assert sum(before.values()) > 300


def test_once_and_again_changes_nothing(tmp_path, fixture):
    iam = _open(tmp_path)
    container_names.rewrite(iam, ORGS, WORKSPACES)
    first = _decisions(iam, fixture)
    again = container_names.rewrite(iam, ORGS, WORKSPACES)
    assert set(again.counts.values()) == {0}
    assert _decisions(iam, fixture) == first


def test_every_stored_name_is_a_path(tmp_path):
    iam = _open(tmp_path)
    container_names.rewrite(iam, ORGS, WORKSPACES)
    rewriter = LegacyNames(ORGS, WORKSPACES, iam.catalogs)
    store = iam.store
    for attachment in store.list_attachments():
        assert attachment.scope is None or not attachment.scope.startswith(
            ("abi:-", "abi:org-", "abi:_none")
        ), attachment
    for grant in store.list_pending_grants():
        assert grant.scope == _workspace("ws-aaaaaaaaaaa1")
    for placement in store.list_placements():
        assert placement.container != UNRESOLVED, placement
    for policy in store.list_policies(limit=500).items:
        assert not policy.owner_scope.startswith("abi:org-")
        for statement in policy.document.statements:
            for pattern in statement.resources:
                assert not rewriter.is_old_pattern(pattern), (policy.id, pattern)
    for key in store.list_keys():
        for statement in key.scope or ():
            for pattern in statement["resources"]:
                parse_resource_name(pattern.replace("*", "x"))


def test_an_old_scope_nexus_does_not_know_is_left_deciding_nothing():
    rewriter = LegacyNames(ORGS, WORKSPACES, _catalogs())
    assert rewriter.scope("abi:org-gone:ws-gone") == "abi:org-gone:ws-gone"
    assert rewriter.notes
    assert rewriter.scope("abi:-:-") == "abi:"
    assert rewriter.scope(f"abi:{O1}:*") == _org(O1) + "/*"
    assert rewriter.owner(f"abi:{O1}:-") == _org(O1)
    # The "org" of the workspaces in none owned what the moves made for them.
    assert rewriter.owner("abi:_none:-") == "abi:"
    assert rewriter.scope("abi:_none:-") == "abi:_none:-"
    assert rewriter.scope(_org(O1)) == _org(O1)


def _catalogs() -> CatalogRegistry:
    registry = CatalogRegistry()
    registry.register(NEXUS_CATALOG)
    return registry


def test_patterns_of_every_shape():
    rewriter = LegacyNames(ORGS, WORKSPACES, _catalogs())
    w1 = _workspace("ws-aaaaaaaaaaa1")

    def plain(pattern):
        return sorted(p for k, p in rewriter.pattern(pattern) if k is None)

    assert plain(f"abi:{O1}:ws-aaaaaaaaaaa1:triple_store:graph/*") == [f"{w1}/triple_store:graph/*"]
    assert plain("abi:*:*:triple_store:graph/x") == [
        "abi:*/triple_store:graph/x",
        "abi:triple_store:graph/x",
    ]
    assert plain("abi:-:-:model_registry:model/*") == ["abi:model_registry:model/*"]
    assert plain("abi:%2A:%2A:iam:policy/*") == ["abi:iam:policy/*"]
    assert plain("${scope}:triple_store:graph/*") == ["${scope}/triple_store:graph/*"]
    # The workspace itself, for the actions on workspaces only.
    assert (
        "workspace",
        "${scope}",
    ) in rewriter.pattern("${scope}:nexus:workspace/-")
    # CreateWorkspace was decided on the organization.
    assert ("nexus:CreateWorkspace", "${scope}/nexus:workspace/*") in rewriter.pattern(
        "${scope}:nexus:organization/-"
    )
    # An org's own level stays at its level: no workspace content.
    org_level = plain(f"abi:{O1}:-:nexus:*")
    assert org_level and not any("nexus:workspace" in p for p in org_level)
    # Already a path: kept.
    assert rewriter.pattern(f"{w1}/triple_store:graph/*") == [(None, f"{w1}/triple_store:graph/*")]


def test_a_glob_derivative():
    assert {"x", "*:-:x"} <= derive("abi:*:-:x", "abi:o:-:")
    assert derive("abi:o:w:*", "abi:o:w:") == {"*"}
    assert derive("abi:o:w:x", "abi:p:w:") == set()


def test_a_placement_of_a_workspace_gone_names_nothing_and_never_fails(tmp_path):
    """A placement of a workspace Nexus no longer knows has no container: it is
    kept as it was and reads as UNRESOLVED, so a create there is not found
    rather than a name that cannot be built."""
    iam = _open(
        tmp_path,
        "INSERT INTO iam_placements (service, id_key, org, workspace) "
        f"VALUES ('triple_store', 'gone', '{O1}', 'ws-gone9999999')",
    )
    report = container_names.rewrite(iam, ORGS, WORKSPACES)
    assert any("ws-gone9999999" in note for note in report.notes)
    assert iam.resolve_placement("triple_store", "gone") == UNRESOLVED
    guard = ServiceGuard(TRIPLE_STORE_CATALOG, lambda: iam)
    assert guard.name("graph", "gone") == f"{UNRESOLVED}/triple_store:graph/gone"
    container_names.rewrite(iam, ORGS, WORKSPACES)  # again: still kept, still read
    assert iam.resolve_placement("triple_store", "gone") == UNRESOLVED


async def _iam_migrations(db) -> None:
    # The table Nexus's SQL migrations make (``0059_iam_role_data.sql``).
    await db.execute(
        text(
            "CREATE TABLE IF NOT EXISTS iam_migrations (name VARCHAR(128) PRIMARY KEY, "
            "applied_at TIMESTAMP NOT NULL, report TEXT)"
        )
    )


async def _before_iam_install(db) -> None:
    """An install from before IAM held any role: Nexus's rows are the only record.
    org-1's owner (``owner_id``) and admin, ws-1's owner (``owner_id``), member and
    viewer, a workspace in no organization, and a superadmin."""
    await _iam_migrations(db)
    now = datetime(2026, 1, 1)
    db.add(
        OrganizationModel(
            id="org-1", name="Org", slug="org-1", owner_id="u-owner", created_at=now, updated_at=now
        )
    )
    for ws, org in (("ws-1", "org-1"), ("ws-2", None)):
        db.add(
            WorkspaceModel(
                id=ws,
                name=ws,
                slug=ws,
                owner_id="u-owner",
                organization_id=org,
                created_at=now,
                updated_at=now,
            )
        )
    db.add(
        UserModel(
            id="u-root",
            email="root@example.com",
            name="Root",
            is_superadmin=True,
            created_at=now,
            updated_at=now,
        )
    )
    await db.flush()
    for table, place, user, role in (
        ("organization_members", "organization_id", "u-admin", "admin"),
        ("workspace_members", "workspace_id", "u-member", "member"),
        ("workspace_members", "workspace_id", "u-viewer", "viewer"),
    ):
        target = "org-1" if table == "organization_members" else "ws-1"
        await db.execute(
            text(
                f"INSERT INTO {table} (id, {place}, user_id, role, created_at) "
                "VALUES (:id, :place, :user, :role, CURRENT_TIMESTAMP)"
            ),
            {"id": f"m-{user}", "place": target, "user": user, "role": role},
        )
    await db.commit()


def _held(world: LegacyNexusIam) -> set[tuple[str, str, str | None]]:
    """``(Nexus user, policy, scope)`` of every built-in role a user holds."""
    with as_service_account("api"):
        found = set()
        for attachment in world.iam.list_attachments():
            if not attachment.policy_id.startswith("builtin."):
                continue
            principal = world.iam.get_principal(attachment.principal_id)
            if principal.kind != "user":
                continue
            found.add((str(principal.subject), attachment.policy_id, attachment.scope))
        return found


@pytest.mark.asyncio
async def test_an_install_from_before_iam_moves_its_role_data_first(nexus_db):
    """Nexus kept every membership itself: before the moves, which read the roles
    IAM holds, the role data moves into IAM in their grammar, recorded as coming
    from before IAM; then the moves run."""
    ran: list[str] = []

    async def moves() -> None:
        ran.append("moves")

    world = LegacyNexusIam()
    async with nexus_db() as db:
        await _before_iam_install(db)
        assert await container_names.role_data_pending(db)
        with world.installed():
            assert await container_names.before_names(db, moves) is True
        assert ran == ["moves"]
        assert not await container_names.role_data_pending(db)
        assert await bootstrap.moved_from_before_iam(db)
        report = json.loads(
            (
                await db.execute(
                    text("SELECT report FROM iam_migrations WHERE name = :n"),
                    {"n": bootstrap.MIGRATION_NAME},
                )
            ).scalar()
        )
        assert (report["orgs"], report["workspaces"], report["platform_admins"]) == (1, 2, 1)
        # Recorded: the move of today finds it done and adds nothing.
        assert (await bootstrap.migrate_role_data(db)).applied is False
    assert _held(world) == {
        # An organization's owner and admin are held below it too, as Nexus mirrored them.
        ("u-owner", "builtin.owner", "abi:org-1:-"),
        ("u-owner", "builtin.owner", "abi:org-1:*"),
        ("u-admin", "builtin.admin", "abi:org-1:-"),
        ("u-admin", "builtin.admin", "abi:org-1:*"),
        ("u-owner", "builtin.owner", "abi:org-1:ws-1"),
        ("u-owner", "builtin.owner", "abi:_none:ws-2"),
        ("u-member", "builtin.member", "abi:org-1:ws-1"),
        ("u-viewer", "builtin.viewer", "abi:org-1:ws-1"),
        ("u-root", "builtin.platform_admin", None),
    }


@pytest.mark.asyncio
async def test_without_the_role_data_moved_the_moves_wait(nexus_db):
    """The role data could not be moved (no IAM to move it into): nothing runs and
    nothing is recorded; once it is in IAM, the moves run."""
    ran: list[str] = []

    async def moves() -> None:
        ran.append("moves")

    async with nexus_db() as db:
        await _iam_migrations(db)
        await db.execute(
            text(
                "INSERT INTO workspace_members (id, workspace_id, user_id, role, created_at) "
                "VALUES ('m-1', 'ws-1', 'u-1', 'admin', CURRENT_TIMESTAMP)"
            )
        )
        await db.commit()
        assert await container_names.role_data_pending(db)
        assert await container_names.before_names(db, moves) is False
        assert ran == []
        assert not await container_names.recorded(db, container_names.MIGRATION_NAME)
        assert not await container_names.recorded(db, bootstrap.MIGRATION_NAME)
        # Once the role data is in IAM, the moves run.
        await db.execute(
            text(
                "INSERT INTO iam_migrations (name, applied_at, report) "
                "VALUES ('iam_roles_v1', CURRENT_TIMESTAMP, '{}')"
            )
        )
        await db.commit()
        assert not await container_names.role_data_pending(db)
        assert not await bootstrap.moved_from_before_iam(db)
        world = LegacyNexusIam()
        with world.installed():
            assert await container_names.before_names(db, moves) is True
        assert ran == ["moves"]


async def _moves_stopped(db, world: LegacyNexusIam) -> None:
    """The start of zen's upgrade: the role data moves in the old grammar, then
    the move of the sets stops (``policy_tree_v1`` not recorded), so the move of
    the names waits."""

    async def moves() -> None:
        return None

    await _before_iam_install(db)
    with world.installed():
        assert await container_names.before_names(db, moves) is True
        assert await container_names.migrate_names(db) is None
    assert container_names.pending()


async def _sets_moved(db) -> None:
    await db.execute(
        text(
            "INSERT INTO iam_migrations (name, applied_at, report) "
            "VALUES ('policy_tree_v1', CURRENT_TIMESTAMP, '{}')"
        )
    )
    await db.commit()


# The roles of org-1's owner on org-1 and ws-1, in each grammar.
_OWNER_OLD = {
    ("u-owner", "builtin.owner", "abi:org-1:-"),
    ("u-owner", "builtin.owner", "abi:org-1:*"),
    ("u-owner", "builtin.owner", "abi:org-1:ws-1"),
}
_ORG_1 = container_name("nexus", "organization", "org-1")
_OWNER_NEW = {
    ("u-owner", "builtin.owner", _ORG_1),
    ("u-owner", "builtin.owner", _ORG_1 + "/*"),
    (
        "u-owner",
        "builtin.owner",
        container_name("nexus", "workspace", "ws-1", parent=_ORG_1),
    ),
}


@pytest.mark.asyncio
async def test_a_role_held_in_both_grammars_does_not_stop_the_move(nexus_db, tmp_path):
    """An upgrade whose moves stopped once: while the move of the names waited,
    the owner's roles were attached again in the grammar of today (by the
    configuration's seeds of then). The move merges each old one into its twin
    instead of failing on the store's unique attachment, which rolled it back at
    every start."""
    from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import MEMBERSHIPS

    world = LegacyNexusIam(store=IAMStoreSQLite(str(tmp_path / "iam.sqlite")))
    async with nexus_db() as db:
        await _moves_stopped(db, world)
        assert _OWNER_OLD <= _held(world)
        with world.installed():
            await MEMBERSHIPS.register_workspace("org-1", "ws-1")
            entries = [("u-owner", "owner", scope) for _u, _p, scope in sorted(_OWNER_NEW)]
            await MEMBERSHIPS.seed([e for e in entries if not e[2].endswith("/*")], replace=True)
        assert _OWNER_OLD | _OWNER_NEW <= _held(world)

        await _sets_moved(db)
        with world.installed():
            report = await container_names.migrate_names(db)
        assert report is not None
        assert report.counts["attachments_merged"] == 3
        assert await container_names.recorded(db, container_names.MIGRATION_NAME)
        assert not container_names.pending()
    held = _held(world)
    assert _OWNER_NEW <= held
    assert not {scope for _u, _p, scope in held if scope and scope.startswith("abi:org-1:")}


@pytest.mark.asyncio
async def test_twin_invitations_keep_their_grant_after_the_move(nexus_db, tmp_path):
    """Two pending invitations of one person to org-1's admin role: one made
    before the upgrade (its grant in the old grammar), one while the move of the
    names waited (its twin in the new). The move merges the twins into the grant
    made first and lists it on both invitations: revoking one keeps the other's."""
    from naas_abi.apps.nexus.apps.api.app.models import InvitationModel
    from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import MEMBERSHIPS
    from naas_abi.apps.nexus.apps.api.app.services.invites.runtime import InvitationRuntime

    world = LegacyNexusIam(store=IAMStoreSQLite(str(tmp_path / "iam.sqlite")))
    email, provider = "ann@example.com", "builtin"

    def pending_grant(scope: str) -> str:
        with as_service_account("api"):
            return str(world.iam.create_pending_grant(provider, email, "builtin.admin", scope).id)

    def pending() -> set[str]:
        with as_service_account("api"):
            return {str(g.id) for g in world.iam.list_pending_grants(email=email)}

    async with nexus_db() as db:
        await _moves_stopped(db, world)
        old = pending_grant("abi:org-1:-")
        with world.installed():
            await MEMBERSHIPS.register_org("org-1")
        new = pending_grant(_ORG_1)
        for invitation_id, grant in (("inv-before", old), ("inv-during", new)):
            db.add(
                InvitationModel(
                    id=invitation_id,
                    email=email,
                    provider=provider,
                    organization_id="org-1",
                    org_role="admin",
                    grant_ids=json.dumps([grant]),
                )
            )
        await db.commit()

        await _sets_moved(db)
        with world.installed():
            report = await container_names.migrate_names(db)
        assert report is not None
        assert report.grants_merged == {new: old}
        assert report.counts["invitations_remapped"] == 1
        assert pending() == {old}
        rows = (await db.execute(text("SELECT id, grant_ids FROM invitations ORDER BY id"))).all()
        assert [(i, json.loads(g)) for i, g in rows] == [
            ("inv-before", [old]),
            ("inv-during", [old]),
        ]

        with world.installed():
            service = InvitationRuntime(identity=lambda: None, iam=lambda: world.iam).service(db)
            await service.revoke("inv-before")
        # The invitation made during the wait still gives the admin role at org-1:
        # it lists the grant its twin was merged into.
        assert pending() == {old}
        with world.installed():
            await service.revoke("inv-during")
        assert pending() == set()


@pytest.mark.asyncio
async def test_the_configured_roles_wait_in_the_old_grammar(nexus_db, monkeypatch):
    """The configuration's seeds run after the moves, stopped or not: while the
    names wait, the roles they declare are attached in the old grammar (an owner
    org-wide too), which the move rewrites; once it is recorded, in the grammar of
    today, where they are held already."""
    from naas_abi.apps.nexus.apps.api.app.core import org_seed

    world = LegacyNexusIam()
    declared_scopes = [("org-1", None), ("org-1", "ws-1")]
    declared = [("u-root", "owner", "org-1", None), ("u-root", "owner", "org-1", "ws-1")]
    root_old = {
        ("u-root", "builtin.owner", "abi:org-1:-"),
        ("u-root", "builtin.owner", "abi:org-1:*"),
        ("u-root", "builtin.owner", "abi:org-1:ws-1"),
    }
    async with nexus_db() as db:
        monkeypatch.setattr(org_seed, "async_engine", db.bind)
        await _moves_stopped(db, world)
        with world.installed():
            await org_seed._apply_declared_roles(declared_scopes, declared)
        assert {h for h in _held(world) if h[0] == "u-root" and h[2]} == root_old

        await _sets_moved(db)
        with world.installed():
            report = await container_names.migrate_names(db)
            assert report is not None
            assert report.counts["attachments_merged"] == 0
            # A start after the move: the same declarations, held already.
            await org_seed._apply_declared_roles(declared_scopes, declared)
    root_new = {("u-root", policy, scope) for _u, policy, scope in _OWNER_NEW}
    assert {h for h in _held(world) if h[0] == "u-root" and h[2]} == root_new


def test_an_org_wide_mirror_missing_is_made_before_the_moves():
    """An organization's admin held only at its own level (no ``abi:O:*``): the
    old grammar's mirror is made, so the moves see the workspaces it reaches."""
    world = LegacyNexusIam()
    org_scope = world.org("org-1")
    world.workspace("org-1", "ws-1")
    with as_service_account("api"):
        admin = world.iam.ensure_user(LEGACY_NEXUS_ISSUER, "ann", provider="nexus")
        world.iam.attach_policy("builtin.admin", admin.id, org_scope)
        member = world.iam.ensure_user(LEGACY_NEXUS_ISSUER, "max", provider="nexus")
        world.iam.attach_policy("builtin.member", member.id, org_scope)
    assert container_names.mirror_old_org_wide(world.iam) == 1
    with as_service_account("api"):
        scopes = {(a.policy_id, a.scope) for a in world.iam.list_attachments(principal_id=admin.id)}
        assert ("builtin.admin", "abi:org-1:*") in scopes
        assert {a.scope for a in world.iam.list_attachments(principal_id=member.id)} == {org_scope}
    assert container_names.mirror_old_org_wide(world.iam) == 0


@pytest.mark.asyncio
async def test_a_process_stops_waiting_once_another_has_recorded_the_moves(nexus_db):
    """A replica whose start did not make the moves refuses module scopes and
    features until it re-reads that another one recorded them."""
    from naas_abi.apps.nexus.apps.api.app.services.iam import authz, policy_tree

    async with nexus_db() as db:
        await db.execute(
            text(
                "CREATE TABLE IF NOT EXISTS iam_migrations (name VARCHAR(128) PRIMARY KEY, "
                "applied_at TIMESTAMP NOT NULL, report TEXT)"
            )
        )
        await db.commit()
        policy_tree.set_pending(True)
        container_names.set_pending(True)
        try:
            assert await container_names.refresh_pending(db) is True
            assert authz.upgrading()
            # Another process records the sets' move: the names still wait.
            await db.execute(
                text(
                    "INSERT INTO iam_migrations (name, applied_at, report) "
                    f"VALUES ('{policy_tree.MIGRATION_NAME}', CURRENT_TIMESTAMP, '{{}}')"
                )
            )
            await db.commit()
            assert await container_names.refresh_pending(db) is True
            assert not policy_tree.pending() and container_names.pending()
            await db.execute(
                text(
                    "INSERT INTO iam_migrations (name, applied_at, report) "
                    f"VALUES ('{container_names.MIGRATION_NAME}', CURRENT_TIMESTAMP, '{{}}')"
                )
            )
            await db.commit()
            assert await container_names.refresh_pending(db) is False
            assert not authz.upgrading()
        finally:
            policy_tree.set_pending(False)
            container_names.set_pending(False)


@pytest.mark.asyncio
async def test_the_moves_lock_holds_nothing_on_sqlite():
    """SQLite has no lock between processes: one API process starts the upgrade
    (the lock is PostgreSQL's advisory lock)."""
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine("sqlite+aiosqlite://")
    try:
        async with container_names.moves_lock(engine):
            async with container_names.moves_lock(engine):
                pass
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_the_moves_lock_holds_one_process_at_a_time_on_postgresql():
    """Two API processes starting at once: the second moves only once the first
    is done, and then finds the moves recorded."""
    import asyncio
    import os

    from sqlalchemy.ext.asyncio import create_async_engine

    dsn = os.environ.get("IAM_TEST_POSTGRES_DSN") or os.environ.get("DOCUMENT_TEST_POSTGRES_DSN")
    if not dsn:
        pytest.skip("Set IAM_TEST_POSTGRES_DSN to run on PostgreSQL")
    url = dsn.replace("postgresql://", "postgresql+asyncpg://", 1)
    first, second = create_async_engine(url), create_async_engine(url)
    order: list[str] = []
    held = asyncio.Event()

    async def start(engine, name: str, signal: asyncio.Event | None) -> None:
        async with container_names.moves_lock(engine):
            order.append(f"{name} in")
            if signal is not None:
                signal.set()
                await asyncio.sleep(0.3)
            order.append(f"{name} out")

    try:
        one = asyncio.create_task(start(first, "one", held))
        await held.wait()
        await asyncio.gather(start(second, "two", None), one)
        assert order == ["one in", "one out", "two in", "two out"]
    finally:
        await first.dispose()
        await second.dispose()
