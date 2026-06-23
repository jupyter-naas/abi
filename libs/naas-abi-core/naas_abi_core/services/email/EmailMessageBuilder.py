from __future__ import annotations

from email.message import EmailMessage
from email.utils import formataddr

from naas_abi_core.services.email.EmailPorts import EmailAttachment, resolve_recipients


def build_email_message(
    *,
    to_email: str | None = None,
    subject: str,
    text_body: str,
    html_body: str | None = None,
    from_email: str,
    from_name: str | None = None,
    reply_to: str | None = None,
    attachments: list[EmailAttachment] | None = None,
    to_emails: list[str] | str | None = None,
) -> EmailMessage:
    msg = EmailMessage()
    msg["To"] = ", ".join(resolve_recipients(to_email, to_emails))
    msg["Subject"] = subject
    msg["From"] = (
        formataddr((from_name or "", from_email)) if from_name else from_email
    )
    if reply_to:
        msg["Reply-To"] = reply_to

    msg.set_content(text_body)
    if html_body:
        msg.add_alternative(html_body, subtype="html")

    for attachment in attachments or []:
        maintype, _, subtype = attachment.mime_type.partition("/")
        if not subtype:
            maintype, subtype = "application", "octet-stream"
        msg.add_attachment(
            attachment.content,
            maintype=maintype,
            subtype=subtype,
            filename=attachment.filename,
        )

    return msg
