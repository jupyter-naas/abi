"""Triggers built from the ``search_recent_tweets_workflow`` configuration."""

from __future__ import annotations

from datetime import timedelta

import pytest
from naas_abi_core.module.jobs import Cron, Every
from naas_abi_marketplace.applications.x import (
    XSearchRecentTweetsFilesConfiguration,
    XTweetSearchWorkflowConfiguration,
)
from naas_abi_marketplace.applications.x.flows.conftest import search_filter
from naas_abi_marketplace.applications.x.flows.triggers import (
    MAX_TRIGGERS_PER_WORKFLOW,
    nats_cron,
    reprocess_trigger,
    reprocess_triggers,
    search_trigger,
    search_triggers,
    shards,
)


@pytest.mark.parametrize(
    ("configured", "nats"),
    [
        ("0 * * * *", "0 0 * * * *"),
        ("*/15 9-17 * * 1-5", "0 */15 9-17 * * 1-5"),
        ("@hourly", "@hourly"),
        # croniter puts the seconds last, NATS first
        ("0 * * * * 30", "30 0 * * * *"),
    ],
)
def test_a_configured_cron_becomes_a_nats_schedule(configured, nats):
    assert nats_cron(configured) == nats


def test_a_cron_entry_gets_a_cron_trigger_carrying_its_filter():
    trigger = search_trigger(search_filter("news", cron="10,25,40,55 * * * *"))
    assert isinstance(trigger, Cron)
    assert trigger.spec == "0 10,25,40,55 * * * *"
    assert trigger.time_zone == "UTC" and trigger.input == {"filter": "news"}


def test_an_interval_entry_gets_an_every_trigger_carrying_its_filter():
    trigger = search_trigger(search_filter("news", interval_seconds=3600))
    assert isinstance(trigger, Every) and trigger.input == {"filter": "news"}
    assert trigger == Every(timedelta(hours=1), input={"filter": "news"})


def test_an_entry_with_no_cadence_ticks_every_minute():
    trigger = search_trigger(search_filter("news"))
    assert trigger == Every(timedelta(seconds=60), input={"filter": "news"})


def test_both_cadences_still_fail_at_config_load():
    with pytest.raises(ValueError, match="not both"):
        XTweetSearchWorkflowConfiguration(
            name="news", query="q", cron="0 * * * *", interval_seconds=60
        )


def test_each_filter_gets_its_own_trigger():
    triggers = search_triggers(
        [search_filter("news"), search_filter("sports", cron="@daily")]
    )
    assert list(triggers) == ["news", "sports"]
    assert triggers["news"].input == {"filter": "news"}
    assert triggers["sports"].input == {"filter": "sports"}


def test_a_duplicate_name_keeps_the_first_entry():
    first, second = (
        search_filter("news", interval_seconds=60),
        search_filter("news", interval_seconds=90),
    )
    triggers = search_triggers([first, second])
    assert list(triggers) == ["news"] and triggers["news"].interval == "60s"


def test_an_entry_nats_cannot_schedule_is_left_out_not_fatal():
    bad = search_filter("bad", cron="@sometimes")
    assert list(search_triggers([bad, search_filter("news")])) == ["news"]


def test_triggers_are_split_to_what_a_descriptor_holds():
    triggers = search_triggers([search_filter(f"f{i}") for i in range(35)])
    groups = shards(triggers)
    assert [len(g) for g in groups] == [MAX_TRIGGERS_PER_WORKFLOW, 16, 3]


def files_entry(name="sweep", **overrides):
    return XSearchRecentTweetsFilesConfiguration(name=name, **overrides)


def test_a_files_entry_is_a_scheduled_reprocess_carrying_its_input():
    trigger = reprocess_trigger(
        files_entry(
            cron="0,15,30,45 * * * *",
            prefix="x/search_recent_tweets/news",
            skip_existing=False,
            max_age_hours=24,
            persist=False,
            app_publish=True,
        )
    )
    assert isinstance(trigger, Cron) and trigger.spec == "0 0,15,30,45 * * * *"
    assert trigger.input == {
        "prefix": "x/search_recent_tweets/news",
        "persist": False,
        "force": True,  # skip_existing: false
        "app_publish": True,
        "max_age_hours": 24,
    }


def test_a_files_entry_without_a_cadence_sweeps_every_hour_and_a_half():
    trigger = reprocess_trigger(files_entry())
    assert trigger == Every(
        timedelta(seconds=5400),
        input={
            "prefix": "x/search_recent_tweets",
            "persist": True,
            "force": False,
            "app_publish": False,
        },
    )


def test_files_entries_are_one_trigger_each_by_name():
    triggers = reprocess_triggers(
        [files_entry("a"), files_entry("b"), files_entry("a")]
    )
    assert list(triggers) == ["a", "b"]
