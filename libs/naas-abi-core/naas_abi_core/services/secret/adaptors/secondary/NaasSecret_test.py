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


def test_naas_secret_keeps_its_api_key_out_of_errors_and_logs(monkeypatch):
    import requests
    from naas_abi_core import logger
    from naas_abi_core.services.secret.adaptors.secondary.NaasSecret import NaasSecret
    from naas_abi_core.services.secret.SecretPorts import SecretAuthenticationError

    api_key = "naas-api-key-under-test"

    def refused(*args, **kwargs):
        response = requests.Response()
        response.status_code = 401
        response.url = args[0] if args else ""
        return response

    monkeypatch.setattr(requests, "get", refused)
    logged: list[str] = []
    sink = logger.add(lambda message: logged.append(str(message)), level="DEBUG")
    try:
        with pytest.raises(SecretAuthenticationError) as raised:
            NaasSecret(api_key, "https://secrets.example").get("mod/token")
    finally:
        logger.remove(sink)

    assert api_key not in str(raised.value)
    assert "https://secrets.example" in str(raised.value)
    assert logged and not any(api_key in line for line in logged)
