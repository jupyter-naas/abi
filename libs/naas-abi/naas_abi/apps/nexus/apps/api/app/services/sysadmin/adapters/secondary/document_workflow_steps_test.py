import asyncio

import pytest
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.document_workflow_steps import (
    DocumentWorkflowSteps,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.jobs import ChildRun
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import SourceUnavailable
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.tests import fixtures
from naas_abi_core.services.document.adapters.secondary.DocumentSecondaryAdapterSQLite import (
    DocumentSecondaryAdapterSQLite,
)
from naas_abi_core.services.document.DocumentPort import CollectionSpec, FieldSpec
from naas_abi_core.services.document.DocumentService import DocumentService
from naas_abi_sdk.workflows import steps_collection

PROJECT = "zen"
FIRED = "2026-10-02T11:00:00+00:00"


def _as_journaled(run_id, step, fired_at=FIRED):
    """The summary document the SDK's StepJournal writes."""
    data = {
        "run_id": run_id,
        "key": step.key,
        "kind": step.kind,
        "status": step.status,
        "attempt": step.attempt,
        "started_at": step.started_at,
        "finished_at": step.finished_at or "",
        "duration_ms": step.duration_ms or 0,
        "error": step.error,
        "fired_at": fired_at,
    }
    if step.child:
        data["child"] = {
            "module_id": step.child.module_id,
            "workflow": step.child.workflow,
            "run_id": step.child.run_id,
        }
    if step.result_bytes is not None:
        data["result_bytes"] = step.result_bytes
    return data


@pytest.fixture
def root(tmp_path):
    yield DocumentService._for_engine(DocumentSecondaryAdapterSQLite(str(tmp_path / "d.sqlite")))


def _seed(root, project=PROJECT):
    for (module_id, run_id), detail in fixtures.workflow_steps().items():
        view = root.for_namespace(module_id)
        view.ensure_collection(
            CollectionSpec(
                name=steps_collection(project),
                fields=(FieldSpec(name="run_id", type="string", indexed=True),),
            )
        )
        for step in detail.steps:
            view.put(steps_collection(project), f"{run_id}#{step.key}", _as_journaled(run_id, step))
    return root


def _journal(root, run_id, fired_at=None, project=PROJECT):
    return asyncio.run(
        DocumentWorkflowSteps(lambda: root, project).journal("acme.flows", run_id, fired_at)
    )


def test_reads_a_runs_steps_in_start_order_with_children(root):
    steps = _journal(_seed(root), "ingest:5").steps

    assert [s.key for s in steps] == ["fetch", "map[0]", "map[1]"]
    fetch, ok, failed = steps
    assert (fetch.kind, fetch.status, fetch.attempt, fetch.duration_ms) == (
        "step",
        "SUCCEEDED",
        2,
        2000,
    )
    assert fetch.child is None and fetch.result_bytes == 64
    assert ok.child == ChildRun("acme.flows", "map_item", "map_item:1")
    assert failed.status == "FAILED" and failed.error.startswith("ChildRunFailed")


def test_a_step_still_running_has_no_end_or_duration(root):
    (step,) = _journal(_seed(root), "ingest:6").steps

    assert (step.status, step.finished_at, step.duration_ms) == ("RUNNING", None, None)


def test_a_run_has_only_its_own_steps(root):
    _seed(root)

    assert [s.key for s in _journal(root, "ingest:6").steps] == ["fetch"]
    assert _journal(root, "ingest:99").steps == ()


def test_steps_of_another_trigger_that_reused_the_run_id_are_left_out(root):
    _seed(root)
    old = fixtures.workflow_steps()[("acme.flows", "ingest:6")].steps[0]
    root.for_namespace("acme.flows").put(
        steps_collection(PROJECT),
        "ingest:6#stale",
        _as_journaled("ingest:6", old, fired_at="2026-01-01T00:00:00+00:00") | {"key": "stale"},
    )

    both = _journal(root, "ingest:6")
    mine = _journal(root, "ingest:6", fired_at="2026-10-02T11:00:00+00:00")

    assert {s.key for s in both.steps} == {"fetch", "stale"}
    assert {s.key for s in mine.steps} == {"fetch"}


@pytest.mark.parametrize(
    "bad",
    [{"attempt": "two"}, {"attempt": [1]}],
)
def test_a_step_summary_that_cannot_be_read_is_skipped_not_fatal(root, bad):
    _seed(root)
    good = fixtures.workflow_steps()[("acme.flows", "ingest:6")].steps[0]
    broken = _as_journaled("ingest:6", good) | {
        "key": "broken",
        "status": "SUCCEEDED",
        "finished_at": "2026-10-02T12:00:02+00:00",
    }
    root.for_namespace("acme.flows").put(steps_collection(PROJECT), "ingest:6#broken", broken | bad)

    assert [s.key for s in _journal(root, "ingest:6").steps] == ["fetch"]


def test_a_duration_or_size_that_is_not_a_number_is_left_out_of_the_step(root):
    _seed(root)
    good = fixtures.workflow_steps()[("acme.flows", "ingest:6")].steps[0]
    root.for_namespace("acme.flows").put(
        steps_collection(PROJECT),
        "ingest:6#fetch",
        _as_journaled("ingest:6", good)
        | {"status": "SUCCEEDED", "finished_at": "2026-10-02T12:00:02+00:00"}
        | {"duration_ms": "long", "result_bytes": "big"},
    )

    (step,) = _journal(root, "ingest:6").steps

    assert (step.status, step.duration_ms, step.result_bytes) == ("SUCCEEDED", None, None)


def test_a_bad_attempt_skips_only_that_step(root):
    _seed(root)
    steps = _journal(root, "ingest:5")
    root.for_namespace("acme.flows").put(
        steps_collection(PROJECT),
        "ingest:5#fetch",
        _as_journaled("ingest:5", fixtures.workflow_steps()[("acme.flows", "ingest:5")].steps[0])
        | {"attempt": "two"},
    )

    after = _journal(root, "ingest:5")

    assert [s.key for s in steps.steps] == ["fetch", "map[0]", "map[1]"]
    assert [s.key for s in after.steps] == ["map[0]", "map[1]"]


def test_a_module_without_a_journal_has_no_steps(root):
    assert _journal(root, "ingest:5").steps == ()


def test_another_project_has_other_steps(root):
    _seed(root)

    assert _journal(root, "ingest:5", project="other").steps == ()


def test_backend_errors_make_the_source_unavailable():
    def broken():
        raise RuntimeError("document service down")

    with pytest.raises(SourceUnavailable) as exc:
        asyncio.run(DocumentWorkflowSteps(broken, PROJECT).journal("acme.flows", "ingest:5"))
    assert exc.value.source == "steps"
