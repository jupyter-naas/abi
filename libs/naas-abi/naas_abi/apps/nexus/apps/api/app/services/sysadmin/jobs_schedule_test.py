from datetime import UTC, datetime, timedelta

import pytest
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.jobs import TriggerSpec
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.jobs_schedule import (
    describe,
    go_duration_seconds,
    next_cron,
    next_every,
)


def at(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=UTC)


# --- next_cron ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "expression,after,expected",
    [
        ("0 0 6 * * *", "2026-10-02T05:59:59", "2026-10-02T06:00:00"),
        ("0 0 6 * * *", "2026-10-02T06:00:00", "2026-10-03T06:00:00"),
        ("30 15 * * * *", "2026-10-02T10:20:00", "2026-10-02T11:15:30"),
        ("0 */10 * * * *", "2026-10-02T10:21:00", "2026-10-02T10:30:00"),
        ("*/15 * * * * *", "2026-10-02T10:21:01", "2026-10-02T10:21:15"),
        ("0 30 9 * * mon-fri", "2026-10-02T10:00:00", "2026-10-05T09:30:00"),  # Fri -> Mon
        ("0 0 0 1 * *", "2026-10-02T00:00:00", "2026-11-01T00:00:00"),
        ("0 0 12 * jan,jul *", "2026-10-02T00:00:00", "2027-01-01T12:00:00"),
        ("0 0 0 * * 7", "2026-10-02T00:00:00", "2026-10-04T00:00:00"),  # 7 is Sunday
        ("0 0 8-10 * * *", "2026-10-02T09:30:00", "2026-10-02T10:00:00"),
        ("0 0 0 29 2 *", "2026-10-02T00:00:00", "2028-02-29T00:00:00"),
    ],
)
def test_next_cron(expression, after, expected):
    assert next_cron(expression, "", at(after)) == at(expected)


def test_day_of_month_and_day_of_week_combine_with_or():
    # The 15th, or any Monday: Mon Oct 5 comes before Thu Oct 15.
    assert next_cron("0 0 0 15 * mon", "UTC", at("2026-10-02T00:00:00")) == at(
        "2026-10-05T00:00:00"
    )


@pytest.mark.parametrize(
    "alias,expected",
    [
        ("@hourly", "2026-10-02T11:00:00"),
        ("@daily", "2026-10-03T00:00:00"),
        ("@midnight", "2026-10-03T00:00:00"),
        ("@weekly", "2026-10-04T00:00:00"),
        ("@monthly", "2026-11-01T00:00:00"),
        ("@yearly", "2027-01-01T00:00:00"),
        ("@annually", "2027-01-01T00:00:00"),
    ],
)
def test_next_cron_aliases(alias, expected):
    assert next_cron(alias, "", at("2026-10-02T10:20:00")) == at(expected)


def test_next_cron_honours_the_time_zone():
    # 06:00 in Paris (UTC+2 in October) is 04:00 UTC.
    assert next_cron("0 0 6 * * *", "Europe/Paris", at("2026-10-02T03:00:00")) == at(
        "2026-10-02T04:00:00"
    )
    # After the switch to winter time (Oct 25), 06:00 Paris is 05:00 UTC.
    assert next_cron("0 0 6 * * *", "Europe/Paris", at("2026-10-26T00:00:00")) == at(
        "2026-10-26T05:00:00"
    )


@pytest.mark.parametrize("bad", ["", "0 0 6 * *", "0 0 25 * * *", "x * * * * *", "@sometimes"])
def test_invalid_cron_has_no_next_tick(bad):
    assert next_cron(bad, "", at("2026-10-02T00:00:00")) is None


def test_unknown_time_zone_has_no_next_tick():
    assert next_cron("0 0 6 * * *", "Mars/Olympus", at("2026-10-02T00:00:00")) is None


def test_impossible_dates_have_no_next_tick():
    assert next_cron("0 0 0 31 2 *", "", at("2026-10-02T00:00:00")) is None


# --- next_every --------------------------------------------------------------------------


def test_go_durations():
    assert go_duration_seconds("10m") == 600
    assert go_duration_seconds("1h30m") == 5400
    assert go_duration_seconds("1.5s") == 1.5
    assert go_duration_seconds("nonsense") is None


def test_next_every_is_the_last_fire_plus_the_interval():
    assert next_every("10m", at("2026-10-02T10:00:00")) == at("2026-10-02T10:10:00")
    assert next_every("10m", None) is None


def test_next_every_rolls_forward_past_now():
    last = at("2026-10-02T10:00:00")
    assert next_every("10m", last, now=at("2026-10-02T10:35:00")) == at("2026-10-02T10:40:00")


# --- describe ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "trigger,text",
    [
        (TriggerSpec("cron", "0 0 6 * * *", "UTC"), "Every day at 06:00 UTC"),
        (TriggerSpec("cron", "0 0 6 * * *", ""), "Every day at 06:00 UTC"),
        (TriggerSpec("cron", "30 0 6 * * *", ""), "Every day at 06:00:30 UTC"),
        (
            TriggerSpec("cron", "0 30 9 * * mon-fri", "Europe/Paris"),
            "At 09:30 on weekdays (Europe/Paris)",
        ),
        (TriggerSpec("cron", "0 0 10 * * 1-5", ""), "At 10:00 on weekdays UTC"),
        (TriggerSpec("cron", "0 0 10 * * sat,sun", ""), "At 10:00 on weekends UTC"),
        (TriggerSpec("cron", "0 0 8 * * mon,wed", ""), "At 08:00 on Monday and Wednesday UTC"),
        (TriggerSpec("cron", "0 15 * * * *", ""), "Every hour at :15"),
        (TriggerSpec("cron", "0 */10 * * * *", ""), "Every 10 minutes"),
        (TriggerSpec("cron", "*/30 * * * * *", ""), "Every 30 seconds"),
        (TriggerSpec("cron", "0 * * * * *", ""), "Every minute"),
        (TriggerSpec("cron", "0 0 */2 * * *", ""), "Every 2 hours"),
        (TriggerSpec("cron", "0 0 0 1 * *", ""), "On the 1st of every month at 00:00 UTC"),
        (TriggerSpec("cron", "0 0 0 22 * *", ""), "On the 22nd of every month at 00:00 UTC"),
        (TriggerSpec("cron", "0 0 0 1 1 *", ""), "Every year on Jan 1 at 00:00 UTC"),
        (TriggerSpec("cron", "@daily", ""), "Every day at 00:00 UTC"),
        (TriggerSpec("cron", "@hourly", ""), "Every hour at :00"),
        (TriggerSpec("cron", "@weekly", ""), "Every Sunday at 00:00 UTC"),
        (TriggerSpec("cron", "@monthly", ""), "On the 1st of every month at 00:00 UTC"),
        (TriggerSpec("cron", "@yearly", ""), "Every year on Jan 1 at 00:00 UTC"),
        (TriggerSpec("cron", "0 5,35 8-18 * * *", ""), "Cron 0 5,35 8-18 * * *"),
        (TriggerSpec("every", "10m"), "Every 10 minutes"),
        (TriggerSpec("every", "1h"), "Every hour"),
        (TriggerSpec("every", "2h"), "Every 2 hours"),
        (TriggerSpec("every", "1h30m"), "Every 90 minutes"),
        (TriggerSpec("every", "45s"), "Every 45 seconds"),
        (TriggerSpec("every", "24h"), "Every day"),
        (TriggerSpec("every", "1s"), "Every second"),
        (TriggerSpec("event", "evt.1a2b3c4d5e6f.>"), "On event evt.1a2b…"),
        (TriggerSpec("event", "orders.created"), "On NATS subject orders.created"),
        (TriggerSpec("other", "whatever"), "whatever"),
    ],
)
def test_describe(trigger, text):
    assert describe(trigger) == text


def test_next_cron_result_is_after_the_reference_and_in_utc():
    now = datetime.now(UTC)
    found = next_cron("*/5 * * * * *", "", now)
    assert found is not None and found > now and found.utcoffset() == timedelta(0)
