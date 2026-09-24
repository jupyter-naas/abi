from __future__ import annotations

from types import SimpleNamespace

import pytest
from naas_abi.apps.nexus.apps.api.app.core import config
from naas_abi.apps.nexus.apps.api.app.services import secrets_crypto


@pytest.fixture
def secret_key(monkeypatch: pytest.MonkeyPatch):
    def use(key: str) -> None:
        monkeypatch.setattr(config, "settings", SimpleNamespace(secret_key=key))

    return use


def test_key_is_read_at_call_time_not_at_import(secret_key) -> None:
    secret_key("first-key")
    ciphertext = secrets_crypto.encrypt_secret_value("sk-live")

    secret_key("second-key")

    assert secrets_crypto.try_decrypt_secret_value(ciphertext) is None


def test_reencrypt_moves_a_legacy_ciphertext_to_the_current_key(secret_key) -> None:
    secret_key("change-me-in-production")
    legacy = secrets_crypto.encrypt_secret_value("sk-live")

    secret_key("new-strong-key")
    rotated = secrets_crypto.reencrypt_secret_value(legacy, ["change-me-in-production"])

    assert rotated is not None
    assert secrets_crypto.decrypt_secret_value(rotated) == "sk-live"


def test_reencrypt_leaves_current_ciphertexts_alone(secret_key) -> None:
    secret_key("new-strong-key")
    current = secrets_crypto.encrypt_secret_value("sk-live")

    assert secrets_crypto.reencrypt_secret_value(current, ["change-me-in-production"]) is None


def test_reencrypt_ignores_values_no_old_key_can_open(secret_key) -> None:
    secret_key("some-other-key")
    foreign = secrets_crypto.encrypt_secret_value("sk-live")

    secret_key("new-strong-key")

    assert secrets_crypto.reencrypt_secret_value(foreign, ["change-me-in-production"]) is None
