from __future__ import annotations

from naas_abi_core import logger
from naas_abi_core.services.ServiceBase import ServiceBase
from naas_abi_core.services.email.EmailPorts import (
    EmailAttachment,
    IEmailAdapter,
    resolve_recipients,
)
from naas_abi_core.services.email.ontologies.modules.EmailEventOntology import (
    EmailError,
    EmailSent,
)


class EmailService(ServiceBase):
    def __init__(self, adapter: IEmailAdapter):
        super().__init__()
        self._adapter = adapter

    def __publish_event(self, event: object) -> None:
        if not self.services_wired:
            return
        if not self.services.events_available():
            return
        try:
            self.services.events.publish(event)
        except Exception as exc:
            # Send is the source of truth; event logging must never break it.
            logger.warning(f"EmailService: failed to publish event: {exc}")

    def send(
        self,
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
    ) -> None:
        recipients = ", ".join(resolve_recipients(to_email, to_emails))
        try:
            self._adapter.send(
                to_email=to_email,
                subject=subject,
                text_body=text_body,
                html_body=html_body,
                from_email=from_email,
                from_name=from_name,
                reply_to=reply_to,
                attachments=attachments,
                to_emails=to_emails,
            )
        except Exception as exc:
            self.__publish_event(
                EmailError(to=recipients, subject=subject, message=str(exc))
            )
            raise
        self.__publish_event(
            EmailSent(to=recipients, subject=subject, sender=from_email)
        )
