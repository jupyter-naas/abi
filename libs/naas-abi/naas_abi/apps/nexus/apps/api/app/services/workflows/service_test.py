import asyncio
from dataclasses import replace
from datetime import UTC, datetime

import pytest
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.in_memory_jobs import (
    InMemoryInputValidator,
    InMemoryJobCatalog,
    InMemoryJobControl,
    InMemoryJobQueue,
    InMemoryJobRunStore,
    InMemoryStepStore,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.in_memory_resources import (
    InMemoryAuditLog,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.jobs import (
    InvalidInput,
    RunNotCancellable,
    RunNotFound,
    SchemaIssue,
    WorkflowNotFound,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.jobs_service import JobsAdminService
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import SourceUnavailable
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.resources import AuditUnavailable
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.tests import fixtures
from naas_abi.apps.nexus.apps.api.app.services.workflows.service import WorkflowsService
from naas_abi.apps.nexus.apps.api.app.services.workflows.workflows import (
    MAX_WAIT_SECONDS,
    Caller,
    InvalidIdempotencyKey,
    check_idempotency_key,
)

NOW = datetime(2026, 10, 2, 13, 0, 0, tzinfo=UTC)
USER = Caller("user", "u1")
KEY = Caller("api_key")


def run(coro):
    return asyncio.run(coro)


class Clock:
    """A clock the fake sleep advances: waiting costs no time in a test."""

    def __init__(self):
        self.now = 0.0
        self.sleeps: list[float] = []

    def monotonic(self):
        return self.now

    async def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds
        if self.on_sleep:
            self.on_sleep(len(self.sleeps))

    on_sleep = None


def parts(**overrides):
    parts = {
        "catalogs": [
            InMemoryJobCatalog(fixtures.job_definitions() + fixtures.workflow_definitions())
        ],
        "runs": InMemoryJobRunStore(fixtures.job_runs() + fixtures.workflow_runs()),
        "control": InMemoryJobControl(),
        "queue": InMemoryJobQueue(),
        "audit": InMemoryAuditLog(),
        "project": "zen",
        "clock": lambda: NOW,
        "steps": InMemoryStepStore(fixtures.workflow_steps()),
        "validator": InMemoryInputValidator(),
    }
    parts.update(overrides)
    return parts


def service(clock=None, **overrides):
    clock = clock or Clock()
    return WorkflowsService(
        JobsAdminService(**parts(**overrides)), sleep=clock.sleep, monotonic=clock.monotonic
    )


def test_lists_only_workflows_with_their_schemas_and_sources():
    found = run(service().list())

    assert [w.key for w in found.workflows] == ["acme.flows/ingest", "acme.flows/map_item"]
    assert found.workflows[0].input_schema == fixtures.INGEST_INPUT_SCHEMA
    assert found.sources["engine"].available


def test_a_start_returns_the_run_id_at_once_and_is_audited_with_how_the_caller_authenticated():
    control, audit = InMemoryJobControl(), InMemoryAuditLog()

    started = run(
        service(control=control, audit=audit).start(
            USER, "acme.flows", "ingest", {"filter": "news"}, idempotency_key="k-1"
        )
    )

    assert started.run_id == "ingest:101"
    assert (started.view.run.status, started.view.finished) == ("QUEUED", False)
    assert control.triggered == [("acme.flows", "ingest", {"filter": "news"})]
    assert control.keys == ["k-1"]
    assert [
        (r.action.actor_id, r.action.via, r.action.operation, r.phase) for r in audit.records
    ] == [
        ("u1", "user", "trigger", "requested"),
        ("u1", "user", "trigger", "succeeded"),
    ]


def test_an_api_key_start_is_audited_without_a_user_id():
    audit = InMemoryAuditLog()

    run(service(audit=audit).start(KEY, "acme.flows", "ingest", {"filter": "news"}))

    assert {(r.action.actor_id, r.action.via) for r in audit.records} == {("", "api_key")}


def test_an_input_that_does_not_match_the_schema_starts_nothing_and_audits_nothing():
    control, audit = InMemoryJobControl(), InMemoryAuditLog()
    validator = InMemoryInputValidator({"x": [SchemaIssue("/limit", "too small")]})

    with pytest.raises(InvalidInput) as exc:
        run(
            service(control=control, audit=audit, validator=validator).start(
                KEY, "acme.flows", "ingest", {"name": "x"}
            )
        )

    assert exc.value.issues == (SchemaIssue("/limit", "too small"),)
    assert control.triggered == [] and audit.records == []


def test_nothing_starts_when_the_audit_record_cannot_be_written():
    control = InMemoryJobControl()

    with pytest.raises(AuditUnavailable):
        run(
            service(control=control, audit=InMemoryAuditLog(fail="db down")).start(
                KEY, "acme.flows", "ingest", {"filter": "news"}
            )
        )

    assert control.triggered == []


def test_a_plain_job_is_not_a_workflow():
    control = InMemoryJobControl()

    for name in ("nightly", "nope"):
        with pytest.raises(WorkflowNotFound):
            run(service(control=control).start(KEY, "acme.jobs", name, {}))
    assert control.triggered == []


def test_the_broker_being_down_is_an_unavailable_source_and_the_failure_is_audited():
    audit = InMemoryAuditLog()

    with pytest.raises(SourceUnavailable):
        run(
            service(control=InMemoryJobControl(fail="no broker"), audit=audit).start(
                KEY, "acme.flows", "ingest", {"filter": "news"}
            )
        )

    assert [r.phase for r in audit.records] == ["requested", "failed"]


def test_waiting_returns_the_run_as_soon_as_it_ends():
    clock = Clock()
    runs = InMemoryJobRunStore(fixtures.workflow_runs())
    finished = replace(
        fixtures.workflow_runs()[1],
        run_id="ingest:101",
        result={"count": 2},
        status="SUCCEEDED",
    )

    def appear(sleeps):
        if sleeps == 2:  # a host takes the run, then finishes it
            runs.runs.append(finished)

    clock.on_sleep = appear
    started = run(
        service(clock, runs=runs).start(KEY, "acme.flows", "ingest", {"filter": "news"}, wait=30)
    )

    assert started.view.finished and started.view.run.result == {"count": 2}
    assert len(clock.sleeps) == 2
    assert clock.sleeps[0] < clock.sleeps[1] <= 1.0  # backs off, never past a second


def test_waiting_gives_up_at_the_deadline_with_the_run_as_it_stands():
    clock = Clock()

    started = run(service(clock).start(KEY, "acme.flows", "ingest", {"filter": "news"}, wait=2.5))

    assert started.run_id == "ingest:101"
    assert (started.view.run.status, started.view.finished) == ("QUEUED", False)
    assert clock.now == pytest.approx(2.5)  # the last sleep is cut to the deadline


def test_waiting_is_capped():
    clock = Clock()

    run(service(clock).start(KEY, "acme.flows", "ingest", {"filter": "news"}, wait=10_000))

    assert clock.now == pytest.approx(MAX_WAIT_SECONDS)


def test_a_run_store_failing_while_waiting_does_not_hide_the_started_run():
    started = run(
        service(runs=InMemoryJobRunStore(fail="db down")).start(
            KEY, "acme.flows", "ingest", {"filter": "news"}, wait=1
        )
    )

    assert started.run_id == "ingest:101" and started.view.run.status == "QUEUED"


def test_a_failed_run_is_a_finished_run():
    runs = InMemoryJobRunStore(
        [replace(fixtures.workflow_runs()[2], job="ingest", run_id="ingest:101")]
    )

    started = run(service(runs=runs).start(KEY, "acme.flows", "ingest", {"filter": "news"}, wait=1))

    assert started.view.finished
    assert (started.view.run.status, started.view.run.error) == ("FAILED", "ValueError: bad item")


def test_status_has_the_whole_result_and_the_steps():
    big = {"rows": ["x" * 100 for _ in range(400)]}
    runs = InMemoryJobRunStore([replace(fixtures.workflow_runs()[1], result=big)])

    view = run(service(runs=runs).status("acme.flows", "ingest:5"))

    assert view.run.result == big  # not the Jobs tab's preview
    assert [s.key for s in view.workflow.steps] == ["fetch", "map[0]", "map[1]"]


def test_a_run_nobody_recorded_yet_reads_as_queued_when_its_workflow_exists():
    view = run(service().status("acme.flows", "ingest:77"))

    assert (view.run.status, view.run.run_id, view.workflow.steps) == ("QUEUED", "ingest:77", ())


@pytest.mark.parametrize(
    "module,run_id",
    [
        ("acme.flows", "nope:1"),  # no such workflow
        ("acme.flows", "garbage"),  # not a run id
        ("acme.jobs", "nightly:3"),  # a plain job's run
        ("acme.jobs", "nightly:99"),  # a plain job's missing run
        ("no.module", "ingest:1"),
    ],
)
def test_status_of_something_that_is_not_a_workflow_run_is_not_found(module, run_id):
    with pytest.raises(RunNotFound):
        run(service().status(module, run_id))


def test_cancel_is_audited_with_the_caller():
    control, audit = InMemoryJobControl(), InMemoryAuditLog()

    run(service(control=control, audit=audit).cancel(KEY, "acme.flows", "ingest:6"))

    assert control.cancelled == [("acme.flows", "ingest", "ingest:6")]
    assert [
        (r.action.via, r.action.operation, r.action.resource_id, r.phase) for r in audit.records
    ] == [
        ("api_key", "cancel", "acme.flows/ingest:6", "requested"),
        ("api_key", "cancel", "acme.flows/ingest:6", "succeeded"),
    ]


def test_cancel_refuses_runs_that_are_over_and_runs_of_plain_jobs():
    control, audit = InMemoryJobControl(), InMemoryAuditLog()
    flows = service(control=control, audit=audit)

    with pytest.raises(RunNotCancellable):
        run(flows.cancel(USER, "acme.flows", "ingest:5"))
    with pytest.raises(RunNotFound):
        run(flows.cancel(USER, "acme.jobs", "sync:9"))  # running, but a job's

    assert control.cancelled == [] and audit.records == []


@pytest.mark.parametrize("key", [None, ""])
def test_no_idempotency_key_is_none(key):
    assert check_idempotency_key(key) is None


def test_an_idempotency_key_must_be_a_header_value():
    assert check_idempotency_key("import-2026-10-02") == "import-2026-10-02"
    for bad in ("x" * 201, "a\nb", "é"):
        with pytest.raises(InvalidIdempotencyKey):
            check_idempotency_key(bad)
