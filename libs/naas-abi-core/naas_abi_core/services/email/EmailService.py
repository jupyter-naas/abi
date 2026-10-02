from __future__ import annotations

from naas_abi_core import logger
from naas_abi_core.services.email.EmailPorts import (
    EmailAttachment,
    IEmailAdapter,
    SentEmail,
    SentEmailSummary,
    resolve_recipients,
)
from naas_abi_core.services.email.ontologies.modules.EmailEventOntology import (
    EmailError,
    EmailSent,
)
from naas_abi_core.services.ServiceBase import ServiceBase


class EmailService(ServiceBase):
    def __init__(self, adapter: IEmailAdapter):
        super().__init__()
        self._adapter = adapter

    @property
    def adapter(self) -> IEmailAdapter:
        """The wrapped secondary adapter -- public so callers (e.g.
        ``EngineNATSLoader``) can check what kind of adapter this service is
        backed by, mirroring ``ObjectStorageService.adapter``."""
        return self._adapter

    def __publish_event(self, event: object) -> None:
        if not self.services_wired:
            return
        if not self.services.events_available():
            return
        try:
            self.services.events.publish(event)
        except Exception as exc:  # noqa: BLE001
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
        cc_emails: list[str] | str | None = None,
    ) -> str | None:
        """Send; returns the id of the kept copy when the adapter keeps one."""
        recipients = ", ".join(resolve_recipients(to_email, to_emails))
        cc_recipients = (
            ", ".join(resolve_recipients(None, cc_emails)) if cc_emails else ""
        )
        display_recipients = (
            f"{recipients}; cc: {cc_recipients}" if cc_recipients else recipients
        )
        try:
            message_id = self._adapter.send(
                to_email=to_email,
                subject=subject,
                text_body=text_body,
                html_body=html_body,
                from_email=from_email,
                from_name=from_name,
                reply_to=reply_to,
                attachments=attachments,
                to_emails=to_emails,
                cc_emails=cc_emails,
            )
        except Exception as exc:
            self.__publish_event(
                EmailError(to=display_recipients, subject=subject, message=str(exc))
            )
            raise
        self.__publish_event(
            EmailSent(to=display_recipients, subject=subject, sender=from_email)
        )
        return message_id

    def list_sent(
        self, *, limit: int = 100, before: str | None = None
    ) -> list[SentEmailSummary]:
        """Kept sent mail, newest first. ``SentEmailsNotKept`` if the adapter keeps none."""
        return self._adapter.list_sent(limit=limit, before=before)

    def get_sent(self, message_id: str) -> SentEmail:
        return self._adapter.get_sent(message_id)

    def delete_sent(self, message_id: str) -> None:
        self._adapter.delete_sent(message_id)
