from naas_abi_core.engine.engine_configuration.EngineConfiguration_SecretService import (
    DotenvSecretConfiguration,
    NaasSecretConfiguration,
    SecretAdapterConfiguration,
    SecretServiceConfiguration,
)
from naas_abi_core.services.secret.Secret import Secret
from naas_abi_core.services.secret.SecretPorts import ISecretAdapter


def test_secret_service_configuration():
    from naas_abi_core.services.secret.adaptors.secondary.dotenv_secret_secondaryadaptor import (
        DotenvSecretSecondaryAdaptor,
    )

    configuration = SecretServiceConfiguration(
        secret_adapters=[
            SecretAdapterConfiguration(
                adapter="dotenv", config=DotenvSecretConfiguration()
            )
        ]
    )
    assert configuration.secret_adapters is not None
    assert len(configuration.secret_adapters) == 1

    secret_adapter = configuration.secret_adapters[0].load()

    assert secret_adapter is not None
    assert isinstance(secret_adapter, ISecretAdapter)
    assert isinstance(secret_adapter, DotenvSecretSecondaryAdaptor)
    assert secret_adapter.path == ".env"

    secret_service = configuration.load()

    assert secret_service is not None
    assert isinstance(secret_service, Secret)


def test_secret_service_configuration_dotenv_custom_path(tmp_path, monkeypatch):
    from naas_abi_core.services.secret.adaptors.secondary.dotenv_secret_secondaryadaptor import (
        DotenvSecretSecondaryAdaptor,
    )

    (tmp_path / ".env.remote").write_text("ENV=remote\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    configuration = SecretServiceConfiguration(
        secret_adapters=[
            SecretAdapterConfiguration(
                adapter="dotenv",
                config=DotenvSecretConfiguration(path=".env.remote"),
            )
        ]
    )

    secret_adapter = configuration.secret_adapters[0].load()

    assert isinstance(secret_adapter, DotenvSecretSecondaryAdaptor)
    assert secret_adapter.path == ".env.remote"


def test_secret_service_configuration_dotenv_missing_file():
    import pytest

    configuration = SecretServiceConfiguration(
        secret_adapters=[
            SecretAdapterConfiguration(
                adapter="dotenv",
                config=DotenvSecretConfiguration(path=".env.this-file-does-not-exist"),
            )
        ]
    )

    with pytest.raises(FileNotFoundError):
        configuration.secret_adapters[0].load()


def test_secret_service_configuration_naas():
    import os

    from dotenv import load_dotenv
    from naas_abi_core.services.secret.adaptors.secondary.NaasSecret import (
        NaasSecret,
    )

    load_dotenv()

    naas_api_key = os.getenv("NAAS_API_KEY")
    if naas_api_key is None:
        raise ValueError("NAAS_API_KEY is not set")

    naas_api_url = os.getenv("NAAS_API_URL")
    if naas_api_url is None:
        raise ValueError("NAAS_API_URL is not set")

    configuration = SecretServiceConfiguration(
        secret_adapters=[
            SecretAdapterConfiguration(
                adapter="naas",
                config=NaasSecretConfiguration(
                    naas_api_key=naas_api_key,
                    naas_api_url=naas_api_url,
                ),
            )
        ]
    )
    assert configuration.secret_adapters is not None
    assert len(configuration.secret_adapters) == 1

    secret_adapter = configuration.secret_adapters[0].load()

    assert secret_adapter is not None
    assert isinstance(secret_adapter, ISecretAdapter)
    assert isinstance(secret_adapter, NaasSecret)
