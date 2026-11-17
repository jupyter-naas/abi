"""Schedule configuration of the X module's entries.

``search_recent_tweets_workflow`` and ``search_recent_tweets_files`` entries
are driven either by an interval (``interval_seconds``, an ``Every`` trigger)
or by a cron (``cron``, a ``Cron`` trigger in UTC): never both.
"""

from __future__ import annotations

import pytest
from naas_abi_apps.x.configuration import (
    DEFAULT_FILES_INTERVAL_SECONDS,
    DEFAULT_SEARCH_INTERVAL_SECONDS,
    XConfiguration,
    XSearchRecentTweetsFilesConfiguration,
    XTweetSearchWorkflowConfiguration,
)

QUERY = "(openai OR anthropic) lang:en -is:retweet"
MALFORMED = ["", "   ", "0 *", "not a cron", "0 0 * * * * *"]


def search(**overrides) -> XTweetSearchWorkflowConfiguration:
    return XTweetSearchWorkflowConfiguration(name="ai_llms", query=QUERY, **overrides)


def files(**overrides) -> XSearchRecentTweetsFilesConfiguration:
    return XSearchRecentTweetsFilesConfiguration(
        name="reprocess_envelopes", **overrides
    )


ENTRIES = [
    pytest.param(search, DEFAULT_SEARCH_INTERVAL_SECONDS, 3600, id="search"),
    pytest.param(files, DEFAULT_FILES_INTERVAL_SECONDS, 5400, id="files"),
]


@pytest.mark.parametrize(("entry", "default", "interval"), ENTRIES)
def test_interval_seconds_only_keeps_the_interval(entry, default, interval):
    config = entry(interval_seconds=interval)
    assert config.interval_seconds == interval
    assert config.cron is None


@pytest.mark.parametrize(("entry", "default", "interval"), ENTRIES)
def test_cron_only_keeps_the_cron(entry, default, interval):
    config = entry(cron="0,15,30,45 * * * *")
    assert config.cron == "0,15,30,45 * * * *"
    assert config.interval_seconds is None


@pytest.mark.parametrize(("entry", "default", "interval"), ENTRIES)
def test_neither_defaults_to_the_interval(entry, default, interval):
    config = entry()
    assert config.interval_seconds == default
    assert config.cron is None


@pytest.mark.parametrize(("entry", "default", "interval"), ENTRIES)
def test_both_interval_and_cron_is_rejected(entry, default, interval):
    with pytest.raises(ValueError, match="not both"):
        entry(interval_seconds=interval, cron="0 * * * *")


@pytest.mark.parametrize(("entry", "default", "interval"), ENTRIES)
def test_cron_is_normalized(entry, default, interval):
    assert entry(cron="  0 9 * * 1-5  ").cron == "0 9 * * 1-5"


@pytest.mark.parametrize("cron", MALFORMED)
@pytest.mark.parametrize(("entry", "default", "interval"), ENTRIES)
def test_malformed_cron_is_rejected(entry, default, interval, cron):
    with pytest.raises(ValueError, match="cron"):
        entry(cron=cron)


@pytest.mark.parametrize(
    "cron", ["@hourly", "0 * * * *", "*/15 9-17 * * 1-5", "0 0 1 * * *"]
)
@pytest.mark.parametrize(("entry", "default", "interval"), ENTRIES)
def test_accepted_cron_forms(entry, default, interval, cron):
    assert entry(cron=cron).cron == cron


def test_the_module_configuration_validates_its_entries():
    config = XConfiguration(
        search_recent_tweets_workflow=[
            {"name": "news", "query": "q", "cron": "@daily"}
        ],
        search_recent_tweets_files=[{"name": "sweep"}],
        count_recent_tweets_workflow=[{"name": "feed", "query": "q"}],
        app={"dataset": {"sync_enabled": True}},
    )
    assert isinstance(
        config.search_recent_tweets_workflow[0], XTweetSearchWorkflowConfiguration
    )
    assert config.search_recent_tweets_files[0].interval_seconds == 5400
    assert config.app.dataset.sync_enabled is True and config.app.publish is True


def test_duplicate_entry_names_are_refused():
    with pytest.raises(ValueError, match="duplicate entry names"):
        XConfiguration(
            search_recent_tweets_workflow=[
                {"name": "news", "query": "a"},
                {"name": "news", "query": "b"},
            ]
        )


def test_a_bearer_token_in_the_configuration_is_refused():
    with pytest.raises(ValueError, match="engine secret"):
        XConfiguration(bearer_token="secret")
