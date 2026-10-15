"""IAMService: its own operations, authorized with ``iam:*``, caching and boot."""

from __future__ import annotations

import time

import pytest

from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.services.iam import roles
from naas_abi_core.services.iam.adapters.secondary.IAMStoreMemory import IAMStoreMemory
from naas_abi_core.services.iam.catalog import ActionCatalog, ActionSpec, ResourceType
from naas_abi_core.services.iam.IAMPorts import (
    IAMConflictError,
    IAMNotFoundError,
    PermissionDeniedError,
    RevisionConflictError,
)
from naas_abi_core.services.iam.IAMService import (
    LEGACY_NEXUS_ISSUER,
    IAMService,
    attachment_resource,
)
from naas_abi_core.services.iam.policy import PolicyValidationError
from naas_abi_core.services.iam.tests.iam_harness import (
    TRIPLE_STORE,
    document,
    graph,
    statement,
)

QUERY = "triple_store:Query"


# -- boot ---------------------------------------------------------------------------


def test_bootstrap_is_idempotent_and_seeds_the_root_of_trust():
    store = IAMStoreMemory()
    service = IAMService(store)
    service.bootstrap()
    revision = store.revision()
    service.bootstrap()
    assert store.revision() == revision
    for name, policy_id in roles.SERVICE_ACCOUNTS.items():
        account = store.find_service_account(name)
        assert account is not None
        assert [
            a.policy_id for a in store.list_attachments(principal_id=account.id)
        ] == [policy_id]
    managed = {p.id for p in store.list_policies(limit=1000).items}
    assert {
        roles.VIEWER,
        roles.MEMBER,
        roles.ADMIN,
        roles.OWNER,
        roles.PLATFORM_ADMIN,
        roles.SELF,
        roles.PLATFORM_VIEWER,
        roles.PLATFORM_MEMBER,
        roles.ENGINE,
        roles.API,
        roles.IDP,
        roles.TRANSITIONAL_MODULE,
    } <= managed
    assert [c.service for c in store.list_catalogs()] == ["iam"]


def test_nothing_is_allowed_before_bootstrap():
    service = IAMService(IAMStoreMemory())
    with as_service_account("engine"):
        assert not service.authorize(QUERY, graph("a")).allowed
        with pytest.raises(IAMNotFoundError):
            service.create_policy("p", document(statement("Allow", ["iam:*"], ["*"])))


def test_built_in_service_accounts_stay_active(h):
    engine = h.iam.store.find_service_account("engine")
    with as_service_account("engine"), pytest.raises(IAMConflictError):
        h.iam.suspend_principal(engine.id)


# -- IAM authorizes itself ------------------------------------------------------------


def test_iam_operations_need_iam_actions(h):
    bob = h.user()
    doc = document(statement("Allow", [QUERY], ["*"]))
    with h.as_(bob):
        with pytest.raises(IAMNotFoundError):
            h.iam.create_policy("mine", doc)
        with pytest.raises(IAMNotFoundError):
            h.iam.attach_policy(roles.PLATFORM_ADMIN, bob.id)
        with pytest.raises(IAMNotFoundError):
            h.iam.create_service_account("ci/x")
        # bob can see himself (builtin.self), not suspend himself.
        with pytest.raises(PermissionDeniedError):
            h.iam.suspend_principal(bob.id)
        assert h.iam.get_principal(bob.id).id == bob.id
    h.grant(
        bob.id,
        statement(
            "Allow", ["iam:CreatePolicy", "iam:GetPolicy"], ["abi:-:-:iam:policy/*"]
        ),
    )
    with h.as_(bob):
        created = h.iam.create_policy("mine", doc)
        assert h.iam.get_policy(created.id).name == "mine"
        with pytest.raises(PermissionDeniedError):
            h.iam.delete_policy(created.id)


def test_list_operations_return_only_allowed_items_and_page_after_filtering(h):
    users = [h.user(f"u{i}") for i in range(6)]
    visible = sorted(u.id for u in users[::2])
    bob = h.user("bob")
    h.grant(
        bob.id,
        statement(
            "Allow",
            ["iam:ListPrincipals"],
            [f"abi:-:-:iam:principal/{i}" for i in visible],
        ),
    )
    with h.as_(bob):
        first = h.iam.list_principals("user", limit=2)
        assert [p.id for p in first.items] == visible[:2]
        assert first.next_after is not None
        rest = h.iam.list_principals("user", limit=2, after=first.next_after)
        assert [p.id for p in rest.items] == visible[2:]
        assert rest.next_after is None


# -- principals and groups --------------------------------------------------------------


def test_ensure_user_creates_once_and_refreshes_the_profile(h):
    first = h.user("bob", email="bob@example.com")
    again = h.user("bob", email="bob@example.com")
    assert again == first
    renamed = h.user("bob", email="robert@example.com", display_name="Robert")
    assert renamed.id == first.id
    assert (renamed.email, renamed.display_name) == ("robert@example.com", "Robert")
    assert h.user("bob2").id != first.id


def test_legacy_nexus_users_resolve_by_their_nexus_id(h):
    """TRANSITIONAL until OIDC: Nexus names its users by Nexus id on calls."""
    record = h.admin("ensure_user", LEGACY_NEXUS_ISSUER, "user-0123456789ab")
    h.attach(roles.PLATFORM_ADMIN, record.id)
    from naas_abi_core.engine.call_context import (
        CallContext,
        Principal,
        use_call_context,
    )

    ctx = CallContext(
        principal=Principal(id="api", kind="service_account", name="api"),
        on_behalf_of=Principal(id="user-0123456789ab", kind="user"),
    )
    with use_call_context(ctx):
        assert h.iam.authorize(QUERY, graph("a")).allowed


def test_deleting_a_principal_keeps_its_id_and_drops_its_grants(h):
    bob = h.user()
    sales = h.group()
    h.admin("add_group_member", sales.id, bob.id)
    h.grant(bob.id, statement("Allow", [QUERY], ["*"]))
    deleted = h.admin("delete_principal", bob.id)
    assert deleted.status == "deleted"
    assert h.iam.store.get_principal(bob.id).status == "deleted"
    assert h.iam.store.list_attachments(principal_id=bob.id) == []
    assert h.iam.store.groups_of(bob.id) == []
    assert not h.allowed(QUERY, graph("a"), bob)
    with pytest.raises(IAMConflictError):
        h.attach(roles.VIEWER, bob.id, "abi:org-1:ws-1")
    with pytest.raises(IAMConflictError):
        h.admin("resume_principal", bob.id)


def test_groups_cannot_contain_groups(h):
    outer, inner = h.group("outer"), h.group("inner")
    with pytest.raises(ValueError):
        h.admin("add_group_member", outer.id, inner.id)
    with pytest.raises(IAMNotFoundError):
        h.admin("get_group", h.user().id)


def test_group_mappings_and_members_are_listed(h):
    sales = h.group()
    bob = h.user()
    h.admin("add_group_member", sales.id, bob.id)
    h.admin("map_idp_group", "acme", "Sales", sales.id)
    assert h.admin("list_group_members", sales.id) == [bob.id]
    assert [m.claim_value for m in h.admin("list_idp_group_mappings", sales.id)] == [
        "Sales"
    ]
    assert h.admin("unmap_idp_group", "acme", "Sales", sales.id) is True
    assert h.iam.resolve_idp_groups("acme", ["Sales"]) == []


# -- policies ---------------------------------------------------------------------------------


def test_policies_are_validated_against_the_registered_catalogs(h):
    with pytest.raises(PolicyValidationError) as invalid:
        h.admin(
            "create_policy",
            "bad",
            document(
                statement("Allow", ["triple_store:Teleport"], ["*"]),
                statement("Allow", ["nothing:*"], ["*"]),
                statement("Allow", [QUERY], ["graph/a"]),
            ),
        )
    errors = " | ".join(invalid.value.errors)
    assert "triple_store:Teleport" in errors
    assert "nothing:*" in errors
    assert "graph/a" in errors
    created = h.admin(
        "create_policy", "ok", document(statement("Allow", ["triple_store:Q*"], ["*"]))
    )
    assert created.revision == 1


def test_updates_are_optimistic_and_managed_policies_are_iams_alone(h):
    created = h.admin(
        "create_policy", "p", document(statement("Allow", [QUERY], ["*"]))
    )
    updated = h.admin(
        "update_policy",
        created.id,
        expected_revision=1,
        document=document(statement("Allow", ["triple_store:Insert"], ["*"])),
    )
    assert updated.revision == 2
    with pytest.raises(RevisionConflictError):
        h.admin("update_policy", created.id, expected_revision=1, name="stale")
    with pytest.raises(IAMConflictError):
        h.admin("update_policy", roles.VIEWER, expected_revision=1, name="mine")
    with pytest.raises(IAMConflictError):
        h.admin("delete_policy", roles.VIEWER)


def test_an_attached_policy_cannot_be_deleted(h):
    bob = h.user()
    policy = h.grant(bob.id, statement("Allow", [QUERY], ["*"]))
    with pytest.raises(IAMConflictError):
        h.admin("delete_policy", policy.id)
    h.admin("detach_policy", policy.id, bob.id)
    h.admin("delete_policy", policy.id)


def test_a_policy_using_scope_needs_a_scoped_attachment(h):
    bob = h.user()
    with pytest.raises(ValueError):
        h.attach(roles.VIEWER, bob.id)
    with pytest.raises(ValueError):
        h.attach(roles.VIEWER, bob.id, "org-1:ws-1")
    first = h.attach(roles.VIEWER, bob.id, "abi:org-1:ws-1")
    assert h.attach(roles.VIEWER, bob.id, "abi:org-1:ws-1") == first


def test_attachment_names_sit_at_their_scope():
    assert attachment_resource("builtin.viewer", "usr_x", "abi:org-1:ws-1") == (
        "abi:org-1:ws-1:iam:attachment/builtin.viewer/usr_x"
    )
    assert (
        attachment_resource("p", "u", "abi:org-1:*") == "abi:org-1:-:iam:attachment/p/u"
    )
    assert attachment_resource("p", "u", None) == "abi:-:-:iam:attachment/p/u"


def test_list_attachments_is_filtered(h):
    admin, bob = h.user("admin"), h.user("bob")
    h.attach(roles.ADMIN, admin.id, "abi:org-1:ws-1")
    h.attach(roles.VIEWER, bob.id, "abi:org-1:ws-1")
    h.attach(roles.VIEWER, bob.id, "abi:org-1:ws-2")
    with h.as_(admin):
        listed = h.iam.list_attachments(principal_id=bob.id)
    assert [a.scope for a in listed] == ["abi:org-1:ws-1"]


# -- catalogs ---------------------------------------------------------------------------------


def test_registering_a_catalog_regenerates_the_roles(h):
    bob = h.user()
    h.attach(roles.VIEWER, bob.id, "abi:org-1:ws-1")
    kv = "abi:org-1:ws-1:keyvalue:key/k"
    assert not h.allowed("keyvalue:Get", kv, bob)
    catalog = ActionCatalog(
        service="keyvalue",
        version=1,
        resource_types=(ResourceType("key"),),
        actions=(
            ActionSpec("Get", "read", ("key",)),
            ActionSpec("Set", "write", ("key",)),
        ),
    )
    assert h.admin("register_catalog", catalog) is True
    assert h.allowed("keyvalue:Get", kv, bob)
    assert not h.allowed("keyvalue:Set", kv, bob)
    explanation = h.iam.authorizer.explain(h.context(bob), "keyvalue:Get", kv)
    assert explanation.statement is not None
    assert explanation.statement.policy_id == roles.VIEWER


def test_the_highest_catalog_version_wins(h):
    v2 = ActionCatalog.from_dict({**TRIPLE_STORE.to_dict(), "version": 2})
    assert h.admin("register_catalog", v2) is True
    assert h.admin("register_catalog", TRIPLE_STORE) is False
    assert h.iam.catalogs.get("triple_store") == v2
    assert [
        c.version for c in h.iam.store.list_catalogs() if c.service == "triple_store"
    ] == [2]


def test_a_catalog_cannot_drop_an_action_a_policy_names(h):
    bob = h.user()
    h.grant(bob.id, statement("Allow", ["triple_store:Insert"], ["*"]))
    shrunk = ActionCatalog(
        service="triple_store",
        version=2,
        resource_types=TRIPLE_STORE.resource_types,
        actions=tuple(a for a in TRIPLE_STORE.actions if a.name != "Insert"),
    )
    with pytest.raises(IAMConflictError):
        h.admin("register_catalog", shrunk)
    assert h.iam.catalogs.get("triple_store") == TRIPLE_STORE


def test_register_catalog_needs_the_action(h):
    with h.as_(actor="some-module"), pytest.raises(IAMNotFoundError):
        h.iam.register_catalog(TRIPLE_STORE)


# -- placements and scopes ----------------------------------------------------------------------


def test_placement_resolution(h):
    h.admin("put_placement", "document", "nexus-ws-1", "org-1", "ws-1")
    h.admin("put_placement", "document", "nexus-ws-1/*", "org-1", "ws-1")
    h.admin("put_placement", "document", "nexus-ws-1/private/*", "org-1", "ws-2")
    h.admin("put_placement", "document", "people", "-", "-")
    assert h.iam.resolve_placement("document", "nexus-ws-1") == ("org-1", "ws-1")
    assert h.iam.resolve_placement("document", "nexus-ws-1/c/d") == ("org-1", "ws-1")
    assert h.iam.resolve_placement("document", "nexus-ws-1/private/x") == (
        "org-1",
        "ws-2",
    )
    assert h.iam.resolve_placement("document", "elsewhere") == ("-", "-")
    assert h.iam.resolve_placement("dataset", "nexus-ws-1") == ("-", "-")
    assert h.admin("delete_placement", "document", "nexus-ws-1/private/*") is True
    assert h.iam.resolve_placement("document", "nexus-ws-1/private/x") == (
        "org-1",
        "ws-1",
    )
    with pytest.raises(ValueError):
        h.admin("put_placement", "document", "a*b")
    assert len(h.admin("list_placements", "document")) == 3


def test_scopes_map_workspaces_to_their_org(h):
    h.admin("put_scope", "org-1")
    h.admin("put_scope", "org-1", "ws-1")
    assert h.iam.workspace_org("ws-1") == "org-1"
    assert h.iam.workspace_org("ws-2") is None
    with pytest.raises(IAMConflictError):
        h.admin("put_scope", "org-2", "ws-1")
    with pytest.raises(ValueError):
        h.admin("put_scope", "Org 1")
    assert h.admin("delete_scope", "org-1", "ws-1") is True


# -- caching --------------------------------------------------------------------------------------


def test_changes_through_the_service_apply_at_the_next_check(h):
    bob = h.user()
    assert not h.allowed(QUERY, graph("a"), bob)  # cached: no access
    policy = h.grant(bob.id, statement("Allow", [QUERY], ["*"]))
    assert h.allowed(QUERY, graph("a"), bob)
    h.admin("detach_policy", policy.id, bob.id)
    assert not h.allowed(QUERY, graph("a"), bob)


def test_cached_state_expires(h):
    store = h.iam.store
    service = IAMService(store, cache_ttl_seconds=0.05)
    from naas_abi_core.services.iam.tests.iam_harness import IAMHarness

    other = IAMHarness(service)
    bob = h.user()
    assert not other.allowed(QUERY, graph("a"), bob)
    # Another process writes the shared store: this one never hears of it.
    h.grant(bob.id, statement("Allow", [QUERY], ["*"]))
    assert not other.allowed(QUERY, graph("a"), bob)
    time.sleep(0.1)
    assert other.allowed(QUERY, graph("a"), bob)


def test_listeners_hear_every_change(h):
    heard: list[int] = []
    h.iam.add_change_listener(heard.append)
    h.iam.add_change_listener(lambda _revision: 1 / 0)  # never fails a write
    h.user("new")
    assert heard and heard[-1] == h.iam.store.revision()
