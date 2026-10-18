"""IAMService: its own operations, authorized with ``iam:*``, caching and boot."""

from __future__ import annotations

import time
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.services.iam import roles
from naas_abi_core.services.iam.adapters.secondary.IAMStoreMemory import IAMStoreMemory
from naas_abi_core.services.iam.catalog import ActionCatalog, ActionSpec, ResourceType
from naas_abi_core.services.iam.IAMPorts import (
    IAMConflictError,
    IAMNotFoundError,
    KeyRefusedError,
    PermissionDeniedError,
    RevisionConflictError,
)
from naas_abi_core.services.iam.IAMService import (
    LEGACY_NEXUS_ISSUER,
    IAMService,
    attachment_resource,
)
from naas_abi_core.services.iam.policy import (
    PolicyValidationError,
    parse_policy_document,
)
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
        roles.TRANSITIONAL_NEXUS_USER,
        roles.MODULE_BOOTSTRAP,
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


def _nexus_call(user_id: str):
    from naas_abi_core.engine.call_context import (
        CallContext,
        Principal,
        use_call_context,
    )

    return use_call_context(
        CallContext(
            principal=Principal(id="api", kind="service_account", name="api"),
            on_behalf_of=Principal(id=user_id, kind="user"),
        )
    )


def test_a_nexus_user_holds_the_transitional_kernel_grant(h):
    """TRANSITIONAL until #65: Nexus decides for a user named by its Nexus id."""
    with _nexus_call("user-0123456789ab"):
        assert h.iam.authorize(
            "model_registry:Chat", "abi:-:-:model_registry:model/m"
        ).allowed
        assert h.iam.authorize(QUERY, graph("a")).allowed
        assert not h.iam.authorize(
            "iam:ListPrincipals", "abi:-:-:iam:principal/x"
        ).allowed


def _approved_module(h, document_, name="module/default/research"):
    account = h.service_account(name)
    project, module_id = name.split("/")[1:]
    with h.as_(account):
        h.iam.submit_manifest(module_id, project, document_)
    h.admin("approve_manifest", account.id)
    return account


def test_a_remote_module_cannot_evict_registrations(h):
    """Its bootstrap registers its own module; no manifest grants eviction."""
    account = _approved_module(h, document(statement("Allow", ["discovery:*"], ["*"])))
    own = "abi:-:-:discovery:module/default/research"
    other = "abi:-:-:discovery:module/default/other"
    assert h.allowed("discovery:Register", own, account)
    assert not h.allowed("discovery:Evict", own, account)
    assert not h.allowed("discovery:Evict", other, account)


RUN = "abi:-:-:discovery:run/{owner}/default/inv-1"


@pytest.mark.parametrize(
    "action", ["discovery:GetAgentRun", "discovery:CancelAgentRun"]
)
def test_a_nexus_user_reaches_only_their_own_agent_runs(h, action):
    """Regression: the transitional grant must not open another user's run."""
    with _nexus_call("user-aaaaaaaaaaaa"):
        assert h.iam.authorize(action, RUN.format(owner="user-aaaaaaaaaaaa")).allowed
        assert not h.iam.authorize(
            action, RUN.format(owner="user-bbbbbbbbbbbb")
        ).allowed
        assert h.iam.authorize(
            "discovery:InvokeAgent", "abi:-:-:discovery:agent/default/m/a"
        ).allowed


@pytest.mark.parametrize(
    "action", ["discovery:GetAgentRun", "discovery:CancelAgentRun"]
)
def test_a_module_acting_for_a_user_follows_that_users_runs(h, action):
    """A run started for a user is the user's: a module delegating for that
    user (a delegated token, #62) follows it, and still no one else's."""
    from naas_abi_sdk.module import ModuleDependencies
    from naas_abi_sdk.permissions import default_manifest

    from naas_abi_core.engine.call_context import (
        CallContext,
        Principal,
        use_call_context,
    )

    account = _approved_module(
        h, default_manifest(ModuleDependencies(modules=("other",)))
    )
    ada = "user-aaaaaaaaaaaa"
    delegated = CallContext(
        principal=Principal(id=account.id, kind="service_account", name=account.name),
        on_behalf_of=Principal(id=ada, kind="user"),
    )
    with use_call_context(delegated):
        assert h.iam.authorize(action, RUN.format(owner=ada)).allowed
        assert not h.iam.authorize(
            action, RUN.format(owner="user-bbbbbbbbbbbb")
        ).allowed


@pytest.mark.parametrize(
    "action", ["discovery:GetAgentRun", "discovery:CancelAgentRun"]
)
def test_a_remote_module_reaches_only_its_own_agent_runs(h, action):
    from naas_abi_sdk.module import ModuleDependencies
    from naas_abi_sdk.permissions import default_manifest

    account = _approved_module(
        h, default_manifest(ModuleDependencies(modules=("other",)))
    )
    assert h.allowed(action, RUN.format(owner=account.id), account)
    assert not h.allowed(action, RUN.format(owner="user-1"), account)
    assert not h.allowed(action, RUN.format(owner="other"), account)


def test_an_iam_user_holds_no_transitional_grant(h):
    bob = h.user()
    assert not h.allowed(
        "model_registry:Chat",
        "abi:-:-:model_registry:model/m",
        actor="api",
        on_behalf_of=bob,
    )


def test_an_explicit_deny_beats_the_transitional_user_grant(h):
    record = h.admin("ensure_user", LEGACY_NEXUS_ISSUER, "user-0123456789ab")
    h.grant(record.id, statement("Deny", [QUERY], [graph("a")]))
    with _nexus_call("user-0123456789ab"):
        assert not h.iam.authorize(QUERY, graph("a")).allowed
        assert h.iam.authorize(QUERY, graph("b")).allowed


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
        attachment_resource("p", "u", "abi:org-1:*")
        == "abi:org-1:%2A:iam:attachment/p/u"
    )
    assert attachment_resource("p", "u", None) == "abi:%2A:%2A:iam:attachment/p/u"


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


# -- review round 1 --------------------------------------------------------------------


def test_a_clear_during_a_lookup_keeps_its_stale_value_out_of_the_cache():
    from naas_abi_core.services.iam.IAMService import _TTLCache

    cache = _TTLCache(60, 10)
    calls: list[str] = []

    def stale():
        calls.append("stale")
        cache.clear()  # a change lands while the old state is being read
        return "stale"

    assert cache.get("k", stale) == "stale"
    assert cache.get("k", lambda: "fresh") == "fresh"
    assert cache.get("k", lambda: "never") == "fresh"


def test_a_suspension_during_a_check_applies_to_the_next_one(h):
    bob = h.user()
    h.attach(roles.PLATFORM_ADMIN, bob.id)
    store = h.iam.store
    original = store.attachments_for
    suspended = False

    def racing(principal_ids):
        nonlocal suspended
        found = original(principal_ids)
        if not suspended:
            suspended = True
            h.admin("suspend_principal", bob.id)
        return found

    store.attachments_for = racing  # type: ignore[method-assign]
    try:
        h.allowed(QUERY, graph("a"), bob)  # reads the pre-suspension state
    finally:
        store.attachments_for = original  # type: ignore[method-assign]
    assert not h.allowed(QUERY, graph("a"), bob)


def test_ensure_user_survives_a_concurrent_first_sighting(h):
    store = h.iam.store
    first = h.user("bob")
    original = store.find_user
    misses = iter([None])

    def late_find(issuer, subject):
        # The first lookup misses: another request is creating the same user.
        return next(misses, None) or original(issuer, subject)

    store.find_user = late_find  # type: ignore[method-assign]
    try:
        again = h.user("bob")
    finally:
        store.find_user = original  # type: ignore[method-assign]
    assert again.id == first.id


def test_explain_reveals_nothing_without_iam_explain(h):
    carol = h.user("carol")
    group = h.group("secret-team")
    errors = []
    for principal_id in (group.id, "usr_" + "0" * 26, h.user("bob").id):
        with h.as_(carol), pytest.raises(IAMNotFoundError) as refused:
            h.iam.explain(QUERY, graph("a"), principal_id=principal_id)
        errors.append(type(refused.value))
    assert len(set(errors)) == 1


def test_a_caller_who_may_list_nothing_never_scans_the_store(h):
    for i in range(5):
        h.user(f"u{i}")
    store = h.iam.store
    original = store.list_principals
    calls = []

    def counting(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    store.list_principals = counting  # type: ignore[method-assign]
    try:
        with h.as_(actor="some-module"):
            assert h.iam.list_principals(limit=10).items == []
    finally:
        store.list_principals = original  # type: ignore[method-assign]
    assert calls == []


def test_attachment_names_for_org_wide_scopes_differ_from_org_level_ones():
    org_wide = attachment_resource("p", "u", "abi:acme:*")
    org_level = attachment_resource("p", "u", "abi:acme:-")
    assert org_wide == "abi:acme:%2A:iam:attachment/p/u"
    assert org_level == "abi:acme:-:iam:attachment/p/u"


# -- review round 2 --------------------------------------------------------------------


def test_a_policy_attached_at_a_scope_cannot_be_updated_out_of_it(h):
    bob = h.user()
    policy = h.admin(
        "create_policy",
        "read here",
        document(statement("Allow", [QUERY], ["${scope}:triple_store:graph/*"])),
    )
    h.attach(policy.id, bob.id, "abi:acme:ws1")
    with pytest.raises(ValueError, match=r"\$\{scope\}"):
        h.admin(
            "update_policy",
            policy.id,
            expected_revision=1,
            document=document(statement("Allow", ["*"], ["*"])),
        )
    narrowed = h.admin(
        "update_policy",
        policy.id,
        expected_revision=1,
        document=document(
            statement("Allow", [QUERY], ["${scope}:triple_store:graph/a"])
        ),
    )
    assert narrowed.revision == 2
    # Unattached at any scope, a policy may name anything.
    free = h.admin(
        "create_policy", "free", document(statement("Allow", [QUERY], ["*"]))
    )
    h.admin(
        "update_policy",
        free.id,
        expected_revision=1,
        document=document(statement("Allow", ["*"], ["*"])),
    )


def test_every_workspace_is_a_name_for_org_wide_attachments_only(h):
    with pytest.raises(ValueError):
        h.admin("put_scope", "acme", "%2A")
    with pytest.raises(ValueError):
        h.admin("put_placement", "document", "nexus-ws-1/*", "acme", "%2A")
    assert h.iam.workspace_org("%2A") is None


def test_the_ensure_user_race_authorizes_the_existing_principal(h):
    bob = h.user("bob", email="bob@example.com")
    clerk = h.service_account("ci/clerk")
    h.grant(
        clerk.id,
        statement("Allow", ["iam:CreateUser"], ["abi:-:-:iam:principal/*"]),
        statement("Deny", ["iam:CreateUser"], [f"abi:-:-:iam:principal/{bob.id}"]),
    )
    store = h.iam.store
    original = store.find_user
    misses = iter([None])

    def late_find(issuer, subject):
        return next(misses, None) or original(issuer, subject)

    store.find_user = late_find  # type: ignore[method-assign]
    try:
        with h.as_(clerk), pytest.raises((IAMNotFoundError, PermissionDeniedError)):
            h.iam.ensure_user("https://idp.example", "bob", email="mallory@example.com")
    finally:
        store.find_user = original  # type: ignore[method-assign]
    assert store.get_principal(bob.id).email == "bob@example.com"


# -- service accounts, keys and the exchange (RFC §8.1, §8.2) -------------------------


def _module(h, name: str = "module/acme/people"):
    return h.service_account(name)


def test_a_key_is_shown_once_and_stored_hashed(h, iam):
    account = _module(h)
    created = h.admin("create_key", account.id, description="dev")
    assert created.value.startswith(f"abi_sk_{created.record.key_id}_")
    stored = iam.store.get_key(created.record.key_id)
    assert created.value.split("_", 3)[3] not in repr(stored)
    assert len(stored.secret_hash) == 64
    assert h.admin("list_keys", account.id) == [stored]


def test_exchange_gives_a_ten_minute_nats_token_for_the_account(h, iam):
    account = _module(h)
    value = h.admin("create_key", account.id).value
    issued = iam.exchange_key(value)
    claims = iam.verifier().verify(issued.token)
    assert claims.subject == account.id
    assert claims.name == "module/acme/people"
    assert claims.kind == "service_account" and claims.audience == "abi:nats"
    assert claims.lifetime == 600
    assert iam.store.get_key(value.split("_")[2]).last_used_at is not None


def test_a_storm_of_exchanges_writes_the_last_use_once(h, iam, monkeypatch):
    value = h.admin("create_key", _module(h).id).value
    touched: list[str] = []
    real = iam.store.touch_key
    monkeypatch.setattr(
        iam.store,
        "touch_key",
        lambda key_id, now: (touched.append(key_id), real(key_id, now)),
    )
    for _ in range(20):
        iam.exchange_key(value)
        iam.authenticate_key(value)
    assert touched == [value.split("_")[2]]


@pytest.mark.parametrize(
    "mangle",
    [
        lambda v: v[:-1] + ("A" if v[-1] != "A" else "B"),  # wrong secret
        lambda v: "abi_sk_aaaaaaaaaaaaaaaa_" + v.split("_", 3)[3],  # unknown id
        lambda v: v.replace("abi_sk_", "abi_pk_"),  # another kind
        lambda v: "not-a-key",
    ],
)
def test_exchange_refuses_a_bad_key_with_one_message(h, iam, mangle):
    value = h.admin("create_key", _module(h).id).value
    with pytest.raises(KeyRefusedError, match="^invalid key$"):
        iam.exchange_key(mangle(value))


def test_revoked_expired_or_suspended_keys_stop_at_the_next_exchange(h, iam):
    account = _module(h)
    revoked = h.admin("create_key", account.id)
    iam.exchange_key(revoked.value)
    h.admin("revoke_key", account.id, revoked.record.key_id)
    with pytest.raises(KeyRefusedError):
        iam.exchange_key(revoked.value)

    expiring = h.admin(
        "create_key", account.id, expires_at=datetime.now(UTC) + timedelta(seconds=1)
    )
    time.sleep(1.1)
    with pytest.raises(KeyRefusedError):
        iam.exchange_key(expiring.value)

    live = h.admin("create_key", account.id)
    h.admin("suspend_principal", account.id)
    with pytest.raises(KeyRefusedError):
        iam.exchange_key(live.value)
    h.admin("resume_principal", account.id)
    assert iam.exchange_key(live.value).token


def test_rotation_issues_a_new_key_and_revokes_the_old(h, iam):
    account = _module(h)
    old = h.admin("create_key", account.id, description="prod")
    new = h.admin("rotate_key", account.id, old.record.key_id)
    assert new.record.description == "prod"
    assert iam.exchange_key(new.value)
    with pytest.raises(KeyRefusedError):
        iam.exchange_key(old.value)


def test_an_account_at_its_key_limit_can_still_rotate(h, iam):
    account = _module(h)
    created = [h.admin("create_key", account.id) for _ in range(5)]
    new = h.admin("rotate_key", account.id, created[0].record.key_id)
    assert iam.exchange_key(new.value)
    with pytest.raises(KeyRefusedError):
        iam.exchange_key(created[0].value)
    assert (
        len(
            [k for k in h.admin("list_keys", account.id) if k.usable(datetime.now(UTC))]
        )
        == 5
    )


def test_a_rotated_key_gets_a_fresh_life_and_an_expired_one_rotates(h, iam):
    account = h.service_account("ci/nightly")
    short = h.admin(
        "create_key",
        account.id,
        expires_at=datetime.now(UTC) + timedelta(seconds=1),
    )
    time.sleep(1.1)
    with pytest.raises(KeyRefusedError):
        iam.exchange_key(short.value)
    new = h.admin("rotate_key", account.id, short.record.key_id)
    # Not what was left of the old key's life: a ci key's full 90 days.
    assert new.record.expires_at - datetime.now(UTC) > timedelta(days=89)
    assert iam.exchange_key(new.value)


def test_at_most_five_active_keys(h):
    account = _module(h)
    created = [h.admin("create_key", account.id) for _ in range(5)]
    with pytest.raises(IAMConflictError, match="5 active keys"):
        h.admin("create_key", account.id)
    h.admin("revoke_key", account.id, created[0].record.key_id)
    assert h.admin("create_key", account.id)


def test_ci_keys_expire_in_90_days_module_keys_never(h):
    ci = h.admin("create_key", h.service_account("ci/nightly").id).record
    assert ci.expires_at is not None
    assert ci.expires_at - datetime.now(UTC) > timedelta(days=89)
    assert h.admin("create_key", _module(h).id).record.expires_at is None


def test_keys_need_iam_actions_and_belong_to_their_account(h):
    account = _module(h)
    other = _module(h, "module/acme/other")
    key = h.admin("create_key", account.id)
    with h.as_(other):
        with pytest.raises(IAMNotFoundError):
            h.iam.create_key(account.id)
        with pytest.raises(IAMNotFoundError):
            h.iam.revoke_key(account.id, key.record.key_id)
        assert h.iam.list_keys(account.id) == []
    with pytest.raises(IAMNotFoundError):
        h.admin("revoke_key", other.id, key.record.key_id)


def test_a_module_account_starts_with_its_bootstrap_only(h, iam):
    account = _module(h)
    attached = iam.store.list_attachments(principal_id=account.id)
    assert [a.policy_id for a in attached] == [roles.MODULE_BOOTSTRAP]
    assert iam.store.list_attachments(principal_id=h.service_account("ci/x").id) == []


def test_the_engine_key_is_created_once_and_kept_in_the_secrets(iam):
    value = iam.engine_service_key()
    assert iam.secrets.get("iam/service-keys/engine") == value
    assert iam.engine_service_key() == value
    assert iam.verifier().verify(iam.exchange_key(value).token).name == "engine"


def test_a_lost_engine_key_is_replaced_not_accumulated(iam):
    first = iam.engine_service_key()
    for _ in range(6):  # each boot of a process that never saw the stored key
        iam.secrets.delete("iam/service-keys/engine")
        latest = iam.engine_service_key()
    engine = iam.store.find_service_account("engine")
    now = datetime.now(UTC)
    active = [k.key_id for k in iam.store.list_keys(engine.id) if k.usable(now)]
    assert active == [latest.split("_")[2]]
    with pytest.raises(KeyRefusedError):
        iam.exchange_key(first)


def test_in_process_tokens_for_the_engine_and_api(iam):
    for name in ("engine", "api"):
        claims = iam.verifier().verify(iam.issue_service_token(name).token)
        assert claims.name == name and claims.subject.startswith("sa_")


# -- manifests (RFC §8.3) ---------------------------------------------------------------

MANIFEST = document(
    statement(
        "Allow",
        ["triple_store:Query"],
        ["abi:-:-:triple_store:graph/${module.id}-*"],
        sid="OwnGraphs",
    )
)


def _submit(h, account, manifest=MANIFEST, module_id="people", project="acme"):
    with h.as_(account):
        return h.iam.submit_manifest(module_id, project, manifest)


def test_a_manifest_is_pending_until_approved(h, iam):
    account = _module(h)
    own = "abi:-:-:triple_store:graph/people-contacts"
    submitted = _submit(h, account)
    assert submitted.manifest.status == "pending" and not submitted.approved_now
    assert not h.allowed(QUERY, own, account)
    approved = h.admin("approve_manifest", account.id)
    assert approved.status == "approved" and approved.decided_by
    assert h.allowed(QUERY, own, account)
    assert not h.allowed(QUERY, "abi:-:-:triple_store:graph/other-x", account)
    policy = iam.store.get_policy("module.acme.people")
    assert policy.managed
    assert policy.document.statements[0].resources == (
        "abi:-:-:triple_store:graph/people-*",
    )
    # Submitting the approved version again changes nothing.
    again = _submit(h, account)
    assert again.manifest.status == "approved" and not again.approved_now


def test_approval_places_the_module_namespaces_on_the_platform(h, iam):
    account = _module(h)
    _submit(h, account)
    h.admin("approve_manifest", account.id)
    keys = {(p.service, p.id_key) for p in iam.store.list_placements()}
    assert {
        ("document", "people"),
        ("document", "people/*"),
        ("dataset", "people"),
        ("dataset", "people/*"),
    } <= keys


def test_a_new_version_waits_while_the_approved_one_holds(h):
    account = _module(h)
    _submit(h, account)
    h.admin("approve_manifest", account.id)
    wider = document(statement("Allow", ["triple_store:*"], ["*"]))
    pending = _submit(h, account, wider)
    assert pending.manifest.status == "pending"
    assert h.allowed(QUERY, "abi:-:-:triple_store:graph/people-a", account)
    assert not h.allowed("triple_store:Insert", "abi:-:-:triple_store:graph/x", account)


def test_an_admin_can_narrow_or_reject(h):
    account = _module(h)
    _submit(h, account, document(statement("Allow", ["triple_store:*"], ["*"])))
    narrowed = document(
        statement("Allow", ["triple_store:Query"], ["abi:-:-:triple_store:graph/a"])
    )
    h.admin("approve_manifest", account.id, document=narrowed)
    assert h.allowed(QUERY, "abi:-:-:triple_store:graph/a", account)
    assert not h.allowed("triple_store:Insert", "abi:-:-:triple_store:graph/a", account)

    other = _module(h, "module/acme/other")
    _submit(h, other, module_id="other")
    rejected = h.admin("reject_manifest", other.id, reason="too wide")
    assert rejected.status == "rejected" and rejected.reason == "too wide"
    assert _submit(h, other, module_id="other").manifest.status == "rejected"
    with pytest.raises(IAMConflictError):
        h.admin(
            "reject_manifest", account.id, h.admin("get_manifest", account.id).sha256
        )


def test_auto_approve_approves_at_submission(h, iam):
    iam.auto_approve = True
    account = _module(h)
    submitted = _submit(h, account)
    assert submitted.manifest.status == "approved" and submitted.approved_now
    assert h.allowed(QUERY, "abi:-:-:triple_store:graph/people-a", account)
    assert not _submit(h, account).approved_now


def test_a_module_submits_only_as_its_own_account(h):
    account = _module(h)
    with pytest.raises(PermissionDeniedError, match="runs as the service account"):
        _submit(h, account, module_id="other")
    with pytest.raises(PermissionDeniedError):
        _submit(h, account, project="beta")
    with pytest.raises(PermissionDeniedError):
        _submit(h, h.service_account("ci/nightly"))


def test_without_a_version_only_a_pending_manifest_is_decided(h):
    account = _module(h)
    _submit(h, account)
    rejected = h.admin("reject_manifest", account.id, reason="no")
    # Nothing waits: a rejected version is decided on only by naming it.
    with pytest.raises(IAMNotFoundError, match="waits for a decision"):
        h.admin("approve_manifest", account.id)
    with pytest.raises(IAMNotFoundError, match="waits for a decision"):
        h.admin("reject_manifest", account.id)
    approved = h.admin("approve_manifest", account.id, rejected.sha256)
    assert approved.status == "approved"


def test_a_superseded_version_submitted_again_waits_for_approval(h):
    account = _module(h)
    first = _submit(h, account).manifest
    h.admin("approve_manifest", account.id)
    wider = document(statement("Allow", ["triple_store:*"], ["*"]))
    _submit(h, account, wider)
    h.admin("approve_manifest", account.id)
    assert h.admin("get_manifest", account.id, first.sha256).status == "superseded"
    # Rolling back to the first version: pending again, the wider one in force.
    again = _submit(h, account)
    assert again.manifest.status == "pending" and again.in_force
    assert [m.sha256 for m in h.admin("list_manifests", status="pending")] == [
        first.sha256
    ]
    assert h.allowed("triple_store:Insert", "abi:-:-:triple_store:graph/x", account)
    assert h.admin("approve_manifest", account.id).sha256 == first.sha256
    assert not h.allowed("triple_store:Insert", "abi:-:-:triple_store:graph/x", account)


def test_approving_needs_the_admin_action(h):
    account = _module(h)
    _submit(h, account)
    with h.as_(account), pytest.raises(PermissionDeniedError):
        h.iam.approve_manifest(account.id)
    assert h.admin("list_manifests", status="pending")[0].principal_id == account.id


def test_unapproved_modules_reach_nothing_but_their_bootstrap(h):
    account = _module(h)
    _submit(h, account)
    assert not h.allowed(
        "document:Find", "abi:-:-:document:collection/people/c", account
    )
    assert not h.allowed(QUERY, "abi:-:-:triple_store:graph/people-a", account)


# -- broker permissions (RFC §8.4) -------------------------------------------------------


def test_broker_permissions_follow_the_approved_policy(h, iam):
    account = _module(h)
    key = h.admin("create_key", account.id).record
    sa = account.id.removeprefix("sa_")
    before = iam.broker_permissions(account, key)
    assert before.inbox_prefix == f"_INBOX.{key.key_id}"
    assert f"_INBOX.{key.key_id}.>" in before.subscribe
    assert "_INBOX.>" not in before.subscribe
    assert f"abi.agent.acme.{sa}.>" in before.subscribe
    assert f"abi.mod.acme.{sa}.>" in before.subscribe
    assert "abi.iam.v1.token" in before.publish
    assert "abi.iam.v1.changed" not in before.publish
    assert "abi.discovery.acme.v1.>" in before.publish
    assert not any(s.startswith("abi.svc.") for s in before.publish)
    assert ">" not in before.publish and ">" not in before.subscribe

    _submit(h, account, document(statement("Allow", ["document:*"], ["*"])))
    h.admin("approve_manifest", account.id)
    after = iam.broker_permissions(account, key)
    assert "abi.svc.document.v1.>" in after.publish
    assert "abi.svc.triple_store.v1.>" not in after.publish


def test_broker_permissions_never_read_a_cached_policy(h, iam):
    account = _module(h)
    key = h.admin("create_key", account.id).record
    _submit(h, account, document(statement("Allow", ["document:*"], ["*"])))
    h.admin("approve_manifest", account.id)
    assert h.allowed("document:Get", "abi:-:-:document:document/x/y", account)
    # Narrowed in the store by another process (abi iam), this one not told.
    policy = iam.store.get_policy("module.acme.people")
    iam.store.put_managed_policy(
        replace(
            policy,
            document=parse_policy_document(
                document(statement("Allow", ["keyvalue:*"], ["abi:*:*:keyvalue:*"]))
            ),
        )
    )
    after = iam.broker_permissions(account, key)
    assert "abi.svc.document.v1.>" not in after.publish
    assert "abi.svc.keyvalue.v1.>" in after.publish


def test_a_manifest_naming_a_platform_topic_is_refused(h):
    account = _module(h)
    wide = document(statement("Allow", ["bus:*"], ["abi:-:-:bus:topic/abi.iam.v1"]))
    with pytest.raises(PolicyValidationError, match="reserved for the platform"):
        _submit(h, account, wide)
    _submit(h, account)
    with pytest.raises(PolicyValidationError, match="reserved for the platform"):
        h.admin("approve_manifest", account.id, document=wide)


def _topic(topic: str):
    return document(statement("Allow", ["bus:*"], [f"abi:-:-:bus:topic/{topic}"]))


def test_a_topic_nested_in_another_modules_approved_topic_is_refused(h):
    orders = _module(h)
    _submit(h, orders, _topic("orders"))
    h.admin("approve_manifest", orders.id)
    eu = _module(h, "module/acme/eu")
    _submit(h, eu, _topic("orders.eu"), module_id="eu")
    with pytest.raises(PolicyValidationError, match="inside approved topic"):
        h.admin("approve_manifest", eu.id)
    # The same topic is shared, fine.
    shared = _module(h, "module/acme/shared")
    _submit(h, shared, _topic("orders"), module_id="shared")
    assert h.admin("approve_manifest", shared.id).status == "approved"


def test_a_forged_change_notice_never_stops_refreshes(iam):
    import asyncio
    from types import SimpleNamespace

    from naas_abi_proto.iam.v1 import iam_pb2 as pb

    from naas_abi_core.services.iam.adapters.primary.iam__primary_adapter__NATS import (
        IAMPrimaryAdapterNATS,
    )

    other = IAMService(iam.store)  # another process writing the same store
    primary = IAMPrimaryAdapterNATS(iam, iam.verifier())
    calls = []
    iam.invalidate = lambda: calls.append(iam.store.revision())  # type: ignore[method-assign]

    def heard(revision: int) -> None:
        msg = SimpleNamespace(
            data=pb.ChangeEvent(revision=revision).SerializeToString()
        )
        asyncio.run(primary._heard_change(msg))

    heard(2**62)  # forged: the store's revision is what counts
    seen = len(calls)
    heard(2**62)
    assert len(calls) == seen  # nothing changed in the store
    with as_service_account("engine"):
        other.create_service_account("ci/after-the-forgery")
    heard(1)  # a real change, whatever the notice says
    assert len(calls) == seen + 1


def test_a_topic_nested_in_a_policy_attached_directly_is_refused_too(h, iam):
    from naas_abi_core.services.iam.IAMPorts import Attachment, Policy, new_id

    ci = h.service_account("ci/feeder")
    iam.store.put_managed_policy(
        Policy(
            id="custom.feeder",
            name="feeder",
            document=parse_policy_document(_topic("orders")),
            managed=True,
        )
    )
    iam.store.attach(Attachment(new_id("att"), "custom.feeder", ci.id))
    eu = _module(h, "module/acme/eu")
    _submit(h, eu, _topic("orders.eu"), module_id="eu")
    with pytest.raises(PolicyValidationError, match="inside approved topic"):
        h.admin("approve_manifest", eu.id)


def test_a_denied_topic_is_no_topic_another_one_nests_in(h):
    orders = _module(h)
    _submit(h, orders, _topic("orders"))
    h.admin("approve_manifest", orders.id)
    denier = _module(h, "module/acme/denier")
    only_deny = document(statement("Deny", ["bus:*"], ["abi:-:-:bus:topic/orders.eu"]))
    _submit(h, denier, only_deny, module_id="denier")
    assert h.admin("approve_manifest", denier.id).status == "approved"


def test_a_trigger_seal_is_the_engines_over_exactly_its_fields(iam):
    fields = ["abi.jobs.p.trigger.a.b", "manual", "0" * 64, []]
    seal = iam.seal_trigger(fields)
    assert iam.trigger_sealed(fields, seal)
    assert not iam.trigger_sealed([*fields[:1], "event", *fields[2:]], seal)
    assert not iam.trigger_sealed(["abi.jobs.p.trigger.a.c", *fields[1:]], seal)
    assert not iam.trigger_sealed(fields, "v1.forged")
    # The key is kept: another engine on the same secrets seals the same.
    other = IAMService(iam.store, secrets=iam.secrets)
    assert other.trigger_sealed(fields, seal)
