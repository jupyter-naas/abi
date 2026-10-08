import asyncio
from datetime import UTC, datetime

import pytest
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.in_memory_jobs import (
    InMemoryJobCatalog,
    InMemoryJobControl,
    InMemoryJobQueue,
    InMemoryJobRunStore,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.in_memory_resources import (
    InMemoryAuditLog,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.jobs import (
    JobNotFound,
    RunNotCancellable,
    RunNotFound,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.jobs_service import JobsAdminService
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import SourceUnavailable
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.resources import (
    AdminAction,
    AuditRecord,
    AuditUnavailable,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.tests import fixtures

NOW = datetime(2026, 10, 2, 9, 5, 0, tzinfo=UTC)


def run(coro):
    return asyncio.run(coro)


def _service(**overrides):
    definitions = fixtures.job_definitions()
    parts = {
        "catalogs": [
            InMemoryJobCatalog([d for d in definitions if d.location == "engine"], source="engine"),
            InMemoryJobCatalog(
                [d for d in definitions if d.location == "remote"], source="discovery"
            ),
        ],
        "runs": InMemoryJobRunStore(fixtures.job_runs()),
        "control": InMemoryJobControl(),
        "queue": InMemoryJobQueue({("acme.jobs", "nightly"): (2, 1)}),
        "audit": InMemoryAuditLog(),
        "project": "zen",
        "trace_ui_url": "http://jaeger:16686",
        "clock": lambda: NOW,
    }
    parts.update(overrides)
    return JobsAdminService(**parts)


def test_overview_lists_every_job_with_schedule_runs_and_queue():
    overview = run(_service().overview())
    jobs = {j.definition.key: j for j in overview.jobs}

    assert overview.project == "zen"
    assert [j.definition.key for j in overview.jobs] == [
        "acme.jobs/nightly",
        "acme.jobs/sync",
        "acme.other/report",
    ]
    nightly = jobs["acme.jobs/nightly"]
    assert nightly.triggers[0].summary == "Every day at 06:00 UTC"
    assert nightly.next_at == nightly.triggers[0].next_at == "2026-10-03T06:00:00+00:00"
    assert [r.run_id for r in nightly.recent] == ["nightly:3", "nightly:2"]
    assert nightly.last_run is not None and nightly.last_run.run_id == "nightly:3"
    assert (nightly.queued, nightly.in_flight, nightly.running) == (2, 1, 0)

    sync = jobs["acme.jobs/sync"]
    assert sync.running == 1
    # Every 10m without a scheduled fire on record: no next tick known.
    assert sync.next_at is None and sync.triggers[0].summary == "Every 10 minutes"
    assert (sync.queued, sync.in_flight) == (None, None)

    report = jobs["acme.other/report"]
    assert report.definition.instances == 2 and report.next_at is None
    assert all(s.available for s in overview.sources.values())
    assert set(overview.sources) == {"engine", "discovery", "runs", "queue"}


def test_every_triggers_roll_forward_from_the_last_scheduled_fire():
    runs = fixtures.job_runs()
    from dataclasses import replace

    from naas_abi.apps.nexus.apps.api.app.services.sysadmin.jobs import RunTrigger

    runs.append(
        replace(
            runs[2],
            run_id="sync:8",
            status="SUCCEEDED",
            trigger=RunTrigger("schedule"),
            fired_at="2026-10-02T08:50:00+00:00",
            started_at="2026-10-02T08:50:00.100000+00:00",
            finished_at="2026-10-02T08:50:02+00:00",
        )
    )
    overview = run(_service(runs=InMemoryJobRunStore(runs)).overview())
    sync = next(j for j in overview.jobs if j.definition.name == "sync")

    assert sync.next_at == "2026-10-02T09:10:00+00:00"


def test_runs_recorded_before_fired_at_anchor_intervals_on_their_start():
    runs = fixtures.job_runs()
    from dataclasses import replace

    from naas_abi.apps.nexus.apps.api.app.services.sysadmin.jobs import RunTrigger

    runs.append(
        replace(
            runs[2],
            run_id="sync:9",
            status="SUCCEEDED",
            trigger=RunTrigger("schedule"),
            fired_at=None,
            started_at="2026-10-02T08:50:00.100000+00:00",
            finished_at="2026-10-02T08:50:02+00:00",
        )
    )
    overview = run(_service(runs=InMemoryJobRunStore(runs)).overview())
    sync = next(j for j in overview.jobs if j.definition.name == "sync")

    assert sync.next_at is not None and sync.next_at.startswith("2026-10-02T09:10:00")


def test_overview_degrades_per_source():
    overview = run(
        _service(
            catalogs=[
                InMemoryJobCatalog(fixtures.job_definitions()[:2], source="engine"),
                SourceUnavailable("discovery", "nats.discovery is not configured"),
            ],
            runs=InMemoryJobRunStore(fail="document service down"),
            queue=InMemoryJobQueue(fail="no broker"),
        ).overview()
    )

    assert [j.definition.name for j in overview.jobs] == ["nightly", "sync"]
    assert overview.sources["discovery"].reason == "nats.discovery is not configured"
    assert overview.sources["runs"].available is False
    assert overview.sources["queue"].available is False
    assert all(j.recent == () and j.last_run is None and j.queued is None for j in overview.jobs)


def test_runs_page_across_job_modules_with_a_cursor():
    service = _service()

    first = run(service.runs(limit=2))
    second = run(service.runs(limit=2, before=first.next))
    failed = run(service.runs(statuses=["FAILED", "TIMED_OUT"]))
    one_job = run(service.runs(module="acme.jobs", job="nightly"))

    assert [r.run_id for r in first.runs] == ["sync:9", "report:1"]
    assert first.next == "2026-10-02T07:00:01+00:00"
    assert [r.run_id for r in second.runs] == ["nightly:3", "nightly:2"]
    assert [r.run_id for r in failed.runs] == ["report:1", "nightly:2"]
    assert failed.next is None
    assert [r.run_id for r in one_job.runs] == ["nightly:3", "nightly:2"]


def test_runs_need_the_run_store():
    with pytest.raises(SourceUnavailable):
        run(_service(runs=SourceUnavailable("runs", "NATS mode is off")).runs())


def test_a_run_with_its_trace_link():
    detail, trace_url = run(_service().run("acme.jobs", "nightly:3"))

    assert detail.result == {"rows": 3}
    assert trace_url == "http://jaeger:16686/trace/" + "b" * 32
    _, no_trace = run(_service().run("acme.jobs", "sync:9"))
    assert no_trace is None
    with pytest.raises(RunNotFound):
        run(_service().run("acme.jobs", "nightly:99"))


def test_trigger_is_audited_and_returns_the_run_id():
    control, audit = InMemoryJobControl(), InMemoryAuditLog()
    run_id = run(
        _service(control=control, audit=audit).trigger("u1", "acme.jobs", "nightly", {"full": True})
    )

    assert run_id == "nightly:101"
    assert control.triggered == [("acme.jobs", "nightly", {"full": True})]
    action = AdminAction("u1", "jobs", "trigger", "acme.jobs/nightly")
    assert audit.records == [AuditRecord(action, "requested"), AuditRecord(action, "succeeded")]


def test_unknown_jobs_cannot_be_triggered():
    control = InMemoryJobControl()
    with pytest.raises(JobNotFound):
        run(_service(control=control).trigger("u1", "acme.jobs", "nope", {}))
    assert control.triggered == []


def test_no_trigger_without_an_audit_record():
    control = InMemoryJobControl()
    with pytest.raises(AuditUnavailable):
        run(
            _service(control=control, audit=InMemoryAuditLog(fail="db down")).trigger(
                "u1", "acme.jobs", "nightly", {}
            )
        )
    assert control.triggered == []


def test_trigger_needs_nats():
    with pytest.raises(SourceUnavailable):
        run(
            _service(control=SourceUnavailable("jobs", "NATS mode is off")).trigger(
                "u1", "acme.jobs", "nightly", {}
            )
        )


def test_cancel_only_running_runs_and_audit_it():
    control, audit = InMemoryJobControl(), InMemoryAuditLog()
    service = _service(control=control, audit=audit)

    run(service.cancel("u1", "acme.jobs", "sync:9"))

    assert control.cancelled == [("acme.jobs", "sync", "sync:9")]
    assert audit.records[-1] == AuditRecord(
        AdminAction("u1", "jobs", "cancel", "acme.jobs/sync:9"), "succeeded"
    )
    with pytest.raises(RunNotCancellable) as exc:
        run(service.cancel("u1", "acme.jobs", "nightly:3"))
    assert exc.value.status == "SUCCEEDED"
    with pytest.raises(RunNotFound):
        run(service.cancel("u1", "acme.jobs", "nightly:99"))


def test_failures_since_a_time_newest_first():
    service = _service()

    recent = asyncio.run(service.failures(since="2026-10-02T00:00:00+00:00"))
    assert [r.run_id for r in recent.runs] == ["report:1"] and recent.count == 1
    assert recent.since == "2026-10-02T00:00:00+00:00"
    everything = asyncio.run(service.failures(since="2026-09-01T00:00:00+00:00"))
    assert [r.run_id for r in everything.runs] == ["report:1", "nightly:2"]
    assert everything.count == 2 and everything.more is False


def test_failures_default_to_the_last_day():
    failures = asyncio.run(_service().failures())

    assert failures.since == "2026-10-01T09:05:00+00:00"
    assert [r.run_id for r in failures.runs] == ["report:1"]


def test_failures_need_the_run_store():
    with pytest.raises(SourceUnavailable):
        asyncio.run(_service(runs=SourceUnavailable("runs", "down")).failures())


def _with_skipped_runs():
    from naas_abi.apps.nexus.apps.api.app.services.sysadmin.jobs import JobRun, RunTrigger

    skipped = [
        JobRun(
            "acme.jobs",
            "nightly",
            f"nightly:{n}",
            "SKIPPED",
            trigger=RunTrigger("schedule"),
            started_at=f"2026-10-02T08:0{n}:00+00:00",
            finished_at=f"2026-10-02T08:0{n}:01+00:00",
            skip_reason="nothing new",
        )
        for n in (5, 6)
    ]
    return InMemoryJobRunStore(fixtures.job_runs() + skipped)


def test_skipped_runs_are_hidden_unless_asked_for():
    service = _service(runs=_with_skipped_runs())

    default = run(service.runs(module="acme.jobs", job="nightly"))
    skipped = run(service.runs(statuses=["SKIPPED"]))
    everything = run(service.runs(module="acme.jobs", job="nightly", include_skipped=True))

    assert [r.run_id for r in default.runs] == ["nightly:3", "nightly:2"]
    assert [r.run_id for r in skipped.runs] == ["nightly:6", "nightly:5"]
    assert skipped.runs[0].skip_reason == "nothing new"
    assert [r.run_id for r in everything.runs] == [
        "nightly:6",
        "nightly:5",
        "nightly:3",
        "nightly:2",
    ]


def test_the_overview_shows_real_runs_and_when_a_job_last_had_nothing_to_do():
    overview = run(_service(runs=_with_skipped_runs()).overview())
    nightly = {j.definition.key: j for j in overview.jobs}["acme.jobs/nightly"]

    assert [r.run_id for r in nightly.recent] == ["nightly:3", "nightly:2"]
    assert nightly.last_run is not None and nightly.last_run.run_id == "nightly:3"
    assert nightly.last_skipped is not None and nightly.last_skipped.run_id == "nightly:6"


def test_skipped_runs_are_never_failures():
    found = run(_service(runs=_with_skipped_runs()).failures(since="2026-10-01T00:00:00+00:00"))

    assert all(r.status in ("FAILED", "TIMED_OUT") for r in found.runs)
