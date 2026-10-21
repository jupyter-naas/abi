from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class EmailAttachment:
    filename: str
    content: bytes
    mime_type: str
    # Set both to embed the attachment inline in the HTML body. ``content_id``
    # is the value referenced from the HTML as ``<img src="cid:...">`` and
    # ``is_inline`` marks the attachment as inline rather than a download.
    content_id: str | None = None
    is_inline: bool = False


def resolve_recipients(
    to_email: str | list[str] | None = None,
    to_emails: list[str] | str | None = None,
) -> list[str]:
    """Normalize ``to_email`` and/or ``to_emails`` into an ordered recipient list.

    Either argument may be a single address, a comma-separated string, or a list
    of those. Both are accepted together; addresses are trimmed and de-duplicated
    while preserving first-seen order. Raises ``ValueError`` when no address is
    found so callers never silently send to nobody.
    """

    seen: set[str] = set()
    recipients: list[str] = []
    for value in (to_email, to_emails):
        if value is None:
            continue
        parts = [value] if isinstance(value, str) else value
        for part in parts:
            for address in part.split(","):
                cleaned = address.strip()
                if cleaned and cleaned not in seen:
                    seen.add(cleaned)
                    recipients.append(cleaned)
    if not recipients:
        raise ValueError("At least one recipient is required (to_email/to_emails).")
    return recipients


class SentEmailsNotKept(NotImplementedError):
    """The adapter hands mail off without keeping a copy (SMTP, SES, ...)."""


class SentEmailNotFound(Exception):
    pass


@dataclass(frozen=True)
class SentEmailSummary:
    """A kept copy of a sent message, as listed."""

    message_id: str
    sent_at: str  # ISO 8601
    size: int  # bytes of the RFC 5322 message
    subject: str
    to: str
    sender: str
    # The start of the text body on one line (HTML without tags when there is
    # no text part); empty when the adapter does not read bodies to list.
    snippet: str = ""


@dataclass(frozen=True)
class SentEmail:
    summary: SentEmailSummary
    raw: bytes  # the whole RFC 5322 message (.eml)


class IEmailAdapter(ABC):
    """Sends mail. ``send`` returns the id of the kept copy, or ``None``.

    Keeping sent mail is optional: the filesystem adapter keeps every message
    and implements ``list_sent`` / ``get_sent`` / ``delete_sent``; adapters
    that hand mail to a provider (SMTP, SES, SendGrid, Outlook) keep nothing,
    and those methods raise ``SentEmailsNotKept``. Deleting a kept copy never
    recalls the message.
    """

    @abstractmethod
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
        raise NotImplementedError()

    def list_sent(
        self, *, limit: int = 100, before: str | None = None
    ) -> list[SentEmailSummary]:
        """Kept messages, newest first; ``before`` continues after a message id."""
        raise SentEmailsNotKept(f"{type(self).__name__} keeps no sent mail")

    def get_sent(self, message_id: str) -> SentEmail:
        """One kept message; ``SentEmailNotFound`` if there is none with this id."""
        raise SentEmailsNotKept(f"{type(self).__name__} keeps no sent mail")

    def delete_sent(self, message_id: str) -> None:
        """Delete a kept copy (the message itself is not recalled)."""
        raise SentEmailsNotKept(f"{type(self).__name__} keeps no sent mail")
