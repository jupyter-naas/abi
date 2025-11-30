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
