import asyncio

import pytest
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.in_memory import (
    InMemoryModuleRegistry,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.in_memory_agents import (
    InMemoryAgentControl,
    InMemoryAgentRunStore,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.in_memory_resources import (
    InMemoryAuditLog,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.agents import (
    AgentRunNotCancellable,
    AgentRunNotFound,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.agents_service import AgentsAdminService
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import (
    RemoteModuleInstance,
    SourceUnavailable,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.resources import (
    AdminAction,
    AuditRecord,
    AuditUnavailable,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.tests import fixtures


def _instance(module_id, agents):
    return RemoteModuleInstance(module_id, f"{module_id}-1", "0.1.0", 1, "READY", 1.9e9, agents)


def _service(**overrides):
    values = {
        "registry": InMemoryModuleRegistry(
            [
                _instance("acme.agents", ("Researcher",)),
                _instance("acme.agents", ("Researcher",)),  # a replica
                _instance("acme.other", ("Writer",)),
                _instance("acme.jobs-only", ()),
            ]
        ),
        "runs": InMemoryAgentRunStore(fixtures.agent_runs(), fixtures.agent_events()),
        "control": InMemoryAgentControl(),
        "audit": InMemoryAuditLog(),
        "trace_ui_url": "http://jaeger/",
    }
    values.update(overrides)
    return AgentsAdminService(**values)


def test_lists_runs_of_every_module_that_hosts_agents():
    page = asyncio.run(_service().runs())

    assert [r.run_id for r in page.runs] == ["r4", "r3", "r2", "r1"]
    assert page.next is None
    assert asyncio.run(_service().modules()) == ["acme.agents", "acme.other"]


def test_pages_and_filters_runs():
    service = _service()

    first = asyncio.run(service.runs(limit=2))
    assert [r.run_id for r in first.runs] == ["r4", "r3"] and first.next == first.runs[
        -1
    ].submitted_at
    rest = asyncio.run(service.runs(before=first.next, limit=2))
    assert [r.run_id for r in rest.runs] == ["r2", "r1"]
    assert [r.run_id for r in asyncio.run(service.runs(module="acme.other")).runs] == ["r3"]
    assert [r.run_id for r in asyncio.run(service.runs(statuses=["FAILED"])).runs] == ["r3"]
    assert [r.run_id for r in asyncio.run(service.runs(agent="Writer")).runs] == ["r3"]


def test_a_module_filter_works_without_discovery():
    service = _service(registry=SourceUnavailable("discovery", "NATS mode is off"))

    assert [r.run_id for r in asyncio.run(service.runs(module="acme.other")).runs] == ["r3"]
    with pytest.raises(SourceUnavailable) as raised:
        asyncio.run(service.runs())
    assert raised.value.source == "discovery"


def test_a_run_comes_with_its_events_and_trace_link():
    run, events, trace_url = asyncio.run(_service().run("acme.agents", "r2"))

    assert run.status == "SUCCEEDED" and len(events) == 3
    assert trace_url == f"http://jaeger/trace/{'c' * 32}"
    _, _, no_trace = asyncio.run(_service().run("acme.other", "r3"))
    assert no_trace is None
    with pytest.raises(AgentRunNotFound):
        asyncio.run(_service().run("acme.agents", "r99"))


def test_cancel_only_active_runs_and_audit_it():
    control, audit = InMemoryAgentControl(), InMemoryAuditLog()
    service = _service(control=control, audit=audit)

    asyncio.run(service.cancel("admin-1", "acme.agents", "r4"))

    assert control.cancelled == ["acme.agents/r4"]
    action = AdminAction("admin-1", "agents", "cancel", "acme.agents/r4")
    assert audit.records == [AuditRecord(action, "requested"), AuditRecord(action, "succeeded")]
    with pytest.raises(AgentRunNotCancellable):
        asyncio.run(service.cancel("admin-1", "acme.agents", "r2"))


def test_nothing_is_cancelled_without_an_audit_record():
    control = InMemoryAgentControl()
    service = _service(control=control, audit=InMemoryAuditLog(fail="db down"))

    with pytest.raises(AuditUnavailable):
        asyncio.run(service.cancel("admin-1", "acme.agents", "r4"))
    assert control.cancelled == []


def test_a_failed_cancel_is_audited_and_raised():
    audit = InMemoryAuditLog()
    service = _service(control=InMemoryAgentControl(fail="owner gone"), audit=audit)

    with pytest.raises(SourceUnavailable):
        asyncio.run(service.cancel("admin-1", "acme.agents", "r4"))
    assert [r.phase for r in audit.records] == ["requested", "failed"]
