"""Policies and groups owned by a container, in process: the shared
scenario (``tests/owned_scope_contract.py``) and what only the service shows."""

from __future__ import annotations

import re
from collections.abc import Iterator
from contextlib import contextmanager

import pytest

from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.services.iam import roles
from naas_abi_core.services.iam.catalog import ActionCatalog, ActionSpec, ResourceType
from naas_abi_core.services.iam.IAMPorts import (
    IAMNotFoundError,
    IAMStore,
    IIAMService,
    PermissionDeniedError,
)
from naas_abi_core.services.iam.IAMService import (
    IAMService,
    attachment_resource,
    group_resource,
    policy_resource,
)
from naas_abi_core.services.iam.names import UNRESOLVED, anywhere
from naas_abi_core.services.iam.policy import PolicyValidationError
from naas_abi_core.services.iam.tests import owned_scope_contract as contract
from naas_abi_core.services.iam.tests.iam_harness import (
    ACTIVITY_LOG,
    NEXUS,
    TRIPLE_STORE,
    IAMHarness,
    graph,
    name_in,
    org,
    workspace,
)

WS1, WS2, ORG_SCOPE = contract.WS1, contract.WS2, contract.ORG_SCOPE


def _as_user(h: IAMHarness):
    @contextmanager
    def as_user(record) -> Iterator[IIAMService]:
        with h.as_(record):
            yield h.iam

    return as_user


@pytest.mark.parametrize("scenario", contract.SCENARIOS, ids=lambda s: s.__name__)
def test_owned_scenarios_in_process(h, scenario):
    scenario(h.iam, _as_user(h))


@pytest.fixture(
    params=["sqlite", pytest.param("postgresql", marks=pytest.mark.integration)]
)
def stored(request, tmp_path) -> Iterator[IAMHarness]:
    """A bootstrapped service on SQLite, and on PostgreSQL in a fresh schema
    (``conftest.schema``: skipped without a database)."""
    if request.param == "sqlite":
        from naas_abi_core.services.iam.adapters.secondary.IAMStoreSQLite import (
            IAMStoreSQLite,
        )

        store: IAMStore = IAMStoreSQLite(str(tmp_path / "iam.sqlite"))
    else:
        from naas_abi_core.services.iam.adapters.secondary.IAMStorePostgreSQL import (
            IAMStorePostgreSQL,
        )

        store = IAMStorePostgreSQL(*request.getfixturevalue("schema"))
    iam = IAMService(store)
    try:
        iam.bootstrap()
        for catalog in (TRIPLE_STORE, ACTIVITY_LOG, NEXUS):
            iam._register_catalog(catalog)
        yield IAMHarness(iam)
    finally:
        iam.close()


@pytest.mark.parametrize(
    "scenario",
    [
        contract.run_another_containers_policies_are_not_listed,
        contract.run_the_attach_list_follows_the_right_to_attach,
    ],
    ids=lambda s: s.__name__,
)
def test_what_a_container_lists_on_each_store(stored, scenario):
    scenario(stored.iam, _as_user(stored))


def test_whether_a_policy_is_known_is_one_read_whatever_the_organisations(h):
    """Every organisation's admin may attach every "<O> access" (a platform
    policy confined to a scope): which are attached at their organisation is
    read once per list, not once per organisation."""
    contract.register_containers(h.iam)
    others = [f"org-x{i}" for i in range(20)]
    with as_service_account("api"):
        for org_id in others:
            h.iam.register_container("nexus", "organization", org_id)
    with as_service_account("engine"):
        admins = {}
        for org_id in [contract.ORG, *others]:
            admin = h.iam.ensure_user("https://idp.example", f"admin-{org_id}")
            h.iam.attach_policy(roles.ADMIN, admin.id, org(org_id))
            access = h.iam.create_policy(f"{org_id} access", contract.reader())
            h.iam.attach_policy(access.id, admin.id, org(org_id))
            admins[org_id] = (admin, access.id)
    admin, own = admins[contract.ORG]
    reads: list[str] = []
    for name in ("attachments_of", "list_attachments"):
        method = getattr(h.iam.store, name)

        def counted(*args, _method=method, _name=name, **kwargs):
            if _name == "attachments_of" or kwargs.get("policy_id"):
                reads.append(_name)
            return _method(*args, **kwargs)

        setattr(h.iam.store, name, counted)
    with h.as_(admin):
        listed = {p.id for p in h.iam.list_policies(scope=ORG_SCOPE).items}
        assert reads == ["attachments_of"]
        offered = {p.id for p in h.iam.attachable_policies(ORG_SCOPE).items}
        assert reads == ["attachments_of", "attachments_of"]
    for found in (listed, offered):
        assert own in found
        assert not {access for _admin, access in admins.values()} - {own} & found


def test_names_carry_the_owner():
    assert policy_resource("pol_x", WS1) == WS1 + "/iam:policy/pol_x"
    assert group_resource("grp_x", ORG_SCOPE) == ORG_SCOPE + "/iam:group/grp_x"
    # The platform's are named at the platform, which no ${scope} reaches.
    assert policy_resource("pol_x") == "abi:iam:policy/pol_x"
    assert group_resource("grp_x") == "abi:iam:group/grp_x"


def test_members_and_viewers_hold_nothing_of_iam():
    from naas_abi_core.services.iam.catalog import CatalogRegistry
    from naas_abi_core.services.iam.iam_catalog import CATALOG

    registry = CatalogRegistry()
    registry.register(CATALOG)
    for role in (roles.VIEWER, roles.MEMBER):
        statements = roles.role_policy(role, registry).document.statements
        assert not any(a.startswith("iam:") for s in statements for a in s.actions)
    for role in (roles.ADMIN, roles.OWNER):
        actions = {
            a
            for s in roles.role_policy(role, registry).document.statements
            for a in s.actions
        }
        assert {"iam:CreatePolicy", "iam:AddGroupMember", "iam:ListGroups"} <= actions
        assert not actions & {"iam:MapIdpGroup", "iam:UnmapIdpGroup"}


def test_an_owner_scope_must_be_registered(h):
    root = h.user("root")
    h.attach(roles.PLATFORM_ADMIN, root.id)
    with h.as_(root):
        with pytest.raises(ValueError):
            h.iam.create_policy(
                "x", contract.reader(), scope=workspace("ws-x", "org-x")
            )
        with pytest.raises(ValueError):
            h.iam.create_group("x", scope=org("org-x"))
        # A registered container named under another path is not it.
        with pytest.raises(ValueError):
            h.iam.create_group("x", scope=workspace("ws-1", "org-2"))
        # Owned by a container, never below one.
        with pytest.raises(ValueError):
            h.iam.create_group("x", scope=contract.ORG_WIDE)


def test_an_owned_policy_refuses_what_reaches_beyond_its_scope(h):
    t = contract.team(h.iam)
    with h.as_(t.ws_admin), pytest.raises(PolicyValidationError) as refused:
        h.iam.create_policy(
            "wide",
            contract.document(contract.statement("Deny", ["*"], ["*"])),
            scope=WS1,
        )
    assert "'*'" in str(refused.value)


def test_a_workspace_admin_sees_what_it_may_attach_from_above(h):
    t = contract.team(h.iam)
    with as_service_account("engine"):
        org_policy = h.iam.create_policy(
            "org readers", contract.reader(), scope=ORG_SCOPE
        )
        platform_policy = h.iam.create_policy("platform readers", contract.reader())
        org_group = h.iam.create_group("org analysts", scope=ORG_SCOPE)
        platform_group = h.iam.create_group("platform analysts")
    with h.as_(t.ws_admin):
        listed = {p.id for p in h.iam.list_policies(scope=WS1).items}
        # Attached nowhere: named only to whoever may list them at their owner.
        assert {roles.ADMIN, roles.VIEWER} <= listed
        assert not {org_policy.id, platform_policy.id} & listed
    with as_service_account("engine"):
        h.iam.attach_policy(org_policy.id, t.org_admin.id, contract.ORG_WIDE)
        h.iam.attach_policy(platform_policy.id, t.org_admin.id, ORG_SCOPE)
    with h.as_(t.ws_admin):
        listed = {p.id for p in h.iam.list_policies(scope=WS1).items}
        assert {org_policy.id, platform_policy.id, roles.ADMIN, roles.VIEWER} <= listed
        assert roles.OWNER not in listed  # an admin never attaches owner
        assert t.ws2_policy not in listed
        # Attached from above at ws-1, to a group of the org.
        h.iam.attach_policy(org_policy.id, org_group.id, WS1)
        groups = {g.id for g in h.iam.list_groups(scope=WS1).items}
        assert org_group.id in groups and platform_group.id not in groups
        # Not read one by one: only listed where they may be attached.
        with pytest.raises(IAMNotFoundError):
            h.iam.get_policy(org_policy.id)


def test_a_user_who_leaves_the_org_leaves_its_groups(h):
    t = contract.team(h.iam)
    with h.as_(t.ws_admin):
        group = h.iam.create_group("analysts", scope=WS1)
        h.iam.add_group_member(group.id, t.member.id)
        h.iam.detach_policy(roles.MEMBER, t.member.id, WS1)
    with as_service_account("engine"):
        assert h.iam.list_group_members(group.id) == []


def test_deleting_a_workspace_deletes_what_it_owns(h):
    t = contract.team(h.iam)
    with h.as_(t.ws_admin):
        policy = h.iam.create_policy("readers", contract.reader(), scope=WS1)
        group = h.iam.create_group("analysts", scope=WS1)
        h.iam.attach_policy(policy.id, group.id, WS1)
        h.iam.attach_policy(policy.id, t.member.id, WS1)
        h.iam.create_pending_grant("builtin", "eve@example.com", policy.id, WS1)
    with as_service_account("engine"):
        org_policy = h.iam.create_policy("org", contract.reader(), scope=ORG_SCOPE)
    with as_service_account("api"):
        h.iam.delete_container("nexus", "workspace", "ws-1")
    with as_service_account("engine"):
        with pytest.raises(IAMNotFoundError):
            h.iam.get_policy(policy.id)
        assert h.iam.get_group(group.id).status == "deleted"
        assert h.iam.list_attachments(policy_id=policy.id) == []
        assert h.iam.list_pending_grants(policy_id=policy.id) == []
        # What ws-2 and the org own stays, until the org goes.
        assert h.iam.get_policy(t.ws2_policy).owner_scope == WS2
        assert h.iam.get_policy(org_policy.id).owner_scope == ORG_SCOPE
    with as_service_account("api"):
        h.iam.delete_container("nexus", "organization", "org-1")
    with as_service_account("engine"):
        for policy_id in (t.ws2_policy, org_policy.id):
            with pytest.raises(IAMNotFoundError):
                h.iam.get_policy(policy_id)
        assert h.iam.get_group(t.ws2_group).status == "deleted"


def test_deleting_a_workspace_takes_its_members_out_of_the_orgs_groups(h):
    """Bob is in the org through ws-1 only: when ws-1 goes, he leaves the
    org's groups and what they grant at ws-2, though a policy of the org was
    still attached to him at ws-1 (nothing but IAM detaches that)."""
    t = contract.team(h.iam)
    ws2_graph = name_in(WS2, "triple_store:graph/g")
    with h.as_(t.org_admin):
        readers = h.iam.create_policy("readers", contract.reader(), scope=ORG_SCOPE)
        group = h.iam.create_group("analysts", scope=ORG_SCOPE)
        h.iam.attach_policy(readers.id, group.id, WS2)
        h.iam.add_group_member(group.id, t.member.id)
        h.iam.add_group_member(group.id, t.colleague.id)
        h.iam.attach_policy(readers.id, t.member.id, WS1)
    with h.as_(t.member):
        assert h.iam.authorize("triple_store:Query", ws2_graph).allowed
    with as_service_account("api"):
        h.iam.delete_container("nexus", "workspace", "ws-1")
    with as_service_account("engine"):
        assert h.iam.list_group_members(group.id) == [t.colleague.id]
        assert not any(
            a.scope == WS1 for a in h.iam.list_attachments(principal_id=t.member.id)
        )
    with h.as_(t.member):
        assert not h.iam.authorize("triple_store:Query", ws2_graph).allowed


def test_a_binding_group_belongs_to_the_org_of_its_scope(h):
    contract.team(h.iam)
    with as_service_account("engine"):
        first = h.iam.bind_idp_group("acme", "Sales", roles.VIEWER, WS1)
        again = h.iam.bind_idp_group("acme", "Sales", roles.VIEWER, WS2)
        other = h.iam.bind_idp_group("acme", "Sales", roles.VIEWER, contract.OTHER_ORG)
        assert first.group_id == again.group_id != other.group_id
        assert h.iam.get_group(first.group_id).owner_scope == ORG_SCOPE
        assert h.iam.get_group(other.group_id).owner_scope == org("org-2")


def test_platform_groups_keep_their_rules(h):
    t = contract.team(h.iam)
    with as_service_account("engine"):
        group = h.iam.create_group("everyone")
        h.iam.add_group_member(group.id, t.account.id)
        h.iam.add_group_member(group.id, t.outsider.id)
        h.iam.attach_policy(roles.VIEWER, group.id, WS1)
        h.iam.attach_policy(roles.VIEWER, group.id, contract.OTHER_ORG)


def test_a_group_of_another_workspace_is_not_found_when_attaching(h):
    t = contract.team(h.iam)
    with h.as_(t.ws_admin):
        policy = h.iam.create_policy("readers", contract.reader(), scope=WS1)
        with pytest.raises(IAMNotFoundError):
            h.iam.attach_policy(policy.id, t.ws2_group, WS1)
        with pytest.raises(IAMNotFoundError):
            h.iam.attach_policy(t.ws2_policy, t.member.id, WS1)


# -- owners are containers ------------------------------------------------------------

CRM = ActionCatalog(
    service="crm",
    version=1,
    resource_types=(ResourceType("project", container=True),),
    actions=(ActionSpec("CreateProject", "write", ("project",), creates=True),),
)
QUERY = "triple_store:Query"
GRAPHS = "${scope}/triple_store:graph/*"


def _project(h: IAMHarness, project: str = "p-9", inside: str = WS1) -> str:
    """A container of another module inside ``inside``: a CRM project."""
    h.iam._register_catalog(CRM)
    h.first_party_may("crm")
    with as_service_account("api"):
        return h.iam.register_container("crm", "project", project, parent=inside).name


def _graphs() -> dict:
    return contract.document(contract.statement("Allow", [QUERY], [GRAPHS]))


def test_a_policy_is_attached_at_its_owner_or_below(h):
    t = contract.team(h.iam)
    project = _project(h)
    bob = h.user("bob-at-p")
    with as_service_account("engine"):
        ws_policy = h.iam.create_policy("ws", _graphs(), scope=WS1)
        org_policy = h.iam.create_policy("org", _graphs(), scope=ORG_SCOPE)
        project_policy = h.iam.create_policy("project", _graphs(), scope=project)
        # A workspace's at the workspace or a container inside it.
        for scope in (WS1, project, project + "/*", WS1 + "/*"):
            h.iam.attach_policy(ws_policy.id, bob.id, scope)
        # An organisation's at it, below it, at any container under it.
        for scope in (ORG_SCOPE, contract.ORG_WIDE, WS2, project):
            h.iam.attach_policy(org_policy.id, bob.id, scope)
        # Nothing above its owner, beside it, at the platform or unscoped.
        for policy, scope in (
            (ws_policy, ORG_SCOPE),
            (ws_policy, contract.ORG_WIDE),
            (ws_policy, WS2),
            (ws_policy, "abi:"),
            (ws_policy, None),
            (org_policy, contract.OTHER_ORG),
            (org_policy, "abi:"),
            (project_policy, WS1),
        ):
            with pytest.raises(ValueError, match="belongs to"):
                h.iam.attach_policy(policy.id, bob.id, scope)
    assert t.member  # the team's containers are registered


def test_a_policy_at_a_container_inside_a_workspace_reaches_only_what_it_holds(h):
    contract.team(h.iam)
    project = _project(h)
    bob = h.user("bob-at-p")
    with as_service_account("engine"):
        policy = h.iam.create_policy("ws", _graphs(), scope=WS1)
        h.iam.attach_policy(policy.id, bob.id, project)
    assert h.allowed(QUERY, name_in(project, "triple_store:graph/g"), bob)
    assert not h.allowed(QUERY, name_in(WS1, "triple_store:graph/g"), bob)
    assert not h.allowed(QUERY, name_in(WS2, "triple_store:graph/g"), bob)


def test_a_sub_policy_is_owned_within_its_parents_owner(h):
    contract.team(h.iam)
    project = _project(h)
    with as_service_account("engine"):
        ws_parent = h.iam.create_policy("ws", _graphs(), scope=WS1)
        project_parent = h.iam.create_policy("project", _graphs(), scope=project)
        # A container inside the parent's owner owns a sub-policy of it.
        made = h.iam.create_policy("p", _graphs(), scope=project, parent=ws_parent.id)
        assert made.owner_scope == project
        # Never one above it or beside it.
        for owner in (WS1, ORG_SCOPE, WS2):
            with pytest.raises(ValueError, match="or below"):
                h.iam.create_policy(
                    "x", _graphs(), scope=owner, parent=project_parent.id
                )


@pytest.mark.parametrize(
    "held_at",
    ["owner", "ancestor", "below the ancestor", "the platform", "unscoped"],
)
def test_a_parent_held_at_the_owner_or_above_is_derived_from(h, held_at):
    """Derive only from what you hold: ``P`` attached at the sub-policy's owner,
    at a container it sits in (below it or not), at the platform or unscoped."""
    contract.team(h.iam)
    lead = h.user("lead")
    h.attach(roles.ADMIN, lead.id, WS1)
    with as_service_account("engine"):
        if held_at == "unscoped":
            parent = h.iam.create_policy(
                "every graph",
                contract.document(
                    contract.statement(
                        "Allow", [QUERY], anywhere("triple_store:graph/*")
                    )
                ),
            )
        else:
            parent = h.iam.create_policy("graphs", _graphs())
        scope = {
            "owner": WS1,
            "ancestor": ORG_SCOPE,
            "below the ancestor": contract.ORG_WIDE,
            "the platform": "abi:",
            "unscoped": None,
        }[held_at]
        h.iam.attach_policy(parent.id, lead.id, scope)
    with h.as_(lead):
        made = h.iam.create_policy("mine", _graphs(), scope=WS1, parent=parent.id)
    assert made.parent_id == parent.id


@pytest.mark.parametrize("held_at", ["beside", "inside the owner", "another org"])
def test_a_parent_held_beside_or_below_the_owner_is_not_derived_from(h, held_at):
    contract.team(h.iam)
    project = _project(h)
    lead = h.user("lead")
    h.attach(roles.ADMIN, lead.id, WS1)
    with as_service_account("engine"):
        parent = h.iam.create_policy("graphs", _graphs())
        scope = {
            "beside": WS2,
            "inside the owner": project,
            "another org": contract.OTHER_ORG,
        }[held_at]
        h.iam.attach_policy(parent.id, lead.id, scope)
    with (
        h.as_(lead),
        pytest.raises(PermissionDeniedError, match=f"at {re.escape(WS1)} or above"),
    ):
        h.iam.create_policy("mine", _graphs(), scope=WS1, parent=parent.id)


def test_a_group_of_a_container_holds_the_users_of_its_top_container(h):
    """A workspace's group takes anyone with an attachment within its
    organisation (at another workspace, below the org, inside a project), never
    a user of another organisation."""
    t = contract.team(h.iam)
    project = _project(h, inside=WS2)
    in_project, below_org = h.user("in-project"), h.user("below-org")
    h.attach(roles.VIEWER, in_project.id, project)
    h.attach(roles.VIEWER, below_org.id, contract.ORG_WIDE)
    with as_service_account("engine"):
        group = h.iam.create_group("ws-1 analysts", scope=WS1)
        for user in (t.colleague, in_project, below_org):
            h.iam.add_group_member(group.id, user.id)
        with pytest.raises(ValueError, match=re.escape(f"nothing in {ORG_SCOPE}")):
            h.iam.add_group_member(group.id, t.outsider.id)
    # A workspace at the platform is its own top container: its group takes its
    # own users only, not those of another workspace at the platform.
    solo, other = h.register("solo", "-"), h.register("other", "-")
    there, elsewhere = h.user("there"), h.user("elsewhere")
    h.attach(roles.MEMBER, there.id, solo)
    h.attach(roles.MEMBER, elsewhere.id, other)
    with as_service_account("engine"):
        solo_group = h.iam.create_group("solo team", scope=solo)
        h.iam.add_group_member(solo_group.id, there.id)
        with pytest.raises(ValueError):
            h.iam.add_group_member(solo_group.id, elsewhere.id)


# -- the grammar before container paths ----------------------------------------------

OLD_WS1 = "abi:org-1:ws-1"


def _for_user(record):
    """``api`` acting for ``record``: a first-party account, for a user."""
    from dataclasses import replace

    from naas_abi_core.engine.call_context import Principal, use_call_context

    @contextmanager
    def acting() -> Iterator[None]:
        with as_service_account("api") as ctx:
            user = Principal(id=record.id, kind="user", name=record.name)
            with use_call_context(replace(ctx, on_behalf_of=user)):
                yield

    return acting()


@pytest.mark.parametrize("account", ["engine", "api"])
def test_a_first_party_move_may_still_write_the_old_grammar(h, account):
    """A start-up move that predates container paths (a first-party account
    acting for no user) writes owners and scopes of the old grammar: named in
    UNRESOLVED, they decide nothing until the names are rewritten."""
    contract.team(h.iam)
    bob = h.user("bob-old")
    with as_service_account(account):
        policy = h.iam.create_policy(
            "old",
            contract.document(contract.statement("Allow", [QUERY], [GRAPHS])),
            scope=OLD_WS1,
        )
        h.iam.attach_policy(policy.id, bob.id, OLD_WS1)
        h.iam.attach_policy(roles.MEMBER, bob.id, OLD_WS1)
        h.iam.create_pending_grant("builtin", "eve@example.com", roles.MEMBER, OLD_WS1)
    assert policy.owner_scope == OLD_WS1
    assert policy_resource(policy.id, OLD_WS1) == f"{UNRESOLVED}/iam:policy/{policy.id}"
    assert attachment_resource(policy.id, bob.id, OLD_WS1).startswith(UNRESOLVED + "/")
    # Neither the role nor the policy reaches a new name, nor brings a companion.
    for resource in (graph("g"), name_in(WS1, "triple_store:graph/g")):
        assert not h.allowed(QUERY, resource, bob)
    assert {a.policy_id for a in h.iam.store.list_attachments(principal_id=bob.id)} == {
        policy.id,
        roles.MEMBER,
    }
    # Only what spans every container reaches what is named in UNRESOLVED.
    root = h.user("root-old")
    h.attach(roles.PLATFORM_ADMIN, root.id)
    assert h.allowed("iam:GetPolicy", policy_resource(policy.id, OLD_WS1), root)
    assert not h.allowed("iam:GetPolicy", policy_resource(policy.id, OLD_WS1), bob)


def test_anyone_else_is_refused_the_old_grammar(h):
    contract.team(h.iam)
    root, bob = h.user("root-old"), h.user("bob-old")
    h.attach(roles.PLATFORM_ADMIN, root.id)
    for acting in (h.as_(root), _for_user(root)):
        with acting:
            with pytest.raises(ValueError):
                h.iam.create_policy("old", _graphs(), scope=OLD_WS1)
            with pytest.raises(ValueError):
                h.iam.attach_policy(roles.MEMBER, bob.id, OLD_WS1)
            with pytest.raises(ValueError):
                h.iam.create_pending_grant(
                    "builtin", "eve@example.com", roles.MEMBER, OLD_WS1
                )
            with pytest.raises(ValueError):
                h.iam.list_policies(scope=OLD_WS1)
    assert h.iam.store.list_attachments(principal_id=bob.id) == []
