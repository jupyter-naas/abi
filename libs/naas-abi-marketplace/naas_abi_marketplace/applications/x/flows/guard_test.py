"""The overlap rule: only a run that started earlier blocks, and only its own target."""

from __future__ import annotations

import asyncio

from naas_abi_marketplace.applications.x.flows.conftest import FakeDocuments
from naas_abi_marketplace.applications.x.flows.guard import earlier_active_runs


def record(sequence: int, status: str = "RUNNING", filter: str = "news") -> dict:
    return {
        "run_id": f"search:{sequence}",
        "job": "search",
        "status": status,
        "sequence": sequence,
        "payload": {"filter": filter},
    }


def blocking(records, run_id="search:10", **kwargs):
    return asyncio.run(
        earlier_active_runs(FakeDocuments(records), "runs", "search", run_id, **kwargs)
    )


def test_an_earlier_running_run_blocks():
    assert blocking([record(4)]) == ["search:4"]


def test_a_run_between_two_attempts_still_blocks():
    assert blocking([record(4, "RETRYING")]) == ["search:4"]


def test_finished_runs_do_not_block():
    assert blocking([record(4, "SUCCEEDED"), record(5, "FAILED")]) == []


def test_a_run_never_counts_itself():
    assert blocking([record(10)]) == []


def test_two_ticks_that_start_together_do_not_both_skip():
    # The newer one sees the older and skips; the older sees only a newer run.
    assert blocking([record(10), record(11)], run_id="search:11") == ["search:10"]
    assert blocking([record(10), record(11)], run_id="search:10") == []


def test_only_the_same_target_blocks():
    records = [record(4, filter="sports")]
    same = lambda payload: payload.get("filter") == "news"
    assert blocking(records, same_target=same) == []
    assert blocking([record(4)], same_target=same) == ["search:4"]


def test_it_reads_the_runs_of_the_job_in_the_given_collection():
    documents = FakeDocuments([record(4)])
    asyncio.run(earlier_active_runs(documents, "runs_x", "search", "search:10"))
    assert documents.finds[0]["collection"] == "runs_x"
    assert ("job", "eq", "search") in documents.finds[0]["where"]
