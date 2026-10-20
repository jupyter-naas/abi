import asyncio
import os

import pytest
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.secret_resources import (
    SecretResources,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.contracts import (
    ServiceResourcesContract,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.resources import (
    InvalidResource,
    ResourceNotFound,
    UnsupportedOperation,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.tests import fixtures
from naas_abi_core.services.secret.adaptors.secondary.dotenv_secret_secondaryadaptor import (
    DotenvSecretSecondaryAdaptor,
)
from naas_abi_core.services.secret.Secret import Secret
from naas_abi_core.services.secret.SecretPorts import ISecretAdapter


class DictSecrets(ISecretAdapter):
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


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch):
    # The dotenv adapter mirrors writes into os.environ.
    monkeypatch.setattr(os, "environ", os.environ.copy())


@pytest.fixture
def dotenv(tmp_path):
    path = tmp_path / ".env"
    path.write_text("".join(f"{k}={v.decode()}\n" for k, v in fixtures.SEED_ITEMS.items()))
    return DotenvSecretSecondaryAdaptor(str(path))


class TestSecretResourcesOnDotenv(ServiceResourcesContract):
    masked = True

    @pytest.fixture
    def resources(self, dotenv):
        return SecretResources(Secret([dotenv]))


def test_environment_variables_are_not_secrets(dotenv, monkeypatch):
    monkeypatch.setitem(os.environ, "HOME_LIKE_VARIABLE", "/home/someone")
    resources = SecretResources(Secret([dotenv]))

    with pytest.raises(ResourceNotFound):
        asyncio.run(resources.stat("HOME_LIKE_VARIABLE"))
    names = {e.name for e in asyncio.run(resources.list()).entries}
    assert "HOME_LIKE_VARIABLE" not in names


def test_listing_and_reading_never_carry_values(dotenv):
    resources = SecretResources(Secret([dotenv]))

    page = asyncio.run(resources.list())
    detail = asyncio.run(resources.read("alpha"))

    for value in fixtures.SEED_ITEMS.values():
        assert value.decode() not in repr(page) + repr(detail)
    assert all(e.size is None for e in page.entries)


def test_writes_reach_every_adapter(dotenv, tmp_path):
    other = DictSecrets()
    resources = SecretResources(Secret([dotenv, other]))

    asyncio.run(resources.write("NEW_KEY", b"multi\nline"))

    assert other.values["NEW_KEY"] == "multi\nline"
    assert "NEW_KEY" in (tmp_path / ".env").read_text()


@pytest.mark.parametrize("bad", ["", "BAD KEY", "A=B", "1STARTS_WITH_DIGIT", "new\nline"])
def test_invalid_names_are_rejected(dotenv, bad):
    with pytest.raises(InvalidResource):
        asyncio.run(SecretResources(Secret([dotenv])).write(bad, b"v"))


def test_values_must_be_text_and_cannot_be_downloaded(dotenv):
    resources = SecretResources(Secret([dotenv]))

    with pytest.raises(InvalidResource):
        asyncio.run(resources.write("BINARY", b"\xff\xfe"))
    with pytest.raises(UnsupportedOperation):
        asyncio.run(resources.download("alpha", max_bytes=100))
