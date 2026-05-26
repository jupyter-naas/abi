from naas_abi_core.engine.engine_configuration.EngineConfiguration_EmailService import (
    EmailAdapterConfiguration,
    EmailServiceConfiguration,
)
from naas_abi_core.services.email.EmailService import EmailService
from naas_abi_core.services.email.adapters.secondary.FilesystemAdapter import (
    FilesystemAdapter,
)
from naas_abi_core.services.email.adapters.secondary.SESAdapter import SESAdapter
from naas_abi_core.services.email.adapters.secondary.SMTPAdapter import SMTPAdapter


def test_email_service_configuration_smtp_adapter():
    configuration = EmailServiceConfiguration(
        email_adapter=EmailAdapterConfiguration(
            adapter="smtp",
            config={
                "host": "smtp.example.com",
                "port": 587,
                "username": "username",
                "password": "password",
                "use_tls": True,
            },
        )
    )

    adapter = configuration.email_adapter.load()
    assert isinstance(adapter, SMTPAdapter)
    assert isinstance(configuration.load(), EmailService)


def test_email_service_configuration_filesystem_adapter(tmp_path):
    configuration = EmailServiceConfiguration(
        email_adapter=EmailAdapterConfiguration(
            adapter="filesystem",
            config={"directory": str(tmp_path)},
        )
    )

    adapter = configuration.email_adapter.load()
    assert isinstance(adapter, FilesystemAdapter)
    assert isinstance(configuration.load(), EmailService)


def test_email_service_configuration_ses_adapter():
    configuration = EmailServiceConfiguration(
        email_adapter=EmailAdapterConfiguration(
            adapter="ses",
            config={
                "region_name": "us-east-1",
            },
        )
    )

    adapter = configuration.email_adapter.load()
    assert isinstance(adapter, SESAdapter)
    assert isinstance(configuration.load(), EmailService)


def test_email_service_configuration_ses_adapter_with_explicit_credentials():
    configuration = EmailServiceConfiguration(
        email_adapter=EmailAdapterConfiguration(
            adapter="ses",
            config={
                "region_name": "eu-west-1",
                "aws_access_key_id": "AKIA...",
                "aws_secret_access_key": "secret",
                "aws_session_token": "token",
            },
        )
    )

    adapter = configuration.email_adapter.load()
    assert isinstance(adapter, SESAdapter)


def test_email_service_configuration_ses_adapter_defaults_to_iam_role():
    # No credentials supplied -> boto3 default chain (env, profile, EC2 IAM role).
    configuration = EmailServiceConfiguration(
        email_adapter=EmailAdapterConfiguration(
            adapter="ses",
            config={},
        )
    )

    adapter = configuration.email_adapter.load()
    assert isinstance(adapter, SESAdapter)
