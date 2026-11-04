"""Module scopes: zero trust for viewers and members, grants per item, declared catalogs."""

from __future__ import annotations

import pytest

from naas_abi_core.engine.call_context import use_call_context
from naas_abi_core.services.iam import module_scopes, roles
from naas_abi_core.services.iam.catalog import ActionCatalog
from naas_abi_core.services.iam.IAMPorts import IAMConflictError
from naas_abi_core.services.iam.module_scopes import (
    ModuleCatalogError,
    module_catalog,
    module_service,
    scope_resource,
)
from naas_abi_core.services.iam.tests.iam_harness import (
    document,
    statement,
    workspace,
)

WS = workspace("ws-1")


def _agent(name: str, module: str = "people", ws: str = "ws-1") -> str:
    return scope_resource("agent", module, name, container=workspace(ws))


@pytest.fixture
def iam(iam):
    iam._register_catalog(module_scopes.CATALOG)
    return iam


def _role(h, role: str, subject: str):
    user = h.user(subject)
    h.attach(f"builtin.{role}", user.id, WS)
    return user


DECLARED = {
    "version": 1,
    "resource_types": [{"name": "report", "id": "path"}],
    "actions": [
        {"name": "ExportReport", "level": "read", "resource_types": ["report"]}
    ],
}


def test_a_scope_names_the_workspace_module_and_item():
    assert _agent("Market analyst") == (WS + "/module:agent/people/Market%20analyst")
    assert (
        scope_resource(
            "workflow",
            "naas_abi_marketplace.applications.github",
            "workflow.sync",
            container=workspace("w", "o"),
        )
        == workspace("w", "o")
        + "/module:workflow/naas_abi_marketplace.applications.github/workflow.sync"
    )
    # Without a container, the platform's.
    assert scope_resource("app", "people", "web") == "abi:module:app/people/web"


@pytest.mark.parametrize("role", ["viewer", "member", "admin", "owner"])
def test_no_role_holds_a_module_scope(h, role):
    """Zero trust: owners and admins included, a policy grants each one."""
    user = _role(h, role, role)
    for type_name, action in module_scopes.USE_ACTION.items():
        resource = scope_resource(type_name, "people", "x", container=WS)
        assert not h.allowed(f"module:{action}", resource, user)
    h.grant(
        user.id,
        statement("Allow", ["module:UseAgent"], ["${scope}/module:agent/*"]),
        scope=WS,
    )
    assert h.allowed("module:UseAgent", _agent("A"), user)
    assert not h.allowed("module:UseAgent", _agent("A", ws="ws-2"), user)


def test_a_grant_of_one_agent_leaves_the_others_refused(h):
    bob = _role(h, "member", "bob")
    h.grant(
        bob.id,
        statement("Allow", ["module:UseAgent"], ["${scope}/module:agent/people/A"]),
        scope=WS,
    )
    assert h.allowed("module:UseAgent", _agent("A"), bob)
    assert not h.allowed("module:UseAgent", _agent("B"), bob)
    assert not h.allowed("module:UseAgent", _agent("A", ws="ws-2"), bob)


def test_the_role_policies_name_no_module_scope(iam):
    for role in roles.ROLES:
        policy = iam.store.get_policy(role)
        assert not any(
            action.startswith("module:")
            or "/module:" in resource
            or resource.startswith("abi:module:")
            for s in policy.document.statements
            for action in s.actions
            for resource in s.resources
        )


def test_a_module_service_is_its_identifier_as_a_catalog_name():
    assert module_service("acme.people") == "acme_people"
    assert module_service("Acme-People") == "acme_people"
    assert module_service("9lives") == "m_9lives"


def test_a_declared_catalog_is_the_module_s_own_and_a_module_scope():
    catalog = module_catalog(DECLARED, "acme.people")
    assert catalog.service == "acme_people" and catalog.module == "acme.people"
    assert all(t.module_scope for t in catalog.resource_types)


@pytest.mark.parametrize(
    "service", ["triple_store", "nexus", "module", "iam", "discovery", "other_mod"]
)
def test_a_declared_catalog_naming_another_service_is_refused(service):
    with pytest.raises(ModuleCatalogError):
        module_catalog({**DECLARED, "service": service}, "acme.people")


def test_a_declared_catalog_cannot_be_placed_on_the_platform():
    platform = {
        **DECLARED,
        "resource_types": [{"name": "report", "placement": "platform"}],
    }
    with pytest.raises(ModuleCatalogError):
        module_catalog(platform, "acme.people")


def test_another_module_cannot_take_a_registered_catalog(h, iam):
    iam._register_catalog(module_catalog(DECLARED, "acme.people"))
    with pytest.raises(IAMConflictError):
        iam._register_catalog(module_catalog(DECLARED, "acme-people"))
    with pytest.raises(IAMConflictError):
        iam._register_catalog(
            ActionCatalog.from_dict({**DECLARED, "service": "acme_people"})
        )


def test_declared_actions_are_refused_without_a_grant_and_allowed_with_one(h, iam):
    iam._register_catalog(module_catalog(DECLARED, "acme.people"))
    report = WS + "/acme_people:report/q3"
    bob = _role(h, "member", "bob")
    assert not h.allowed("acme_people:ExportReport", report, bob)
    h.grant(
        bob.id,
        statement(
            "Allow", ["acme_people:ExportReport"], ["${scope}/acme_people:report/*"]
        ),
        scope=WS,
    )
    assert h.allowed("acme_people:ExportReport", report, bob)
    # Nexus checks it as api for the user: api holds every declared action.
    assert h.allowed("acme_people:ExportReport", report, actor="api", on_behalf_of=bob)


def test_a_manifest_carries_its_catalog_and_approval_registers_it(h, iam):
    account = h.service_account("module/acme/acme.people")
    manifest = {
        **document(statement("Allow", ["triple_store:Query"], ["*"])),
        "catalog": DECLARED,
    }
    with h.as_(account):
        submitted = iam.submit_manifest("acme.people", "acme", manifest)
    assert submitted.manifest.status == "pending"
    assert iam.catalogs.get("acme_people") is None
    h.admin("approve_manifest", account.id)
    assert iam.catalogs.get("acme_people").module == "acme.people"
    # The module's side of its own actions, for the user it acts for, who
    # holds them through a policy (no role does).
    bob = _role(h, "admin", "bob")
    h.grant(
        bob.id,
        statement("Allow", ["acme_people:*"], ["${scope}/acme_people:*"]),
        scope=WS,
    )
    report = WS + "/acme_people:report/q3"
    assert h.allowed("acme_people:ExportReport", report, account, on_behalf_of=bob)
    stranger = h.user("stranger")
    assert not h.allowed(
        "acme_people:ExportReport", report, account, on_behalf_of=stranger
    )
    # A changed catalog is a new version, waiting for approval.
    changed = {**manifest, "catalog": {**DECLARED, "version": 2}}
    with h.as_(account):
        again = iam.submit_manifest("acme.people", "acme", changed)
    assert again.manifest.status == "pending"


def test_a_manifest_declaring_a_reserved_catalog_is_refused(h, iam):
    account = h.service_account("module/acme/people")
    manifest = {
        **document(statement("Allow", ["triple_store:Query"], ["*"])),
        "catalog": {**DECLARED, "service": "triple_store"},
    }
    with h.as_(account), pytest.raises(ModuleCatalogError):
        iam.submit_manifest("people", "acme", manifest)


def test_a_manifest_naming_another_module_s_catalog_is_refused(h, iam):
    iam._register_catalog(module_catalog(DECLARED, "people"))
    account = h.service_account("module/acme/people-2")
    manifest = {
        **document(statement("Allow", ["triple_store:Query"], ["*"])),
        "catalog": {**DECLARED, "service": "people"},
    }
    with h.as_(account), pytest.raises(ModuleCatalogError):
        iam.submit_manifest("people-2", "acme", manifest)


class _EngineModule:
    def __init__(self, catalog):
        self.iam_catalog = catalog


def test_an_engine_module_s_catalog_is_registered_at_load_and_enforced(
    h, iam, tmp_path
):
    from dataclasses import replace

    from naas_abi_core.engine.call_context import as_service_account
    from naas_abi_core.services.iam.IAMPorts import (
        PermissionDeniedError,
        ResourceNotFoundError,
    )

    refused = (PermissionDeniedError, ResourceNotFoundError)

    (tmp_path / module_scopes.CATALOG_FILE).write_text(
        "version: 1\n"
        "resource_types:\n  - {name: report, id: path}\n"
        "actions:\n  - {name: ExportReport, level: read, resource_types: [report]}\n"
    )
    catalog = module_scopes.load_module_catalog(tmp_path, "acme.reports")
    assert module_scopes.load_module_catalog(tmp_path / "none", "x") is None
    h.register("ws-1"), h.register("ws-2")
    with as_service_account("engine"):
        registered = module_scopes.register_module_catalogs(
            iam, [_EngineModule(catalog), _EngineModule(None)]
        )
    assert registered == ["acme_reports"]
    bob = _role(h, "member", "bob")

    def export(ws="ws-1"):
        ctx = replace(h.context(bob), container=workspace(ws))
        with use_call_context(ctx):
            iam.require_declared("acme_reports:ExportReport", "report", ["q3"])

    with pytest.raises(refused):
        export()
    h.grant(
        bob.id,
        statement("Allow", ["acme_reports:ExportReport"], ["${scope}/acme_reports:*"]),
        scope=WS,
    )
    export()
    with pytest.raises(refused):
        export("ws-2")
    # A container IAM does not know names nothing: not found.
    with pytest.raises(ResourceNotFoundError):
        export("ws-9")


def test_members_reach_a_module_s_workflows_at_the_broker_never_its_jobs(h, iam):
    """Which workflow a member starts is its module scope's (Nexus checks it
    first): the broker's own check lets a member trigger a workflow, by its
    ``workflow/…`` name, never a plain job; a viewer neither."""
    from naas_abi_core.services.discovery.iam_catalog import CATALOG as DISCOVERY

    iam._register_catalog(DISCOVERY)
    flow = "abi:discovery:workflow/default/acme.flows/workflow.ingest"
    job = "abi:discovery:job/default/acme.flows/workflow.ingest"
    member, viewer = _role(h, "member", "m"), _role(h, "viewer", "v")
    assert h.allowed("discovery:TriggerJob", flow, member)
    assert not h.allowed("discovery:TriggerJob", job, member)
    assert not h.allowed("discovery:TriggerJob", flow, viewer)
    assert not h.allowed("discovery:ListJobs", job, viewer)


def test_a_refused_engine_catalog_is_skipped_never_stops_the_load(h, iam):
    """Another module's service is a conflict: logged and skipped, the other
    modules' catalogs registered (and the refused one's checks fail closed)."""
    from naas_abi_core.engine.call_context import as_service_account

    iam._register_catalog(module_catalog(DECLARED, "acme.people"))
    taken = module_catalog(DECLARED, "acme-people")  # also acme_people
    other = module_catalog(DECLARED, "acme.reports")
    with as_service_account("engine"):
        registered = module_scopes.register_module_catalogs(
            iam, [_EngineModule(taken), _EngineModule(other)]
        )
    assert registered == ["acme_reports"]
    assert iam.catalogs.get("acme_people").module == "acme.people"


def test_a_malformed_catalog_file_leaves_the_module_without_one(tmp_path):
    (tmp_path / module_scopes.CATALOG_FILE).write_text(
        "resource_types:\n  - {name: report, placement: platform}\nactions: []\n"
    )
    with pytest.raises(ModuleCatalogError):
        module_scopes.load_module_catalog(tmp_path, "acme.reports")
    assert module_scopes.declared_catalog(tmp_path, "acme.reports") is None
    (tmp_path / module_scopes.CATALOG_FILE).write_text(": not yaml: [")
    assert module_scopes.declared_catalog(tmp_path, "acme.reports") is None


def test_one_module_id_declares_a_catalog_in_one_project_only(h, iam):
    """The service comes from the module id: the same id in another project
    would replace the first's catalog, so its declaring manifest is refused."""
    manifest = {
        **document(statement("Allow", ["triple_store:Query"], ["*"])),
        "catalog": DECLARED,
    }
    first = h.service_account("module/acme/acme.people")
    with h.as_(first):
        iam.submit_manifest("acme.people", "acme", manifest)
    h.admin("approve_manifest", first.id)
    second = h.service_account("module/other/acme.people")
    with h.as_(second), pytest.raises(IAMConflictError):
        iam.submit_manifest("acme.people", "other", manifest)
    # Without a catalog, the other project's module is as before.
    with h.as_(second):
        plain = iam.submit_manifest(
            "acme.people", "other", document(*manifest["statements"])
        )
    assert plain.manifest.status == "pending"


# -- declared actions in the container of the call ----------------------------------

CONTAINERS = {
    "version": 1,
    "resource_types": [
        {"name": "project", "container": True},
        {"name": "deal", "id": "opaque"},
    ],
    "actions": [
        {
            "name": "CreateProject",
            "level": "write",
            "resource_types": ["project"],
            "creates": True,
        },
        {"name": "OpenProject", "level": "read", "resource_types": ["project"]},
        {"name": "GetDeal", "level": "read", "resource_types": ["deal"]},
    ],
}


@pytest.fixture
def crm(h, iam):
    """A module's catalog declaring a container, ``project``, registered in
    ws-1 as p-9 (by api, which holds every module's own catalog)."""
    from naas_abi_core.engine.call_context import as_service_account

    iam._register_catalog(module_catalog(CONTAINERS, "acme.crm"))
    h.register("ws-1"), h.register("ws-2")
    with as_service_account("api"):
        record = iam.register_container("acme_crm", "project", "p-9", parent=WS)
    return record.name


def _inside(h, record, container):
    from dataclasses import replace

    return use_call_context(replace(h.context(record), container=container))


def test_a_declared_action_is_named_in_the_container_of_the_call(h, iam, crm):
    bob = _role(h, "member", "bob")
    h.grant(
        bob.id,
        statement("Allow", ["acme_crm:GetDeal"], ["${scope}/acme_crm:deal/*"]),
        scope=crm,
    )
    with _inside(h, bob, crm):
        decision, resource = iam.authorize_declared("acme_crm:GetDeal", "deal", ["d-1"])
    assert resource == crm + "/acme_crm:deal/d-1"
    assert decision.allowed
    # In the workspace the project sits in, the deal is the workspace's: the
    # grant at the project does not reach it.
    with _inside(h, bob, WS):
        decision, resource = iam.authorize_declared("acme_crm:GetDeal", "deal", ["d-1"])
    assert resource == WS + "/acme_crm:deal/d-1"
    assert not decision.allowed
    # ``container=`` names it whatever the call's is.
    with _inside(h, bob, WS):
        iam.require_declared("acme_crm:GetDeal", "deal", ["d-1"], container=crm)
    # Without a container, at the platform.
    with h.as_(bob):
        decision, resource = iam.authorize_declared("acme_crm:GetDeal", "deal", ["d-1"])
    assert resource == "abi:acme_crm:deal/d-1" and not decision.allowed


def test_a_container_iam_does_not_know_names_nothing(h, iam, crm):
    from naas_abi_core.services.iam.IAMPorts import ResourceNotFoundError

    bob = _role(h, "member", "bob")
    h.grant(bob.id, statement("Allow", ["acme_crm:GetDeal"], ["*"]))
    unknown = workspace("ws-9")
    # Under another path than its registered one, a container is unknown too.
    moved = workspace("ws-1", "org-2")
    for claimed in (unknown, moved, "abi:not a container"):
        with _inside(h, bob, claimed):
            decision, _resource = iam.authorize_declared(
                "acme_crm:GetDeal", "deal", ["d-1"]
            )
            assert (decision.allowed, decision.visible) == (False, False)
            with pytest.raises(ResourceNotFoundError):
                iam.require_declared("acme_crm:GetDeal", "deal", ["d-1"])
        with h.as_(bob), pytest.raises(ResourceNotFoundError):
            iam.require_declared("acme_crm:GetDeal", "deal", ["d-1"], container=claimed)


def test_a_declared_container_type_s_own_resource_is_the_registered_container(
    h, iam, crm
):
    bob = _role(h, "member", "bob")
    h.grant(
        bob.id,
        statement("Allow", ["acme_crm:OpenProject"], ["${scope}/acme_crm:project/*"]),
        scope=WS,
    )
    # Wherever the call is made, the project is where it was registered.
    for claimed in (None, WS, workspace("ws-2")):
        with _inside(h, bob, claimed):
            decision, resource = iam.authorize_declared(
                "acme_crm:OpenProject", "project", ["p-9"]
            )
        assert resource == crm
        assert decision.allowed
    # A project nobody registered is not found.
    with _inside(h, bob, WS):
        decision, resource = iam.authorize_declared(
            "acme_crm:OpenProject", "project", ["p-10"]
        )
    assert resource == WS + "/acme_crm:project/p-10"
    assert (decision.allowed, decision.visible) == (False, False)
    # A container's id is one value: several parts name no container, denied.
    with _inside(h, bob, WS):
        decision, resource = iam.authorize_declared(
            "acme_crm:OpenProject", "project", ["p-9", "x"]
        )
    assert resource == WS + "/acme_crm:project/p-9%2Fx"
    assert (decision.allowed, decision.visible) == (False, False)
