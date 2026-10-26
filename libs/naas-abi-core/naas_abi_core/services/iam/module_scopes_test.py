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
from naas_abi_core.services.iam.tests.iam_harness import document, statement

WS = "abi:org-1:ws-1"


def _agent(name: str, module: str = "people", workspace: str = "ws-1") -> str:
    return scope_resource("agent", module, name, org="org-1", workspace=workspace)


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
    assert _agent("Market analyst") == (
        "abi:org-1:ws-1:module:agent/people/Market%20analyst"
    )
    assert (
        scope_resource(
            "workflow",
            "naas_abi_marketplace.ai.claude",
            "workflow.sync",
            org="o",
            workspace="w",
        )
        == "abi:o:w:module:workflow/naas_abi_marketplace.ai.claude/workflow.sync"
    )


@pytest.mark.parametrize("role", ["viewer", "member"])
def test_viewers_and_members_hold_no_module_scope(h, role):
    user = _role(h, role, role)
    for type_name, action in module_scopes.USE_ACTION.items():
        resource = scope_resource(
            type_name, "people", "x", org="org-1", workspace="ws-1"
        )
        assert not h.allowed(f"module:{action}", resource, user)


@pytest.mark.parametrize("role", ["admin", "owner"])
def test_admins_and_owners_hold_every_module_scope_at_their_scope(h, role):
    user = _role(h, role, role)
    assert h.allowed("module:UseAgent", _agent("A"), user)
    assert h.allowed(
        "module:RunPipeline",
        scope_resource("pipeline", "p", "pipeline.x", org="org-1", workspace="ws-1"),
        user,
    )
    assert not h.allowed("module:UseAgent", _agent("A", workspace="ws-2"), user)


def test_a_grant_of_one_agent_leaves_the_others_refused(h):
    bob = _role(h, "member", "bob")
    h.grant(
        bob.id,
        statement("Allow", ["module:UseAgent"], ["${scope}:module:agent/people/A"]),
        scope=WS,
    )
    assert h.allowed("module:UseAgent", _agent("A"), bob)
    assert not h.allowed("module:UseAgent", _agent("B"), bob)
    assert not h.allowed("module:UseAgent", _agent("A", workspace="ws-2"), bob)


def test_the_role_policies_mark_no_module_scope_for_viewers_and_members(iam):
    for role in (roles.VIEWER, roles.MEMBER):
        policy = iam.store.get_policy(role)
        assert not any(
            action.startswith("module:")
            for s in policy.document.statements
            for action in s.actions
        )
    admin = iam.store.get_policy(roles.ADMIN)
    assert any("module:UseAgent" in s.actions for s in admin.document.statements)


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
    report = "abi:org-1:ws-1:acme_people:report/q3"
    bob = _role(h, "member", "bob")
    assert not h.allowed("acme_people:ExportReport", report, bob)
    h.grant(
        bob.id,
        statement(
            "Allow", ["acme_people:ExportReport"], ["${scope}:acme_people:report/*"]
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
    # The module's side of its own actions, for the user it acts for.
    bob = _role(h, "admin", "bob")
    report = "abi:org-1:ws-1:acme_people:report/q3"
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
    with as_service_account("engine"):
        iam.put_scope("org-1")
        iam.put_scope("org-1", "ws-1")
        registered = module_scopes.register_module_catalogs(
            iam, [_EngineModule(catalog), _EngineModule(None)]
        )
    assert registered == ["acme_reports"]
    bob = _role(h, "member", "bob")

    def export(workspace="ws-1"):
        ctx = replace(h.context(bob), workspace_id=workspace)
        with use_call_context(ctx):
            module_scopes.require_declared(
                iam, catalog, "ExportReport", "report", ["q3"]
            )

    with pytest.raises(refused):
        export()
    h.grant(
        bob.id,
        statement("Allow", ["acme_reports:ExportReport"], ["${scope}:acme_reports:*"]),
        scope=WS,
    )
    export()
    with pytest.raises(refused):
        export("ws-2")
