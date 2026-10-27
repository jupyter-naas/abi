"""Organisation and workspace sets, in process: what they bound, whom, who sets
them, and how grants meet them (``AGENTS.md``, "Sets")."""

from __future__ import annotations

import pytest

from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.services.iam import module_scopes, roles
from naas_abi_core.services.iam.catalog import ActionCatalog, ActionSpec, ResourceType
from naas_abi_core.services.iam.IAMPorts import (
    GrantNotHeldError,
    IAMNotFoundError,
    PermissionDeniedError,
    ScopeSet,
)
from naas_abi_core.services.iam.sets import SetValidationError
from naas_abi_core.services.iam.tests.iam_harness import document, graph, statement

NEXUS = ActionCatalog(
    service="nexus",
    version=1,
    resource_types=(ResourceType("feature"),),
    actions=(ActionSpec("UseFeature", "read", ("feature",)),),
)
ORG = "org-1"
WS, WS2 = "ws-1", "ws-2"
AT_WS = f"abi:{ORG}:{WS}"
AT_ORG = f"abi:{ORG}:-"
ORG_WIDE = f"abi:{ORG}:*"


def agent(name: str, module: str = "people", workspace: str = WS) -> str:
    return module_scopes.scope_resource(
        "agent", module, name, org=ORG, workspace=workspace
    )


def app(name: str, module: str = "market", workspace: str = WS) -> str:
    return module_scopes.scope_resource(
        "app", module, name, org=ORG, workspace=workspace
    )


def feature(key: str, workspace: str = WS) -> str:
    return f"abi:{ORG}:{workspace}:nexus:feature/{key}"


@pytest.fixture
def iam(iam):
    iam._register_catalog(module_scopes.CATALOG)
    iam._register_catalog(NEXUS)
    with as_service_account("engine"):
        iam.put_scope(ORG)
        iam.put_scope(ORG, WS)
        iam.put_scope(ORG, WS2)
        iam.put_feature_policies({"member": ["chat", "files"], "admin": ["chat"]})
    return iam


def _with_role(h, role: str, subject: str, scope: str = AT_WS):
    person = h.user(subject)
    h.attach(role, person.id, scope)
    return person


def _granted_agent_a(h, subject: str = "bob"):
    """A member granted agent A of P in the workspace."""
    bob = _with_role(h, roles.MEMBER, subject)
    h.grant(
        bob.id,
        statement("Allow", ["module:UseAgent"], ["${scope}:module:agent/people/A"]),
        scope=AT_WS,
    )
    return bob


def _platform_admin(h, subject: str = "root"):
    root = h.user(subject)
    h.attach(roles.PLATFORM_ADMIN, root.id)
    return root


def _set(h, workspace: str = "-", **parts) -> ScopeSet:
    return h.admin("put_set", ORG, workspace, **parts)


def _reason(h, action: str, resource: str, record=None, **kwargs) -> str:
    with h.as_(record, **kwargs):
        return h.iam.authorize(action, resource).reason


# -- what a set bounds, and whom -------------------------------------------------


def test_no_set_recorded_is_everything(h):
    admin = _with_role(h, roles.ADMIN, "alice")
    assert h.allowed("module:UseAgent", agent("A"), admin)
    assert h.allowed("module:OpenApp", app("X"), admin)
    assert h.iam.has_sets() is False


def test_a_set_bounds_a_users_direct_and_group_allows(h):
    bob = _granted_agent_a(h)
    carol = _with_role(h, roles.MEMBER, "carol")
    team = h.group("team")
    h.admin("add_group_member", team.id, carol.id)
    h.grant(
        team.id,
        statement("Allow", ["module:UseAgent"], ["${scope}:module:agent/people/*"]),
        scope=AT_WS,
    )
    assert h.allowed("module:UseAgent", agent("A"), bob)
    assert h.allowed("module:UseAgent", agent("A"), carol)

    _set(h, modules=["market"])

    assert _reason(h, "module:UseAgent", agent("A"), bob) == "outside_set"
    assert _reason(h, "module:UseAgent", agent("A"), carol) == "outside_set"
    # Not there, so not visible: the caller learns nothing more.
    with h.as_(bob):
        assert not h.iam.authorize("module:UseAgent", agent("A")).visible


@pytest.mark.parametrize("role", [roles.ADMIN, roles.OWNER])
def test_owners_and_admins_are_bounded(h, role):
    person = _with_role(h, role, "alice")
    org_person = _with_role(h, role, "olga", ORG_WIDE)
    _set(h, modules=["market"])
    for who in (person, org_person):
        assert not h.allowed("module:UseAgent", agent("A"), who)
        assert h.allowed("module:OpenApp", app("X"), who)


def test_the_user_a_call_acts_for_is_bounded(h):
    bob = _granted_agent_a(h)
    _set(h, WS, modules=["market"])
    assert _reason(h, "module:UseAgent", agent("A"), actor="api", on_behalf_of=bob) == (
        "outside_set"
    )
    # Another workspace of the org has no set: nothing narrows there.
    h.grant(
        bob.id,
        statement("Allow", ["module:UseAgent"], ["${scope}:module:agent/people/A"]),
        scope=f"abi:{ORG}:{WS2}",
    )
    h.attach(roles.MEMBER, bob.id, f"abi:{ORG}:{WS2}")
    assert h.allowed(
        "module:UseAgent", agent("A", workspace=WS2), actor="api", on_behalf_of=bob
    )


def test_the_platform_admin_and_service_accounts_are_not_bounded(h):
    root = _platform_admin(h)
    module = h.service_account("module/acme/people")
    h.grant(
        module.id,
        statement("Allow", ["module:UseAgent"], ["abi:*:*:module:agent/*"]),
    )
    _set(h, modules=[], features=[])
    _set(h, WS, modules=[], features=[])
    assert h.allowed("module:UseAgent", agent("A"), root)
    assert h.allowed("nexus:UseFeature", feature("chat"), root)
    assert h.allowed("module:UseAgent", agent("A"), module)
    assert h.allowed("module:UseAgent", agent("A"), actor="engine")
    # A platform admin through a group is not bounded either.
    admins = h.group("admins")
    support = h.user("support")
    h.admin("add_group_member", admins.id, support.id)
    h.attach(roles.PLATFORM_ADMIN, admins.id)
    assert h.allowed("module:UseAgent", agent("A"), support)
    # But a service account acting for a user is bounded through the user.
    bob = _granted_agent_a(h)
    assert not h.allowed("module:UseAgent", agent("A"), module, on_behalf_of=bob)


def test_a_platform_admin_attachment_at_a_scope_unbinds_no_one(h):
    """Only the platform's own attachment of builtin.platform_admin takes its
    holder out of the sets (attach_policy refuses one at a scope; the store may
    still hold one)."""
    from naas_abi_core.services.iam.IAMPorts import Attachment, new_id

    olga = _with_role(h, roles.ADMIN, "olga")
    h.iam.store.attach(Attachment(new_id("att"), roles.PLATFORM_ADMIN, olga.id, AT_ORG))
    h.iam.invalidate()
    _set(h, modules=["market"])
    assert _reason(h, "module:UseAgent", agent("A"), olga) == "outside_set"


def test_denies_and_other_actions_are_unchanged(h):
    bob = _with_role(h, roles.MEMBER, "bob")
    _set(h, modules=[], features=[])
    assert h.allowed("triple_store:Query", graph("sales"), bob)
    h.grant(bob.id, statement("Deny", ["triple_store:Query"], ["*"]))
    assert _reason(h, "triple_store:Query", graph("sales"), bob) == "explicit_deny"


def test_feature_sets_bound_use_feature(h):
    bob = _with_role(h, roles.MEMBER, "bob")
    assert h.allowed("nexus:UseFeature", feature("files"), bob)
    _set(h, WS, features=["chat"])
    assert h.allowed("nexus:UseFeature", feature("chat"), bob)
    assert _reason(h, "nexus:UseFeature", feature("files"), bob) == "outside_set"
    _set(h, features=[])
    assert not h.allowed("nexus:UseFeature", feature("chat"), bob)


def test_narrowing_applies_at_once_and_lists_follow(h):
    admin = _with_role(h, roles.ADMIN, "alice")
    names = [agent("A"), agent("B"), agent("C", module="market")]
    with h.as_(admin):
        assert h.iam.filter("module:UseAgent", names).allowed == names
    _set(h, modules=["agent/people/B"])
    with h.as_(admin):
        assert h.iam.filter("module:UseAgent", names).allowed == [agent("B")]
        assert not h.iam.allows_every("module", "module", "agent")
    _set(h)  # nothing recorded again: everything
    with h.as_(admin):
        assert h.iam.filter("module:UseAgent", names).allowed == names


# -- who sets them -----------------------------------------------------------------


def test_the_platform_admin_sets_an_orgs_set(h):
    root = _platform_admin(h)
    org_owner = _with_role(h, roles.OWNER, "olga", AT_ORG)
    org_wide = _with_role(h, roles.OWNER, "owen", ORG_WIDE)
    for refused in (org_owner, org_wide):
        with h.as_(refused), pytest.raises(PermissionDeniedError):
            h.iam.put_set(ORG, modules=["people"])
    with h.as_(root):
        recorded = h.iam.put_set(ORG, modules=["people", "market"])
    assert recorded == ScopeSet(ORG, modules=("market", "people"))
    # The org's owners read it, at the org.
    with h.as_(org_owner):
        assert h.iam.get_set(ORG).modules == ("market", "people")


def test_the_orgs_owners_and_admins_set_a_workspaces_set(h):
    org_admin = _with_role(h, roles.ADMIN, "olga", ORG_WIDE)
    ws_admin = _with_role(h, roles.ADMIN, "wanda")
    member = _with_role(h, roles.MEMBER, "bob")
    with h.as_(ws_admin), pytest.raises(PermissionDeniedError):
        h.iam.put_set(ORG, WS, modules=["people"])
    with h.as_(org_admin):
        h.iam.put_set(ORG, WS, modules=["people"], features=["chat"])
    with h.as_(ws_admin):
        assert h.iam.get_set(ORG, WS).modules == ("people",)
        assert h.iam.effective_set(ORG, WS).features == ("chat",)
    with h.as_(member), pytest.raises(PermissionDeniedError):
        h.iam.get_set(ORG, WS)
    with h.as_(member):
        assert h.iam.list_sets(ORG) == []
    with h.as_(org_admin):
        assert [s.workspace for s in h.iam.list_sets(ORG)] == [WS]


def test_a_workspace_set_wider_than_its_orgs_is_refused(h):
    _set(h, modules=["people", "market"], features=["chat"])
    with pytest.raises(SetValidationError) as refused:
        _set(h, WS, modules=["people", "other", "agent/crm/Sales"], features=["files"])
    message = str(refused.value)
    assert "organization org-1" in message
    for extra in ("other", "agent/crm/Sales", "feature files"):
        assert extra in message
    assert "people" not in message.split(":", 1)[1]
    _set(h, WS, modules=["agent/people/A", "market"], features=["chat"])
    with pytest.raises(IAMNotFoundError):
        h.admin("put_set", "org-2", WS, modules=[])


def test_narrowing_the_org_leaves_workspace_sets_recorded_but_bounded(h):
    admin = _with_role(h, roles.ADMIN, "alice")
    _set(h, modules=["people", "market"])
    _set(h, WS, modules=["people", "market"])
    _set(h, modules=["market"])
    assert h.admin("get_set", ORG, WS).modules == ("market", "people")
    assert h.admin("effective_set", ORG, WS).modules == ("market",)
    assert not h.allowed("module:UseAgent", agent("A"), admin)


def test_deleting_a_scope_forgets_its_sets(h):
    _set(h, modules=["people"])
    _set(h, WS, modules=["people"])
    h.admin("delete_scope", ORG, WS)
    assert [(s.org, s.workspace) for s in h.admin("list_sets")] == [(ORG, "-")]
    h.admin("delete_scope", ORG)
    assert h.admin("list_sets") == []


# -- grants meet sets ------------------------------------------------------------------


def test_granting_outside_the_set_is_refused_naming_the_set(h):
    ws_admin = _with_role(h, roles.ADMIN, "wanda")
    bob = _with_role(h, roles.MEMBER, "bob")
    _set(h, modules=["people", "market"])
    _set(h, WS, modules=["people"])
    with h.as_(ws_admin):
        inside = h.iam.create_policy(
            "agent A",
            document(
                statement(
                    "Allow", ["module:UseAgent"], ["${scope}:module:agent/people/A"]
                )
            ),
            scope=AT_WS,
        )
        h.iam.attach_policy(inside.id, bob.id, AT_WS)
        with pytest.raises(GrantNotHeldError) as refused:
            h.iam.create_policy(
                "market app",
                document(
                    statement(
                        "Allow", ["module:OpenApp"], ["${scope}:module:app/market/*"]
                    )
                ),
                scope=AT_WS,
            )
    assert "the set of workspace ws-1 does not include it" in str(refused.value)
    _set(h, WS, modules=["people", "market"])
    _set(h, modules=["people"])
    with h.as_(ws_admin), pytest.raises(GrantNotHeldError) as refused:
        h.iam.create_policy(
            "market app",
            document(
                statement("Allow", ["module:OpenApp"], ["${scope}:module:app/market/X"])
            ),
            scope=AT_WS,
        )
    assert "the set of organization org-1 does not include it" in str(refused.value)


def test_grantable_intersects_holdings_with_the_sets(h):
    ws_admin = _with_role(h, roles.ADMIN, "wanda")
    root = _platform_admin(h)
    _set(h, modules=["people", "agent/market/Analyst"])
    _set(h, WS, modules=["agent/people/A", "agent/market/Analyst"], features=["chat"])

    def held(record, action):
        with h.as_(record):
            catalogs = {c.service: c for c in h.iam.grantable(AT_WS)}
        found = {a.action: a for c in catalogs.values() for a in c.actions}.get(action)
        # What names the action's own type (a role's statement lists every
        # module type for each of its actions).
        kind = {"module:UseAgent": "agent", "module:OpenApp": "app"}.get(action, "")
        return sorted(
            r
            for r in (found.resources if found else ())
            if kind in r or r.endswith(":*")
        )

    assert held(ws_admin, "module:UseAgent") == [
        "${scope}:module:agent/market/Analyst",
        "${scope}:module:agent/people/A",
    ]
    assert held(ws_admin, "module:OpenApp") == []
    assert held(ws_admin, "nexus:UseFeature") == ["${scope}:nexus:feature/chat"]
    # Not bounded, the platform admin may grant what it holds.
    assert "${scope}:*" in held(root, "module:OpenApp")


def test_the_edf_scenario(h):
    """The platform admin gives O {P, M}; O's admin gives W {P, M}; a module
    outside O's set is refused for W; removing P from O takes it at once from
    W's admin and from a member granted agent A, never from the platform admin."""
    root = _platform_admin(h)
    org_admin = _with_role(h, roles.ADMIN, "olga", ORG_WIDE)
    ws_admin = _with_role(h, roles.ADMIN, "wanda")
    bob = _granted_agent_a(h)
    with h.as_(root):
        h.iam.put_set(ORG, modules=["people", "market"])
    with h.as_(org_admin):
        h.iam.put_set(ORG, WS, modules=["people", "market"])
        with pytest.raises(SetValidationError) as refused:
            h.iam.put_set(ORG, WS, modules=["people", "market", "crm"])
    assert "crm" in str(refused.value)
    assert h.allowed("module:UseAgent", agent("A"), bob)
    assert not h.allowed("module:UseAgent", agent("B"), bob)
    assert h.allowed("module:UseAgent", agent("B"), ws_admin)
    assert h.allowed("module:UseAgent", agent("A"), actor="api", on_behalf_of=bob)

    with h.as_(root):
        h.iam.put_set(ORG, modules=["market"])

    assert not h.allowed("module:UseAgent", agent("A"), bob)
    assert not h.allowed("module:UseAgent", agent("A"), actor="api", on_behalf_of=bob)
    assert not h.allowed("module:UseAgent", agent("B"), ws_admin)
    assert h.allowed("module:OpenApp", app("X"), ws_admin)
    assert h.allowed("module:UseAgent", agent("A"), root)
