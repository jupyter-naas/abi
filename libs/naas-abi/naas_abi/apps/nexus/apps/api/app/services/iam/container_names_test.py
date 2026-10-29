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
from pathlib import Path

import pytest
from naas_abi.apps.nexus.apps.api.app import models  # noqa: F401 - the Nexus tables
from naas_abi.apps.nexus.apps.api.app.services.iam import container_names
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


@pytest.mark.asyncio
async def test_the_moves_wait_while_nexus_keeps_memberships_iam_does_not(nexus_db):
    """The moves before container paths read the roles IAM holds: with role data
    not moved yet, nothing runs and nothing is recorded (and it is said)."""
    ran: list[str] = []

    async def moves() -> None:
        ran.append("moves")

    async with nexus_db() as db:
        # The table Nexus's SQL migrations make (``0059_iam_role_data.sql``).
        await db.execute(
            text(
                "CREATE TABLE IF NOT EXISTS iam_migrations (name VARCHAR(128) PRIMARY KEY, "
                "applied_at TIMESTAMP NOT NULL, report TEXT)"
            )
        )
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
        # Once the role data is in IAM, the moves run.
        await db.execute(
            text(
                "INSERT INTO iam_migrations (name, applied_at, report) "
                "VALUES ('iam_roles_v1', CURRENT_TIMESTAMP, '{}')"
            )
        )
        await db.commit()
        assert not await container_names.role_data_pending(db)
        world = LegacyNexusIam()
        with world.installed():
            assert await container_names.before_names(db, moves) is True
        assert ran == ["moves"]


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
