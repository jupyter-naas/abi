import os
import uuid

import pytest
from dotenv import load_dotenv


@pytest.fixture
def base64_secret_naas():
    from naas_abi_core.services.secret.adaptors.secondary.Base64Secret import (
        Base64Secret,
    )
    from naas_abi_core.services.secret.adaptors.secondary.NaasSecret import NaasSecret

    load_dotenv()

    naas_api_key = os.getenv("NAAS_API_KEY")
    if naas_api_key is None:
        pytest.skip("NAAS_API_KEY is not set")

    naas_secret = NaasSecret(naas_api_key, os.getenv("NAAS_API_URL"))
    base64_secret_key = str(uuid.uuid4())
    return Base64Secret(naas_secret, base64_secret_key), naas_secret, base64_secret_key


def test_base64_secret(base64_secret_naas):
    base64_secret_naas, naas_secret, base64_secret_key = base64_secret_naas
    base64_secret_naas.set("test", "test")
    assert base64_secret_naas.get("test") == "test"
    assert base64_secret_naas.list() == {"test": "test"}
    base64_secret_naas.remove("test")
    assert base64_secret_naas.get("test") is None
    assert base64_secret_naas.list() == {}
    base64_secret_naas.set("test", "test")
    assert base64_secret_naas.get("test") == "test"
    assert base64_secret_naas.list() == {"test": "test"}
    base64_secret_naas.remove("test")

    naas_secret.remove(base64_secret_key)


class _MemorySecrets:
    """A backend that keeps text as written, like a remote secret store."""

    def __init__(self):
        self.values: dict[str, str] = {}

    def get(self, key, default=None):
        return self.values.get(key, default)

    def set(self, key, value):
        self.values[key] = value

    def remove(self, key):
        self.values.pop(key, None)

    def list(self):
        return dict(self.values)


@pytest.fixture
def bundle():
    from naas_abi_core.services.secret.adaptors.secondary.Base64Secret import (
        Base64Secret,
    )

    return Base64Secret(_MemorySecrets(), "BUNDLE")


@pytest.mark.parametrize(
    "value",
    [
        'a"b',
        "a'b",
        "back\\slash",
        "ends with backslash\\",
        "line\nbreak",
        "carriage\rreturn",
        "tab\there",
        'a"\nNATS_JWT_SECRET="attacker',
        "${ENGINE_ONLY}",
        "$ENGINE_ONLY",
        "# not a comment",
        "",
    ],
)
def test_a_value_round_trips_and_adds_no_key(bundle, monkeypatch, value):
    monkeypatch.setenv("ENGINE_ONLY", "engine-only-value")
    bundle.set("FIRST", "1")

    bundle.set("MOD_STATE", value)

    assert bundle.get("MOD_STATE") == value
    assert bundle.list() == {"FIRST": "1", "MOD_STATE": value}
    bundle.remove("FIRST")
    assert bundle.list() == {"MOD_STATE": value}


def test_a_bundle_never_interpolates_a_value_from_the_environment(bundle, monkeypatch):
    monkeypatch.setenv("ENGINE_ONLY", "engine-only-value")
    bundle.set("EARLIER", "first")
    bundle.set("MOD_STATE", "${EARLIER}-${ENGINE_ONLY}")

    assert bundle.get("MOD_STATE") == "${EARLIER}-${ENGINE_ONLY}"


@pytest.mark.parametrize("key", ["A B", "A=B", 'A"', "A\nB", "A#", "$A", ""])
def test_a_key_that_cannot_be_stored_as_one_is_refused(bundle, key):
    bundle.set("KEPT", "1")

    with pytest.raises(ValueError):
        bundle.set(key, "value")

    assert bundle.list() == {"KEPT": "1"}
