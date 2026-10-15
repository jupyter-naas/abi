import asyncio

import pytest
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.document_job_runs import (
    DocumentJobRunStore,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.contracts import JobRunStoreContract
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import SourceUnavailable
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.tests import fixtures
from naas_abi_core.services.document.adapters.secondary.DocumentSecondaryAdapterSQLite import (
    DocumentSecondaryAdapterSQLite,
)
from naas_abi_core.services.document.DocumentPort import CollectionSpec
from naas_abi_core.services.document.DocumentService import DocumentService
from naas_abi_sdk.jobs import runs_collection

PROJECT = "zen"


def _as_written(run):
    """The record a job host writes for ``run`` (job_host._handle_delivery)."""
    data = {
        "job": run.job,
        "run_id": run.run_id,
        "module_id": run.module_id,
        "status": run.status,
        "attempt": run.attempt,
        "max_attempts": run.max_attempts,
        "trigger": {"kind": run.trigger.kind}
        | ({"scheduler": run.trigger.scheduler} if run.trigger.scheduler else {}),
        "payload": run.payload,
        "instance": run.instance,
        "fired_at": run.fired_at,
        "started_at": run.started_at,
        "trace_id": run.trace_id,
        "error": run.error,
        "logs": list(run.logs),
    }
    if run.finished_at:
        data["finished_at"] = run.finished_at
    if run.result is not None:
        data["result"] = run.result
    return data


@pytest.fixture
def root(tmp_path):
    backend = DocumentSecondaryAdapterSQLite(str(tmp_path / "documents.sqlite"))
    yield DocumentService._for_engine(backend)


def _seed(root):
    for run in fixtures.job_runs():
        view = root.for_namespace(run.module_id)
        view.ensure_collection(CollectionSpec(name=runs_collection(PROJECT)))
        view.put(runs_collection(PROJECT), run.run_id, _as_written(run))
    return root


class TestDocumentJobRunStore(JobRunStoreContract):
    @pytest.fixture
    def store(self, root):
        _seed(root)
        return DocumentJobRunStore(lambda: root, PROJECT)


def test_a_module_without_runs_has_none(root):
    store = DocumentJobRunStore(lambda: root, PROJECT)

    assert asyncio.run(store.list_runs(["acme.jobs"])) == []
    assert asyncio.run(store.running("acme.jobs")) == []


def test_runs_of_another_project_are_not_listed(root):
    _seed(root)
    store = DocumentJobRunStore(lambda: root, "other-project")

    assert asyncio.run(store.list_runs(["acme.jobs", "acme.other"])) == []


def test_backend_errors_make_the_source_unavailable():
    def broken():
        raise RuntimeError("document service down")

    with pytest.raises(SourceUnavailable) as exc:
        asyncio.run(DocumentJobRunStore(broken, PROJECT).list_runs(["acme.jobs"]))
    assert exc.value.source == "runs"
