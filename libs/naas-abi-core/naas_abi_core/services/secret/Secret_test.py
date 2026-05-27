# mypy: disable-error-code="arg-type,misc"
from typing import Any, Dict

import pytest
from naas_abi_core.services.secret.Secret import Secret
from naas_abi_core.services.secret.SecretPorts import ISecretAdapter
from naas_abi_core.services.secret.ontologies.modules.SecretEventOntology import (
    SecretError,
    SecretRemoved,
    SecretSet,
)


@pytest.fixture
def TestSecretAdapter():
    class TestSecretAdapter(ISecretAdapter):
        def __init__(self, secrets: Dict[str, str | None]):
            self.secrets = secrets or {}

        def get(self, key: str, default: Any = None) -> str | Any | None:
            return self.secrets.get(key, default)

        def set(self, key: str, value: str):
            self.secrets[key] = value

        def remove(self, key: str):
            self.secrets.pop(key, None)

        def list(self) -> Dict[str, str | None]:
            return self.secrets

    return TestSecretAdapter


def test_secret(TestSecretAdapter):
    secret = Secret(
        [
            TestSecretAdapter(
                {
                    "hello": "world",
                }
            ),
            TestSecretAdapter(
                {
                    "hello": "abi",
                    "second": "second",
                }
            ),
        ]
    )

    assert secret.get("hello") == "world"
    assert secret.list() == {
        "hello": "world",
        "second": "second",
    }

    secret.remove("hello")
    assert secret.get("hello") is None
    assert secret.list() == {
        "second": "second",
    }

    secret.remove("second")
    assert secret.list() == {}

    secret.set("hello", "world")
    assert secret.get("hello") == "world"
    assert secret.list() == {
        "hello": "world",
    }


# ---------------------------------------------------------------------------
# Event emission
# ---------------------------------------------------------------------------


SECRET_VALUE = "super-sensitive-token-do-not-leak"


class _FakeEventService:
    def __init__(self) -> None:
        self.published: list = []

    def publish(self, event) -> None:
        self.published.append(event)


class _FakeServices:
    def __init__(self, events=None) -> None:
        self._events = events

    def events_available(self) -> bool:
        return self._events is not None

    @property
    def events(self):
        assert self._events is not None
        return self._events


class _InMemorySecretAdapter(ISecretAdapter):
    def __init__(self) -> None:
        self.secrets: Dict[str, str | None] = {}

    def get(self, key: str, default: Any = None):
        return self.secrets.get(key, default)

    def set(self, key: str, value: str):
        self.secrets[key] = value

    def remove(self, key: str):
        self.secrets.pop(key, None)

    def list(self) -> Dict[str, str | None]:
        return self.secrets


class _BrokenSecretAdapter(ISecretAdapter):
    def get(self, key: str, default: Any = None):
        return default

    def set(self, key: str, value: str):
        raise RuntimeError("adapter set failed")

    def remove(self, key: str):
        raise RuntimeError("adapter remove failed")

    def list(self) -> Dict[str, str | None]:
        return {}


def _assert_no_value_in_event(event) -> None:
    """No event payload may contain the actual secret value."""
    dumped = event.model_dump()
    for v in dumped.values():
        if v is None:
            continue
        assert SECRET_VALUE not in str(v), (
            f"Secret value leaked in event {type(event).__name__}: {dumped}"
        )


def test_events_not_emitted_when_unwired() -> None:
    secret = Secret([_InMemorySecretAdapter()])
    secret.set("k", SECRET_VALUE)
    secret.remove("k")  # no crash even though no events service


def test_events_not_emitted_when_events_unavailable() -> None:
    secret = Secret([_InMemorySecretAdapter()])
    secret.set_services(_FakeServices(events=None))
    secret.set("k", SECRET_VALUE)
    secret.remove("k")  # must not raise


def test_set_emits_secret_set_event_without_value() -> None:
    secret = Secret([_InMemorySecretAdapter()])
    events = _FakeEventService()
    secret.set_services(_FakeServices(events))

    secret.set("API_KEY", SECRET_VALUE)

    assert len(events.published) == 1
    evt = events.published[0]
    assert isinstance(evt, SecretSet)
    assert evt.key == "API_KEY"
    _assert_no_value_in_event(evt)


def test_remove_emits_secret_removed_event() -> None:
    adapter = _InMemorySecretAdapter()
    adapter.set("API_KEY", SECRET_VALUE)
    secret = Secret([adapter])
    events = _FakeEventService()
    secret.set_services(_FakeServices(events))

    secret.remove("API_KEY")

    removed = [e for e in events.published if isinstance(e, SecretRemoved)]
    assert len(removed) == 1
    assert removed[0].key == "API_KEY"
    for e in events.published:
        _assert_no_value_in_event(e)


def test_set_adapter_failure_emits_secret_error_and_reraises() -> None:
    secret = Secret([_BrokenSecretAdapter()])
    events = _FakeEventService()
    secret.set_services(_FakeServices(events))

    with pytest.raises(RuntimeError):
        secret.set("API_KEY", SECRET_VALUE)

    errors = [e for e in events.published if isinstance(e, SecretError)]
    sets = [e for e in events.published if isinstance(e, SecretSet)]
    assert len(errors) == 1
    assert errors[0].key == "API_KEY"
    assert errors[0].operation == "set"
    assert "adapter set failed" in (errors[0].message or "")
    assert sets == []
    for e in events.published:
        _assert_no_value_in_event(e)


def test_remove_adapter_failure_emits_secret_error_and_reraises() -> None:
    secret = Secret([_BrokenSecretAdapter()])
    events = _FakeEventService()
    secret.set_services(_FakeServices(events))

    with pytest.raises(RuntimeError):
        secret.remove("API_KEY")

    errors = [e for e in events.published if isinstance(e, SecretError)]
    removed = [e for e in events.published if isinstance(e, SecretRemoved)]
    assert len(errors) == 1
    assert errors[0].operation == "remove"
    assert removed == []


def test_publisher_exception_does_not_break_secret_ops() -> None:
    class _ExplodingEvents:
        def publish(self, event):
            raise RuntimeError("event bus down")

    adapter = _InMemorySecretAdapter()
    secret = Secret([adapter])
    secret.set_services(_FakeServices(events=_ExplodingEvents()))

    secret.set("k", SECRET_VALUE)
    assert adapter.get("k") == SECRET_VALUE
    secret.remove("k")
    assert adapter.get("k") is None
