"""Schedule configuration for files-reprocessing entries in the X module.

``search_recent_tweets_files`` entries are driven either by a sensor
(``interval_seconds``) or by a cron schedule (``cron``) — never both.
"""

import pytest
from naas_abi_marketplace.applications.x import (
    DEFAULT_FILES_INTERVAL_SECONDS,
    XSearchRecentTweetsFilesConfiguration,
)


def _config(**overrides) -> XSearchRecentTweetsFilesConfiguration:
    return XSearchRecentTweetsFilesConfiguration(name="reprocess_envelopes", **overrides)


def test_interval_seconds_only_keeps_sensor_mode():
    config = _config(interval_seconds=5400)

    assert config.interval_seconds == 5400
    assert config.cron is None


def test_cron_only_keeps_schedule_mode():
    config = _config(cron="0,15,30,45 * * * *")

    assert config.cron == "0,15,30,45 * * * *"
    assert config.interval_seconds is None


def test_neither_defaults_to_sensor_interval():
    config = _config()

    assert config.interval_seconds == DEFAULT_FILES_INTERVAL_SECONDS
    assert config.cron is None


def test_both_interval_and_cron_is_rejected():
    with pytest.raises(ValueError, match="not both"):
        _config(interval_seconds=5400, cron="0 * * * *")


def test_cron_is_normalized():
    assert _config(cron="  0,15,30,45 * * * *  ").cron == "0,15,30,45 * * * *"


@pytest.mark.parametrize("cron", ["", "   ", "0 *", "not a cron", "0 0 * * * * *"])
def test_malformed_cron_is_rejected(cron: str):
    with pytest.raises(ValueError, match="cron"):
        _config(cron=cron)


@pytest.mark.parametrize(
    "cron", ["@hourly", "0 * * * *", "0,15,30,45 * * * *", "0 0 1 * * *"]
)
def test_accepted_cron_forms(cron: str):
    assert _config(cron=cron).cron == cron
