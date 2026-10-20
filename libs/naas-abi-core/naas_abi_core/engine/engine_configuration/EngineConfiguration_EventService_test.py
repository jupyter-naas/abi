import pytest
from naas_abi_core.engine.engine_configuration.EngineConfiguration_EventService import (
    EventAdapterConfiguration,
)
from pydantic import ValidationError

DSN = "postgresql://abi:secret-password@db:5432/abi"


def test_a_postgresql_event_log_is_built_from_its_settings(monkeypatch):
    built = {}

    class FakeAdapter:
        def __init__(self, **kwargs):
            built.update(kwargs)

    monkeypatch.setattr(
        "naas_abi_core.services.event.adapters.secondary.EventPostgreSQLAdapter."
        "EventPostgreSQLAdapter",
        FakeAdapter,
    )
    config = EventAdapterConfiguration(
        adapter="postgresql", config={"dsn": DSN, "schema": "events_prod"}
    )

    config.load()

    assert built["dsn"] == DSN
    assert built["schema"] == "events_prod"
    assert built["pool_max_size"] == 10


def test_a_postgresql_event_log_is_shared_storage():
    config = EventAdapterConfiguration(adapter="postgresql", config={"dsn": DSN})

    assert config.local_storage() is None


@pytest.mark.parametrize(
    "settings", [{"dsn": ""}, {"dsn": DSN, "schema": "Bad-Schema"}, {}]
)
def test_invalid_postgresql_settings_are_refused(settings):
    with pytest.raises((ValidationError, AssertionError, ValueError)):
        EventAdapterConfiguration(adapter="postgresql", config=settings)


def test_the_dsn_never_appears_in_errors_or_repr():
    config = EventAdapterConfiguration(adapter="postgresql", config={"dsn": DSN})
    assert "secret-password" not in repr(config)

    with pytest.raises(Exception) as raised:
        EventAdapterConfiguration(
            adapter="postgresql", config={"dsn": DSN, "schema": "Bad-Schema"}
        )
    assert "secret-password" not in str(raised.value)


def test_events_are_archived_after_seven_days_by_default(monkeypatch):
    built = {}

    class FakeAdapter:
        def __init__(self, **kwargs):
            built.update(kwargs)

    monkeypatch.setattr(
        "naas_abi_core.services.event.adapters.secondary.EventPostgreSQLAdapter."
        "EventPostgreSQLAdapter",
        FakeAdapter,
    )
    EventAdapterConfiguration(adapter="postgresql", config={"dsn": DSN}).load()
    assert (built["archive_after_days"], built["archive_batch_rows"]) == (7, 10_000)

    EventAdapterConfiguration(
        adapter="postgresql", config={"dsn": DSN, "archive_after_days": None}
    ).load()
    assert built["archive_after_days"] is None


@pytest.mark.parametrize(
    "archive", [{"archive_after_days": 0}, {"archive_batch_rows": 0}]
)
def test_invalid_archive_settings_are_refused(archive):
    with pytest.raises((ValidationError, ValueError)):
        EventAdapterConfiguration(adapter="postgresql", config={"dsn": DSN, **archive})
