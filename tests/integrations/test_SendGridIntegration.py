from src.core.integrations.SendGridIntegration import SendGridIntegration, SendGridIntegrationConfiguration
from abi import logger
from src import secret

# Initialize configuration
configuration = SendGridIntegrationConfiguration(
    api_key=secret.get("SENDGRID_API_KEY"),
)

# Initialize integration
sendgrid = SendGridIntegration(configuration)

# Create a test email
email_data = {
    "from_email": "notifications@naas.ai",
    "to_emails": ["florent@naas.ai"],
    "subject": "Test Email",
    "html_content": "<p>This is a test email from SendGrid Integration</p>",
    "plain_text_content": "This is a test email from SendGrid Integration"
}

# Send email
response = sendgrid.send_email(
    from_email=email_data["from_email"],
    to_emails=email_data["to_emails"],
    subject=email_data["subject"],
    html_content=email_data["html_content"],
    plain_text_content=email_data["plain_text_content"]
)

# Log the response
logger.info(f"Email sent with response: {response}") 