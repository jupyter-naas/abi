"""The Document Service agent run store, seeded the way SDK agent hosts write."""

import asyncio

import pytest
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.document_agent_runs import (
    DocumentAgentRunStore,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.contracts import AgentRunStoreContract
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import SourceUnavailable
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.tests import fixtures
from naas_abi_core.services.document.adapters.secondary.DocumentSecondaryAdapterSQLite import (
    DocumentSecondaryAdapterSQLite,
)
from naas_abi_core.services.document.DocumentPort import CollectionSpec
from naas_abi_core.services.document.DocumentService import DocumentService
from naas_abi_sdk.agent_host import agent_events_collection, agent_runs_collection

PROJECT = "zen"
FRAGMENT = 8192  # agent_host._store_output


def _as_written(run):
    """The record an SDK agent host keeps for ``run`` (agent_host._submit/_save)."""
    data = {
        "agent_name": run.agent,
        "invocation_id": run.invocation_id,
        "thread_id": run.thread_id,
        "caller": run.caller,
        "fingerprint": "f" * 64,
        "owner": run.owner,
        "status": run.status,
        "events": [],
        "output_format": 2,
        "last_sequence": run.events,
        "result_parts": 0,
        "result": "",
        "error_code": run.error_code,
        "error_message": run.error_message,
        "submitted_at": run.submitted_at,
        "trace_id": run.trace_id,
    }
    if run.finished_at:
        data["finished_at"] = run.finished_at
    return data


def _seed(root):
    runs, events = agent_runs_collection(PROJECT), agent_events_collection(PROJECT)
    for run in fixtures.agent_runs():
        view = root.for_namespace(run.module_id)
        view.ensure_collection(CollectionSpec(name=runs))
        view.ensure_collection(CollectionSpec(name=events))
        view.put(runs, run.run_id, _as_written(run))
    for (module_id, run_id), emitted in fixtures.agent_events().items():
        view = root.for_namespace(module_id)
        for sequence, (event, text) in enumerate(emitted, 1):
            payload = text.encode()
            parts = max(1, -(-len(payload) // FRAGMENT))
            for part in range(parts):
                chunk = payload[part * FRAGMENT : (part + 1) * FRAGMENT]
                view.put(events, f"{run_id}:{sequence}:{part}", {"data": chunk})
            view.put(events, f"{run_id}:{sequence}", {"event": event, "parts": parts})
    return root


@pytest.fixture
def root(tmp_path):
    backend = DocumentSecondaryAdapterSQLite(str(tmp_path / "documents.sqlite"))
    yield DocumentService._for_engine(backend)


class TestDocumentAgentRunStore(AgentRunStoreContract):
    @pytest.fixture
    def store(self, root):
        _seed(root)
        return DocumentAgentRunStore(lambda: root, PROJECT)


def test_runs_of_another_project_are_not_listed(root):
    _seed(root)
    store = DocumentAgentRunStore(lambda: root, "other-project")

    assert asyncio.run(store.list_runs(["acme.agents", "acme.other"])) == []


def test_an_uncommitted_event_ends_the_list(root):
    _seed(root)
    store = DocumentAgentRunStore(lambda: root, PROJECT)
    view = root.for_namespace("acme.agents")
    view.delete(agent_events_collection(PROJECT), "r2:2")

    assert [e.sequence for e in asyncio.run(store.events("acme.agents", "r2"))] == [1]


def test_backend_errors_make_the_source_unavailable():
    def broken():
        raise RuntimeError("document service down")

    with pytest.raises(SourceUnavailable) as exc:
        asyncio.run(DocumentAgentRunStore(broken, PROJECT).list_runs(["acme.agents"]))
    assert exc.value.source == "agent_runs"
