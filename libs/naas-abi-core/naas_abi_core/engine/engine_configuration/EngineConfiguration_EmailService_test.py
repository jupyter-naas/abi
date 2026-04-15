from naas_abi_core.engine.engine_configuration.EngineConfiguration_EmailService import (
    EmailAdapterConfiguration,
    EmailServiceConfiguration,
)
from naas_abi_core.services.email.EmailService import EmailService
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
