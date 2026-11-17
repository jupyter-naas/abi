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


def test_a_bearer_token_in_the_configuration_is_ignored_with_a_warning(caplog):
    # X_BEARER_TOKEN exported in the shell reaches the module as this field.
    with caplog.at_level("WARNING"):
        config = XConfiguration(bearer_token="tok-123")
    assert config.bearer_token is None
    assert "applications.x/X_BEARER_TOKEN" in caplog.text
    assert "tok-123" not in caplog.text


def test_agent_max_pages_defaults_to_five_and_reads_a_variable():
    assert XConfiguration().agent_max_pages == 5
    assert XConfiguration(agent_max_pages="2").agent_max_pages == 2
    with pytest.raises(ValueError, match="agent_max_pages"):
        XConfiguration(agent_max_pages="0")


BAD_NAMES = ["ai-llms", "a b", "x/y", "", "é", "a.b"]


@pytest.mark.parametrize("name", BAD_NAMES)
@pytest.mark.parametrize(
    "setting",
    [
        "search_recent_tweets_workflow",
        "search_recent_tweets_files",
        "count_recent_tweets_workflow",
    ],
)
def test_entry_names_are_letters_digits_and_underscores(setting, name):
    with pytest.raises(ValueError, match="letters, digits"):
        XConfiguration(**{setting: [{"name": name, "query": "q"}]})


@pytest.mark.parametrize("name", ["agent", "Agent"])
def test_agent_is_the_agent_ledger_not_a_search_filter(name):
    with pytest.raises(ValueError, match="reserved"):
        XConfiguration(search_recent_tweets_workflow=[{"name": name, "query": "q"}])
    # Other entries have no ledger.
    XConfiguration(search_recent_tweets_files=[{"name": name}])


def test_names_differing_only_in_case_share_a_ledger_so_are_duplicates():
    with pytest.raises(ValueError, match="duplicate entry names"):
        XConfiguration(
            search_recent_tweets_workflow=[
                {"name": "News", "query": "a"},
                {"name": "news", "query": "b"},
            ]
        )


def test_app_and_lists_given_as_json_strings_are_parsed():
    # X_APP is a str: common.runtime parses only fields annotated list / dict.
    config = XConfiguration(
        app='{"publish": false, "dataset": {"read_enabled": true}}',
        search_recent_tweets_workflow='[{"name": "news", "query": "q"}]',
        search_recent_tweets_files="[]",
    )
    assert config.app.publish is False and config.app.dataset.read_enabled
    assert config.search_recent_tweets_workflow[0].name == "news"
    assert config.search_recent_tweets_files == []


@pytest.mark.parametrize(
    ("setting", "value"),
    [("app", "{publish: no"), ("search_recent_tweets_workflow", "[{")],
)
def test_bad_json_names_the_setting(setting, value):
    with pytest.raises(ValueError, match=f"{setting} must be JSON"):
        XConfiguration(**{setting: value})
