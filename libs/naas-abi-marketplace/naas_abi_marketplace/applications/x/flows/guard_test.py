"""The overlap rule: only a run that started earlier blocks, and only its own target."""

from __future__ import annotations

import asyncio

import pytest
from naas_abi_marketplace.applications.x.flows.conftest import FakeDocuments
from naas_abi_marketplace.applications.x.flows.guard import (
    OverlapCheckBlind,
    earlier_active_runs,
)


def record(sequence: int, status: str = "RUNNING", filter: str = "news") -> dict:
    return {
        "run_id": f"search:{sequence}",
        "job": "search",
        "status": status,
        "sequence": sequence,
        "payload": {"filter": filter},
    }


def blocking(records, run_id="search:10", **kwargs):
    """The runs that block *run_id*, whose own record the host saved as RUNNING."""
    own = (
        []
        if any(r["run_id"] == run_id for r in records)
        else [record(int(run_id.split(":")[1]))]
    )
    return asyncio.run(
        earlier_active_runs(
            FakeDocuments([*records, *own]), "runs", "search", run_id, **kwargs
        )
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
    documents = FakeDocuments([record(4), record(10)])
    asyncio.run(earlier_active_runs(documents, "runs_x", "search", "search:10"))
    assert documents.finds[0]["collection"] == "runs_x"
    assert ("job", "eq", "search") in documents.finds[0]["where"]


def test_a_check_that_cannot_see_the_running_run_fails_loudly_instead_of_finding_nothing():
    # The host saved this run as RUNNING before its handler started: not finding it
    # means the collection or a field changed, and "no overlap" would be a guess.
    documents = FakeDocuments([record(4)])  # an active run, but not this one
    with pytest.raises(OverlapCheckBlind, match="search:10"):
        asyncio.run(earlier_active_runs(documents, "runs", "search", "search:10"))


def test_no_records_at_all_fails_loudly_too():
    with pytest.raises(OverlapCheckBlind):
        asyncio.run(
            earlier_active_runs(FakeDocuments([]), "runs", "search", "search:10")
        )


def test_a_lookup_in_the_wrong_collection_is_caught():
    class OtherCollection(FakeDocuments):
        async def find(self, collection, **kwargs):
            if collection != "runs_default":
                return await FakeDocuments([]).find(collection, **kwargs)
            return await super().find(collection, **kwargs)

    documents = OtherCollection([record(10)])
    asyncio.run(earlier_active_runs(documents, "runs_default", "search", "search:10"))
    with pytest.raises(OverlapCheckBlind):
        asyncio.run(
            earlier_active_runs(documents, "runs_renamed", "search", "search:10")
        )
