import pytest
from naas_abi import secret
from naas_abi_core import logger
from naas_abi_marketplace.applications.sendgrid.integrations.SendGridIntegration import (
    SendGridIntegration,
    SendGridIntegrationConfiguration,
)


@pytest.fixture
def integration() -> SendGridIntegration:
    configuration = SendGridIntegrationConfiguration(
        api_key=secret.get("SENDGRID_API_KEY"),
    )
    return SendGridIntegration(configuration)


def test_send_email(integration: SendGridIntegration):
    from_email = "notifications@naas.ai"
    to_emails = ["florent.frvservices@gmail.com"]
    subject = "ABI - Asgard Group"
    html_content = """
    <h1>ABI - Atelier de développement</h1>
    <p>Bonjour,</p>
    <p>Nous vous invitons à participer à l'atelier de développement de la semaine prochaine.</p>
    <p>Cordialement,</p>
    <p>L'équipe ABI</p>
    """
    response = integration.send_email(
        from_email=from_email,
        to_emails=to_emails,
        subject=subject,
        html_content=html_content,
    )
    logger.info(response)
