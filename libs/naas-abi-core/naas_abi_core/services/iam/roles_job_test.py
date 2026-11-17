"""An engine module's jobs account holds what the platform holds, its own secrets,
and never unchecked SQL; the kernel's own maintenance runs as the engine."""

from __future__ import annotations

import pytest

from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.engine.engine_loaders.EngineJobLoader import (
    ENGINE_IDENTITY,
    job_identity,
)
from naas_abi_core.services.iam import roles
from naas_abi_core.services.iam.adapters.secondary.IAMStoreMemory import IAMStoreMemory
from naas_abi_core.services.iam.IAMService import IAMService
from naas_abi_core.services.iam.kernel_catalogs import register_kernel_catalogs
from naas_abi_core.services.iam.tests.iam_harness import NEXUS, IAMHarness, name_in


@pytest.fixture
def iam() -> IAMService:
    service = IAMService(IAMStoreMemory())
    service.bootstrap()
    register_kernel_catalogs(service)
    service._register_catalog(NEXUS)
    return service


def _allowed(iam: IAMService, account: str, action: str, resource: str) -> bool:
    with as_service_account(account):
        return iam.authorize(action, resource).allowed


def test_job_account_keeps_to_the_platform_and_its_own_secrets(iam):
    h = IAMHarness(iam)
    ws = h.register("ws-9", "org-2")
    account = job_identity(iam, "acme.reports")
    assert account == roles.job_account_name("acme.reports")
    # What the platform holds, and its own secrets.
    for action, resource in (
        ("object_storage:GetObject", "abi:object_storage:object/acme/report.pdf"),
        ("triple_store:Query", "abi:triple_store:graph/default"),
        ("secret:Get", "abi:secret:secret/acme.reports%2FAPI_KEY"),
    ):
        assert _allowed(iam, account, action, resource), (action, resource)
    # Never an organisation's or a workspace's data, another's secrets, nor
    # unchecked SQL.
    for action, resource in (
        ("dataset:QueryUnchecked", "abi:dataset:catalog/-"),
        ("document:Get", name_in(ws, "document:document/hr/salaries/2026")),
        ("object_storage:GetObject", name_in(ws, "object_storage:object/board.pdf")),
        ("triple_store:DropGraph", name_in(ws, "triple_store:graph/crm")),
        ("secret:Get", "abi:secret:secret/OPENAI_API_KEY"),
        ("secret:Get", "abi:secret:secret/other.module%2FAPI_KEY"),
    ):
        assert not _allowed(iam, account, action, resource), (action, resource)


def test_kernel_maintenance_jobs_keep_running_as_the_engine(iam):
    for owner in (
        "naas_abi_core.dataset",
        "naas_abi_core.agent_memory",
        "naas_abi_core.event_archive",
        "naas_abi_core.activity_log",
    ):
        assert job_identity(iam, owner) == ENGINE_IDENTITY
    assert iam.store.find_service_account("job/naas_abi_core.dataset") is None


def test_job_run_for_a_user_keeps_to_the_platform(iam):
    """A run made for a user is decided by the account and the user together: the
    platform's data the user may reach, none of the user's workspaces."""
    from naas_abi_core.engine.call_context import (
        CallContext,
        Principal,
        service_account,
        use_call_context,
    )

    h = IAMHarness(iam)
    ws = h.register("ws-1", "org-1")
    user = h.user("bob")
    h.attach(roles.ADMIN, user.id, ws)
    account = job_identity(iam, "acme.reports")
    for_user = CallContext(
        principal=service_account(account),
        on_behalf_of=Principal(id=user.id, kind="user"),
    )
    own = name_in(ws, "document:document/notes/c/d")
    with use_call_context(for_user):
        assert not iam.authorize("document:Get", own).allowed
    with h.as_(user):
        assert iam.authorize("document:Get", own).allowed
