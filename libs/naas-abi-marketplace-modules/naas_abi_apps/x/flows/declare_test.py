"""What the X module declares to its job host, from its configuration (no broker)."""

from __future__ import annotations

import asyncio
from datetime import timedelta

import pytest
from naas_abi_apps.x.configuration import XSearchRecentTweetsFilesConfiguration
from naas_abi_apps.x.flows import search
from naas_abi_apps.x.flows.conftest import real_x_module, search_filter
from naas_abi_apps.x.flows.models import SearchRecentTweetsOutput
from naas_abi_sdk.jobs import Cron, Every, JobContext
from naas_abi_sdk.workflows import InvalidWorkflowInput

STATIC_WORKFLOWS = {
    "map_tweet_envelope",
    "reprocess_tweet_envelopes",
    "count_recent_tweets",
}


def declared(module):
    return {job.name: job for job in module.jobs}


def test_the_module_declares_the_mapping_reprocess_and_count_workflows_and_two_jobs():
    jobs = declared(real_x_module())
    assert {n for n, j in jobs.items() if j.kind == "workflow"} == STATIC_WORKFLOWS
    assert {n for n, j in jobs.items() if j.kind == "job"} == {
        "build_app",
        "compact_dataset",
    }


def test_the_mapping_and_count_workflows_have_no_trigger_and_their_limits():
    jobs = declared(real_x_module())
    mapping, count = jobs["map_tweet_envelope"], jobs["count_recent_tweets"]
    assert mapping.triggers == () and count.triggers == ()
    assert (mapping.max_concurrency, mapping.max_attempts) == (
        search.MAP_CONCURRENCY,
        3,
    )
    assert count.max_attempts == 3
    # children are never skipped for an earlier one: each envelope is its own
    assert not mapping.skip_if_running and not count.skip_if_running


def test_the_jobs_keep_their_schedules_in_utc_and_skip_a_tick_while_one_runs():
    jobs = declared(real_x_module())
    assert jobs["build_app"].triggers == (Cron("0 0 * * * *", time_zone="UTC"),)
    assert jobs["compact_dataset"].triggers == (
        Cron("0 30 */6 * * *", time_zone="UTC"),
    )
    for name in ("build_app", "compact_dataset"):
        # a running one, and the next tick, which takes a slot to start and skip
        assert jobs[name].skip_if_running and jobs[name].max_concurrency == 2


def test_the_workflows_have_typed_inputs_the_launch_form_can_use():
    jobs = declared(real_x_module(search_filter("news")))
    assert '"path"' in jobs["map_tweet_envelope"].input_schema
    assert '"prefix"' in jobs["reprocess_tweet_envelopes"].input_schema
    assert '"query"' in jobs["count_recent_tweets"].input_schema
    assert '"filter"' in jobs["search_recent_tweets"].input_schema


def test_without_filters_there_is_no_search_workflow():
    assert "search_recent_tweets" not in declared(real_x_module())


def test_each_filter_is_one_trigger_of_the_search_workflow_carrying_its_name():
    module = real_x_module(
        search_filter("news", cron="0 * * * *"),
        search_filter("sports", interval_seconds=900),
        search_filter("misc"),
    )

    search_job = declared(module)["search_recent_tweets"]
    assert search_job.kind == "workflow"
    assert search_job.triggers == (
        # the configured 5-field cron, as NATS takes it (seconds first)
        Cron("0 0 * * * *", time_zone="UTC", input={"filter": "news"}),
        Every(timedelta(seconds=900), input={"filter": "sports"}),
        Every(timedelta(seconds=60), input={"filter": "misc"}),
    )
    # a running tick and the overlapping one that skips, per filter: never queued
    assert search_job.skip_if_running
    assert search_job.max_concurrency == 6 and search_job.max_attempts == 3


def test_more_filters_than_a_descriptor_holds_declare_more_workflows():
    module = real_x_module(*(search_filter(f"f{i}") for i in range(20)))
    jobs = declared(module)
    first, second = jobs["search_recent_tweets"], jobs["search_recent_tweets_2"]
    assert (len(first.triggers), len(second.triggers)) == (16, 4)
    assert (first.max_concurrency, second.max_concurrency) == (32, 8)
    assert first.skip_if_running and second.skip_if_running
    assert "search_recent_tweets_3" not in jobs


def test_concurrency_stays_within_what_a_descriptor_allows():
    module = real_x_module(*(search_filter(f"f{i}") for i in range(16)))
    assert declared(module)["search_recent_tweets"].max_concurrency == 32


def test_the_manual_reprocess_workflow_exists_without_files_entries():
    jobs = declared(real_x_module())
    reprocess = jobs["reprocess_tweet_envelopes"]
    assert reprocess.kind == "workflow" and reprocess.triggers == ()
    assert reprocess.skip_if_running and reprocess.max_concurrency == 2
    assert reprocess.max_attempts == 2
    assert "reprocess_tweet_envelopes_2" not in jobs


def test_a_files_entry_schedules_the_reprocess_workflow_with_its_input():
    module = real_x_module(
        files=[
            XSearchRecentTweetsFilesConfiguration(
                name="sweep", cron="0,30 * * * *", max_age_hours=24
            )
        ]
    )
    reprocess = declared(module)["reprocess_tweet_envelopes"]
    assert [t.spec for t in reprocess.triggers] == ["0 0,30 * * * *"]
    assert reprocess.triggers[0].input == {
        "prefix": "x/search_recent_tweets",
        "persist": True,
        "force": False,
        "app_publish": False,
        "max_age_hours": 24,
    }


def test_every_declared_job_has_a_handler():
    module = real_x_module(
        *(search_filter(f"f{i}") for i in range(17)),
        files=[XSearchRecentTweetsFilesConfiguration(name="sweep")],
    )
    assert module.missing_job_handlers() == set()


def job_context(name: str, payload: dict) -> JobContext:
    return JobContext(
        run_id=f"{name}:1", job=name, attempt=1, trigger={}, payload=payload
    )


def test_the_search_handler_validates_its_input_and_calls_the_body(monkeypatch):
    module = real_x_module(search_filter("news"))
    seen = []

    async def body(mod, ctx, inp):
        seen.append((mod, inp.filter))
        return SearchRecentTweetsOutput(filter=inp.filter, envelopes=0)

    monkeypatch.setattr(search, "run_search_recent_tweets", body)
    handler = module._job_handlers["search_recent_tweets"]

    out = asyncio.run(handler(job_context("search_recent_tweets", {"filter": "news"})))

    assert seen == [(module, "news")]
    assert out["filter"] == "news" and out["envelopes"] == 0
    with pytest.raises(InvalidWorkflowInput):
        asyncio.run(handler(job_context("search_recent_tweets", {})))


def test_a_skipped_search_has_no_output(monkeypatch):
    module = real_x_module(search_filter("news"))

    async def body(mod, ctx, inp):
        ctx.skip("daily X budget reached")

    monkeypatch.setattr(search, "run_search_recent_tweets", body)
    ctx = job_context("search_recent_tweets", {"filter": "news"})
    assert asyncio.run(module._job_handlers["search_recent_tweets"](ctx)) is None
    assert ctx.skipped == "daily X budget reached"
