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


class IEmailAdapter(ABC):
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
    ) -> None:
        raise NotImplementedError()
