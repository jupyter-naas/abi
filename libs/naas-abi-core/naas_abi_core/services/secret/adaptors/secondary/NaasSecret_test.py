import pytest


@pytest.fixture
def naas_secret():
    import os

    from dotenv import load_dotenv
    from naas_abi_core.services.secret.adaptors.secondary.NaasSecret import NaasSecret

    load_dotenv()

    naas_api_key = os.getenv("NAAS_API_KEY")
    if naas_api_key is None:
        pytest.skip("NAAS_API_KEY is not set")

    return NaasSecret(naas_api_key, os.getenv("NAAS_API_URL"))


def test_naas_secret(naas_secret):
    naas_secret.set("test", "test")
    assert naas_secret.get("test") == "test"
    assert "test" in naas_secret.list()
    naas_secret.remove("test")
    assert naas_secret.get("test") is None
