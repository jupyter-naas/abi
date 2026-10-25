"""What the X module declares to the jobs runtime, from its configuration."""

from __future__ import annotations

from datetime import timedelta

from naas_abi_core.module.jobs import Cron, Every
from naas_abi_marketplace.applications.x.flows.conftest import (
    real_x_module,
    search_filter,
)

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


def test_the_reprocess_workflow_is_manual_only():
    jobs = declared(real_x_module())
    assert jobs["reprocess_tweet_envelopes"].triggers == ()
    assert jobs["map_tweet_envelope"].triggers == ()
    assert jobs["count_recent_tweets"].triggers == ()


def test_the_jobs_keep_the_dagster_schedules_in_utc():
    jobs = declared(real_x_module())
    assert jobs["build_app"].triggers == (Cron("0 0 * * * *", time_zone="UTC"),)
    assert jobs["compact_dataset"].triggers == (
        Cron("0 30 */6 * * *", time_zone="UTC"),
    )


def test_the_workflows_have_typed_inputs_the_launch_form_can_use():
    jobs = declared(real_x_module())
    assert '"path"' in jobs["map_tweet_envelope"].input_schema
    assert '"prefix"' in jobs["reprocess_tweet_envelopes"].input_schema
    assert '"query"' in jobs["count_recent_tweets"].input_schema


def test_without_filters_there_is_no_search_workflow():
    module = real_x_module()
    module._declare_search_workflows()
    assert "search_recent_tweets" not in declared(module)


def test_each_filter_is_one_trigger_of_the_search_workflow_carrying_its_name():
    module = real_x_module(
        search_filter("news", cron="0 * * * *"),
        search_filter("sports", interval_seconds=900),
        search_filter("misc"),
    )
    module._declare_search_workflows()

    search = declared(module)["search_recent_tweets"]
    assert search.kind == "workflow"
    assert search.triggers == (
        Cron("0 0 * * * *", time_zone="UTC", input={"filter": "news"}),
        Every(timedelta(seconds=900), input={"filter": "sports"}),
        Every(timedelta(seconds=60), input={"filter": "misc"}),
    )
    assert '"filter"' in search.input_schema
    # filters run side by side; the overlap of one filter is skipped, not queued
    assert search.max_concurrency == 3 and search.max_attempts == 3


def test_more_filters_than_a_descriptor_holds_declare_more_workflows():
    module = real_x_module(*(search_filter(f"f{i}") for i in range(20)))
    module._declare_search_workflows()
    jobs = declared(module)
    assert len(jobs["search_recent_tweets"].triggers) == 16
    assert len(jobs["search_recent_tweets_2"].triggers) == 4


def test_every_declared_job_has_a_handler():
    module = real_x_module(search_filter("news"))
    module._declare_search_workflows()
    assert module.missing_job_handlers() == set()


def test_a_downstream_subclass_does_not_host_the_jobs_twice(monkeypatch):
    # signals.x extends this module next to it; as for the orchestrations, the
    # marketplace module alone declares the jobs.
    module = real_x_module(search_filter("news"))
    monkeypatch.setattr(type(module), "__module__", "signals.x")
    monkeypatch.setattr(
        "naas_abi_core.module.Module.BaseModule.on_load", lambda self: None
    )
    module.on_load()
    assert module.jobs == ()
