from __future__ import annotations

from naas_abi_core.services.email.EmailPorts import (
    EmailAttachment,
    IEmailAdapter,
    SentEmail,
    SentEmailNotFound,
    SentEmailSummary,
    resolve_recipients,
)
from naas_abi_core.services.email.iam_catalog import CATALOG, DEFAULT_SENDER
from naas_abi_core.services.email.ontologies.modules.EmailEventOntology import (
    EmailError,
    EmailSent,
)
from naas_abi_core.services.iam.guard import ServiceGuard
from naas_abi_core.services.ServiceBase import ServiceBase


def _not_found(message_id: str):
    return lambda: SentEmailNotFound(f"No sent email with id {message_id}")


class EmailService(ServiceBase):
    """Sends mail and reads kept copies, each operation authorized (``email:*``).

    A send is checked on its sender (``sender/<from address>``); the copy it
    keeps is placed in the container of the call. Wired with IAM, it checks
    every call; a facade over NATS is not, and the owner it calls checks.
    """

    def __init__(self, adapter: IEmailAdapter):
        super().__init__()
        self._adapter = adapter
        self._guard = ServiceGuard.of(CATALOG, self)

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
        # Send is the source of truth; emit never raises.
        self.services.events.emit(event)

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
        self._guard.require("Send", "sender", from_email or DEFAULT_SENDER)
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
        if message_id is not None:
            self._guard.place_new("message", message_id)
        self.__publish_event(
            EmailSent(to=display_recipients, subject=subject, sender=from_email)
        )
        return message_id

    def list_sent(
        self, *, limit: int = 100, before: str | None = None
    ) -> list[SentEmailSummary]:
        """Kept sent mail the caller may list, newest first; ``limit`` applies
        after filtering. ``SentEmailsNotKept`` if the adapter keeps none."""
        if not self._guard.enforcing:
            return self._adapter.list_sent(limit=limit, before=before)
        kept: list[SentEmailSummary] = []
        cursor = before
        while len(kept) < limit:
            page = self._adapter.list_sent(limit=limit, before=cursor)
            kept += self._guard.filter(
                "ListSent", "message", page, lambda s: s.message_id
            )
            if len(page) < limit:
                break
            cursor = page[-1].message_id
        return kept[:limit]

    def get_sent(self, message_id: str) -> SentEmail:
        self._guard.require(
            "GetSent", "message", message_id, not_found=_not_found(message_id)
        )
        return self._adapter.get_sent(message_id)

    def delete_sent(self, message_id: str) -> None:
        self._guard.require(
            "DeleteSent", "message", message_id, not_found=_not_found(message_id)
        )
        self._adapter.delete_sent(message_id)
        self._guard.forget("message", message_id)
