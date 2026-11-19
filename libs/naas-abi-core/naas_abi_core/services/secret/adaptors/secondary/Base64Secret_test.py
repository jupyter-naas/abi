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


class _MemorySecret:
    """The adapter the blob lives in."""

    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    def get(self, key, default=None):
        return self.values.get(key, default)

    def set(self, key, value):
        self.values[key] = value

    def remove(self, key):
        self.values.pop(key, None)

    def list(self):
        return dict(self.values)


def _base64_secret():
    from naas_abi_core.services.secret.adaptors.secondary.Base64Secret import (
        Base64Secret,
    )

    backend = _MemorySecret()
    return Base64Secret(backend, "blob"), backend


def test_base64_secret_keeps_values_literal(monkeypatch):
    secrets, backend = _base64_secret()
    monkeypatch.setenv("ABI_TEST_ENGINE_VALUE", "from-the-environment")
    secrets.set("iam/signing", "sealed-value")

    secrets.set("mod/a", "${iam/signing}")
    secrets.set("mod/e", "${ABI_TEST_ENGINE_VALUE}")
    secrets.set("mod/b", 'x"\niam/signing="replaced')
    secrets.set("mod/c", "line one\nline two \\ \"quoted\" 'single' # not a comment")

    assert secrets.get("mod/a") == "${iam/signing}"
    assert secrets.get("mod/e") == "${ABI_TEST_ENGINE_VALUE}"
    assert secrets.get("iam/signing") == "sealed-value"
    assert secrets.get("mod/b") == 'x"\niam/signing="replaced'
    assert secrets.get("mod/c") == (
        "line one\nline two \\ \"quoted\" 'single' # not a comment"
    )
    assert sorted(secrets.list()) == ["iam/signing", "mod/a", "mod/b", "mod/c", "mod/e"]
    import base64
    import json

    stored = json.loads(base64.b64decode(backend.values["blob"]))
    assert stored["mod/a"] == "${iam/signing}"


def test_base64_secret_reads_older_blobs_literally(monkeypatch):
    import base64

    secrets, backend = _base64_secret()
    monkeypatch.setenv("ABI_TEST_ENGINE_VALUE", "from-the-environment")
    backend.values["blob"] = base64.b64encode(
        b'iam/signing="sealed-value"\nmod/a="${iam/signing}"\n'
        b'mod/e="${ABI_TEST_ENGINE_VALUE}"\n'
    ).decode()

    assert secrets.get("iam/signing") == "sealed-value"
    assert secrets.get("mod/a") == "${iam/signing}"
    assert secrets.get("mod/e") == "${ABI_TEST_ENGINE_VALUE}"

    secrets.set("mod/new", "v")  # the next write stores JSON
    assert base64.b64decode(backend.values["blob"]).startswith(b"{")
    assert secrets.get("mod/a") == "${iam/signing}"
