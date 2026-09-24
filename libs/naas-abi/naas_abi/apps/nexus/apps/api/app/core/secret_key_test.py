from __future__ import annotations

import pytest
from naas_abi.apps.nexus.apps.api.app.core.secret_key import (
    SECRET_KEY_NAME,
    is_insecure_secret_key,
    resolve_secret_key,
)


class FakeSecretStore:
    def __init__(self, values: dict[str, str] | None = None, persist: bool = True):
        self.values = dict(values or {})
        self.persist = persist
        self.writes: list[tuple[str, str]] = []

    def get(self, key: str, default=None):
        return self.values.get(key, default)

    def set(self, key: str, value: str) -> None:
        self.writes.append((key, value))
        if self.persist:
            self.values[key] = value


@pytest.mark.parametrize("key", ["", "change-me-in-production", "secret", "changeme"])
def test_known_default_keys_are_insecure(key: str) -> None:
    assert is_insecure_secret_key(key)


def test_a_custom_key_is_not_flagged_even_if_short() -> None:
    # Replacing an operator's own key would orphan secrets encrypted under it.
    assert not is_insecure_secret_key("my-own-short-key")


def test_configured_secure_key_is_kept_and_nothing_is_written() -> None:
    store = FakeSecretStore()

    assert resolve_secret_key("configured-key", store) == "configured-key"
    assert store.writes == []


def test_stored_key_is_used_when_configured_key_is_the_default() -> None:
    store = FakeSecretStore({SECRET_KEY_NAME: "stored-key"})

    assert resolve_secret_key("change-me-in-production", store) == "stored-key"
    assert store.writes == []


def test_key_is_generated_and_persisted_when_none_is_configured() -> None:
    store = FakeSecretStore()

    key = resolve_secret_key("change-me-in-production", store)

    assert not is_insecure_secret_key(key)
    assert len(key) >= 64
    assert store.values[SECRET_KEY_NAME] == key


def test_an_insecure_stored_key_is_replaced() -> None:
    store = FakeSecretStore({SECRET_KEY_NAME: "change-me-in-production"})

    key = resolve_secret_key("change-me-in-production", store)

    assert not is_insecure_secret_key(key)
    assert store.values[SECRET_KEY_NAME] == key


def test_boot_fails_when_the_generated_key_cannot_be_persisted() -> None:
    # A key that only lives in memory would orphan every secret encrypted
    # under it on the next restart.
    store = FakeSecretStore(persist=False)

    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        resolve_secret_key("change-me-in-production", store)
