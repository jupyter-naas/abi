import asyncio
from dataclasses import replace

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


def test_module_runs_keeps_the_last_skip_apart_from_recent_runs(root):
    _seed(root)
    nightly = fixtures.job_runs()[1]
    view = root.for_namespace("acme.jobs")
    for i in range(3):
        skip = replace(
            nightly,
            run_id=f"nightly:skip{i}",
            status="SKIPPED",
            started_at=f"2026-10-02T0{7 + i}:00:00+00:00",
        )
        view.put(runs_collection(PROJECT), skip.run_id, _as_written(skip))
    store = DocumentJobRunStore(lambda: root, PROJECT)

    found = asyncio.run(store.module_runs("acme.jobs", ["nightly"], recent=1)).jobs["nightly"]

    assert [r.run_id for r in found.recent] == ["nightly:3"]
    assert found.last_skipped is not None and found.last_skipped.run_id == "nightly:skip2"


def test_module_runs_reads_one_namespace_view_on_the_store_threads(root):
    import threading

    _seed(root)
    views: list[str] = []
    threads: set[str] = set()

    def documents():
        threads.add(threading.current_thread().name)
        return root

    store = DocumentJobRunStore(documents, PROJECT)
    original = root.for_namespace

    def for_namespace(namespace):
        views.append(namespace)
        return original(namespace)

    root.for_namespace = for_namespace  # type: ignore[method-assign]
    asyncio.run(store.module_runs("acme.jobs", ["nightly", "sync"]))

    assert views == ["acme.jobs"]
    assert all(name.startswith("job-runs") for name in threads)
