"""A module id names one module of the platform.

A module's own namespaces (document namespace, secret prefix, checkpoint scope,
schema sources) are named by its module id. The id is held by one account: the
first of another project's is refused and holds nothing, and so does an account
of an id the core reserves or an engine module has.
"""

from __future__ import annotations

import pytest
from naas_abi_sdk.module import ModuleDependencies
from naas_abi_sdk.permissions import default_manifest

from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.services.document.iam_catalog import CATALOG as DOCUMENT
from naas_abi_core.services.iam import modules, roles
from naas_abi_core.services.iam.IAMPorts import IAMConflictError
from naas_abi_core.services.iam.policy import parse_policy_document
from naas_abi_core.services.iam.tests.iam_harness import document, statement

PUT = "document:Put"
GET = "document:Get"


@pytest.fixture
def iam(iam):
    iam._register_catalog(DOCUMENT)
    return iam


def _documents_manifest() -> dict:
    return default_manifest(ModuleDependencies(services=("document",)))


def _approved(h, iam, project: str, module_id: str):
    account = h.service_account(f"module/{project}/{module_id}")
    with h.as_(account):
        iam.submit_manifest(module_id, project, _documents_manifest())
    h.admin("approve_manifest", account.id)
    return account


def _bound_policy(h, iam, account, project: str, module_id: str) -> None:
    """The default manifest attached as an approval would, without the approval."""
    bound = modules.bind(
        parse_policy_document(_documents_manifest()), project, module_id
    )
    with as_service_account("engine"):
        policy = iam.create_policy(f"bound-{project}-{module_id}", bound)
        iam.attach_policy(policy.id, account.id)


def test_module_id_keeps_its_namespaces_to_one_account(h, iam):
    acme = _approved(h, iam, "acme", "sales")
    record = "abi:document:document/sales/deals/d1"
    assert h.allowed(GET, record, acme)

    second = h.service_account("module/beta/sales")
    with h.as_(second), pytest.raises(IAMConflictError, match="held by"):
        iam.submit_manifest("sales", "beta", _documents_manifest())
    # Even with the module's policy attached, the second account holds nothing.
    _bound_policy(h, iam, second, "beta", "sales")
    assert not h.allowed(GET, record, second)
    assert not h.allowed(PUT, record, second)
    assert not h.allowed(GET, "abi:document:document/other/c/d", second)
    # The first account keeps it.
    assert h.allowed(PUT, record, acme)


def test_module_id_is_freed_when_its_account_is_deleted(h, iam):
    acme = _approved(h, iam, "acme", "sales")
    h.admin("delete_principal", acme.id)
    other = _approved(h, iam, "other", "sales")
    assert h.allowed(GET, "abi:document:document/sales/deals/d1", other)


@pytest.mark.parametrize(
    "module_id",
    ["naas_abi_core.services.agent", "naas_abi_core.services.activity_log", "default"],
)
def test_module_id_keeps_core_namespaces_out_of_reach(h, iam, module_id):
    account = h.service_account(f"module/beta/{module_id}")
    with h.as_(account), pytest.raises(IAMConflictError, match="reserved"):
        iam.submit_manifest(module_id, "beta", _documents_manifest())
    _bound_policy(h, iam, account, "beta", module_id)
    assert not h.allowed(PUT, f"abi:document:document/{module_id}/c/x", account)


def test_module_id_of_an_engine_module_holds_nothing_remotely(h, iam):
    h.service_account(roles.job_account_name("acme.ingest"))
    account = h.service_account("module/acme/acme.ingest")
    with h.as_(account), pytest.raises(IAMConflictError, match="engine module"):
        iam.submit_manifest("acme.ingest", "acme", _documents_manifest())
    _bound_policy(h, iam, account, "acme", "acme.ingest")
    assert not h.allowed(PUT, "abi:document:document/acme.ingest/runs/r1", account)


@pytest.mark.parametrize(
    "namespace", ["naas_abi_core.services.agent", "naas_abi_core.services.activity_log"]
)
def test_core_document_namespaces_keep_to_the_engine(h, iam, namespace):
    """Sealed: no policy opens them, wherever they are placed."""
    account = h.service_account("module/acme/wide")
    h.grant(account.id, statement("Allow", ["document:*"], ["*"]))
    for resource in (
        f"abi:document:namespace/{namespace}",
        f"abi:document:collection/{namespace}/checkpoints",
        f"abi:document:document/{namespace}/checkpoints/x",
        f"abi:nexus:workspace/ws-1/document:document/{namespace}/checkpoints/x",
    ):
        assert not h.allowed(PUT, resource, account), resource
    with as_service_account("engine"):
        assert iam.authorize(
            PUT, f"abi:document:document/{namespace}/checkpoints/x"
        ).allowed


def test_module_dataset_namespace_keeps_project_and_id_apart():
    names = {
        modules.dataset_namespace(project, module_id)
        for project, module_id in (
            ("acme", "crm"),
            ("beta", "crm"),
            ("acme", "acme.crm"),
            ("acme", "acme_crm"),
        )
    }
    assert len(names) == 4
    for name in names:
        assert name.startswith("m_") and name.replace("_", "").isalnum()
    assert modules.variables("module/acme/crm")[
        "module.dataset_namespace"
    ] == modules.dataset_namespace("acme", "crm")


def test_a_manifest_naming_another_namespace_is_its_own_choice(h, iam):
    """What the uniqueness keeps is the module's own namespaces: a written
    manifest may still ask for more, which the admin then sees."""
    account = h.service_account("module/acme/reader")
    with h.as_(account):
        iam.submit_manifest(
            "reader",
            "acme",
            document(statement("Allow", [GET], ["abi:document:document/shared/*"])),
        )
    h.admin("approve_manifest", account.id)
    assert h.allowed(GET, "abi:document:document/shared/c/d", account)


def test_module_id_holder_keeps_its_lookup_to_one_scan(h, iam, monkeypatch):
    """Each IAM write clears the subjects: the holder of a module id is found by
    one scan, then by its id, until it is deleted."""
    acme = _approved(h, iam, "acme", "sales")
    scans: list[str] = []
    listing = iam.store.list_principals

    def counted(*args, **kwargs):
        scans.append(kwargs.get("text") or "")
        return listing(*args, **kwargs)

    monkeypatch.setattr(iam.store, "list_principals", counted)
    record = "abi:document:document/sales/deals/d1"
    for name in ("a", "b", "c"):
        h.user(name)  # an IAM write: every subject is computed again
        assert h.allowed(GET, record, acme)
    assert len(scans) <= 1
