from __future__ import annotations

import pytest
from naas_abi.apps.nexus.apps.api.app.core.secret_key import (
    INSECURE_SECRET_KEYS,
    LEGACY_SECRET_KEY_NAME,
    SECRETS_KEY_NAME,
    is_insecure_secret_key,
    legacy_secret_keys,
    resolve_secrets_key,
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


def test_configured_key_is_kept_and_nothing_is_written() -> None:
    store = FakeSecretStore()

    assert resolve_secrets_key("configured-key", store) == "configured-key"
    assert store.writes == []


def test_stored_key_is_used_when_none_is_configured() -> None:
    store = FakeSecretStore({SECRETS_KEY_NAME: "stored-key"})

    assert resolve_secrets_key("", store) == "stored-key"
    assert store.writes == []


def test_key_is_generated_and_persisted_when_none_is_configured() -> None:
    store = FakeSecretStore()

    key = resolve_secrets_key("", store)

    assert not is_insecure_secret_key(key)
    assert len(key) >= 64
    assert store.values == {SECRETS_KEY_NAME: key}


def test_a_default_is_never_a_secrets_key() -> None:
    store = FakeSecretStore({SECRETS_KEY_NAME: "change-me-in-production"})

    key = resolve_secrets_key("change-me-in-production", store)

    assert not is_insecure_secret_key(key)
    assert store.values[SECRETS_KEY_NAME] == key


def test_the_secrets_key_is_not_the_old_signing_key() -> None:
    # A deployment that had a SECRET_KEY keeps it apart: its secrets move to a key of their own.
    store = FakeSecretStore({LEGACY_SECRET_KEY_NAME: "the-old-signing-key"})

    key = resolve_secrets_key("", store)

    assert key != "the-old-signing-key"
    assert store.values[SECRETS_KEY_NAME] == key
    assert store.values[LEGACY_SECRET_KEY_NAME] == "the-old-signing-key"


def test_boot_fails_when_the_generated_key_cannot_be_persisted() -> None:
    # A key that only lives in memory would orphan every secret encrypted
    # under it on the next restart.
    store = FakeSecretStore(persist=False)

    with pytest.raises(RuntimeError, match=SECRETS_KEY_NAME):
        resolve_secrets_key("", store)


def test_the_keys_old_data_may_still_be_under_are_the_configured_stored_and_default_ones() -> None:
    store = FakeSecretStore({LEGACY_SECRET_KEY_NAME: "stored-old"})

    keys = legacy_secret_keys("configured-old", store)

    assert keys[:2] == ["configured-old", "stored-old"]
    assert set(INSECURE_SECRET_KEYS - {""}) <= set(keys)
    assert "" not in keys
    assert len(keys) == len(set(keys))


def test_without_a_legacy_key_only_the_published_defaults_remain() -> None:
    keys = legacy_secret_keys("", FakeSecretStore())

    assert set(keys) == set(INSECURE_SECRET_KEYS - {""})
