"""Email: send a message, and browse the sent mail the adapter keeps.

Wraps the engine's ``EmailService`` (sync; calls run in a worker thread).

- Create = send. The value is a JSON message (``WRITE_FORMAT``); the id typed
  for it is only a label. When the adapter keeps a copy (filesystem adapter),
  the entry returned is that copy; otherwise the message is sent and nothing
  can be read back (an entry with no actions).
- Sent mail is listed newest first (each row summarized by the start of its
  body, the adapter's ``snippet``), read as headers plus the text body, and
  downloaded as the raw ``.eml``. Deleting removes the kept copy only; the
  message is not recalled. There is no replace: a sent message is final.
- Adapters that keep nothing (SMTP, SES, SendGrid, Outlook) list nothing: the
  listing is an empty page (``keeps_mail`` is false), so the web shows its
  "sent mail is not kept" empty state; sending still works.
"""

from __future__ import annotations

import asyncio
import email
import json
from email.message import EmailMessage
from email.policy import default as default_policy
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.sysadmin.resources import (
    Action,
    InvalidResource,
    ResourceCapabilities,
    ResourceDetail,
    ResourceEntry,
    ResourceNotFound,
    ResourcePage,
    ResourceTooLarge,
    UnsupportedOperation,
    text_preview,
)
from naas_abi_core import logger
from naas_abi_core.services.email.EmailPorts import SentEmailNotFound, SentEmailsNotKept

SERVICE = "email"
KEPT_ACTIONS: tuple[Action, ...] = ("read", "download", "delete")
WRITE_FORMAT = (
    'JSON message: {"to": "a@example.com" or [...], "subject": "...", "text": "...", '
    '"html": "...", "cc": [...], "reply_to": "...", "from": "...", "from_name": "..."}. '
    "Saving sends it."
)


def _keeps_mail(service: Any) -> bool:
    try:
        service.list_sent(limit=1)
    except SentEmailsNotKept:
        return False
    except Exception as exc:  # noqa: BLE001 - decide from the adapter, not a transient error
        logger.warning(f"sysadmin email: could not probe kept mail: {type(exc).__name__}")
    return True


def _render(raw: bytes) -> str:
    message = email.message_from_bytes(raw, policy=default_policy)
    lines = [
        f"{header}: {message[header]}"
        for header in ("From", "To", "Cc", "Reply-To", "Subject", "Date")
        if message[header]
    ]
    body = ""
    if isinstance(message, EmailMessage):
        part = message.get_body(preferencelist=("plain", "html"))
        if part is not None:
            body = str(part.get_content())
    attachments = [
        f"- {a.get_filename() or '(unnamed)'} ({a.get_content_type()})"
        for a in (message.iter_attachments() if isinstance(message, EmailMessage) else ())
    ]
    text = "\n".join(lines) + "\n\n" + body
    if attachments:
        text += "\n\nAttachments:\n" + "\n".join(attachments)
    return text


def _addresses(value: Any) -> list[str]:
    return [a.strip() for a in str(value or "").split(",") if a.strip()]


def _view(raw: bytes, sent_at: str | None) -> dict[str, Any]:
    """The message as the web's email reader shows it (``view`` type ``email``)."""
    message = email.message_from_bytes(raw, policy=default_policy)
    text = html = ""
    attachments: list[dict[str, str]] = []
    if isinstance(message, EmailMessage):
        plain = message.get_body(preferencelist=("plain",))
        rich = message.get_body(preferencelist=("html",))
        text = str(plain.get_content()) if plain is not None else ""
        html = str(rich.get_content()) if rich is not None else ""
        attachments = [
            {"name": a.get_filename() or "(unnamed)", "type": a.get_content_type()}
            for a in message.iter_attachments()
        ]
    return {
        "type": "email",
        "from": str(message["From"] or ""),
        "to": _addresses(message["To"]),
        "cc": _addresses(message["Cc"]),
        "reply_to": str(message["Reply-To"] or ""),
        "subject": str(message["Subject"] or ""),
        "text": text,
        "html": html,
        "sent_at": sent_at,
        "attachments": attachments,
    }


def _recipients(value: Any, field: str) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, str):
        return [value]
    if isinstance(value, list) and all(isinstance(v, str) for v in value):
        return value
    raise InvalidResource(SERVICE, f'"{field}" must be an address or a list of addresses')


class EmailResources:
    service = SERVICE

    def __init__(
        self, email_service: Any, *, default_from: str, default_from_name: str | None = None
    ) -> None:
        self._email = email_service
        self._default_from = default_from
        self._default_from_name = default_from_name
        self.keeps_mail = _keeps_mail(email_service)
        self.capabilities = ResourceCapabilities(
            browse=True, create=True, write_format=WRITE_FORMAT
        )

    # --- sync helpers, run in a worker thread ---------------------------------------

    @staticmethod
    def _entry(summary: Any) -> ResourceEntry:
        snippet = getattr(summary, "snippet", "") or ""
        attributes = {
            "to": summary.to,
            "from": summary.sender,
            "snippet": snippet,
            # The body's first line, like an inbox; the recipient when empty.
            "summary": snippet or f"To {summary.to}",
        }
        return ResourceEntry(
            summary.message_id,
            summary.subject or "(no subject)",
            "item",
            KEPT_ACTIONS,
            size=summary.size,
            modified=summary.sent_at,
            attributes=attributes,
        )

    def _sent(self, resource_id: str) -> Any:
        try:
            return self._email.get_sent(resource_id)
        except (SentEmailNotFound, SentEmailsNotKept):
            raise ResourceNotFound(SERVICE, resource_id) from None

    def _list(self, parent: str, cursor: str | None, limit: int) -> ResourcePage:
        if parent:
            self._sent(parent)
            raise InvalidResource(SERVICE, f"{parent!r} is a message, not a folder")
        if limit < 1:
            raise InvalidResource(SERVICE, "limit must be positive")
        try:
            rows = self._email.list_sent(limit=limit + 1, before=cursor)
        except SentEmailsNotKept:
            return ResourcePage("", ())
        page = rows[:limit]
        return ResourcePage(
            "",
            tuple(self._entry(s) for s in page),
            next_cursor=page[-1].message_id if len(rows) > limit else None,
        )

    def _stat(self, resource_id: str) -> ResourceEntry:
        return self._entry(self._sent(resource_id).summary)

    def _read(self, resource_id: str) -> ResourceDetail:
        sent = self._sent(resource_id)
        return ResourceDetail(
            self._entry(sent.summary),
            text_preview(_render(sent.raw).encode()),
            view=_view(sent.raw, sent.summary.sent_at),
        )

    def _download(self, resource_id: str, max_bytes: int) -> bytes:
        sent = self._sent(resource_id)
        if len(sent.raw) > max_bytes:
            raise ResourceTooLarge(SERVICE, resource_id, len(sent.raw), max_bytes)
        return sent.raw

    def _write(self, resource_id: str, content: bytes) -> ResourceEntry:
        try:
            self._sent(resource_id)
        except ResourceNotFound:
            pass
        else:
            raise UnsupportedOperation(SERVICE, "replace: a sent message is final")
        try:
            message = json.loads(content)
        except ValueError:
            raise InvalidResource(SERVICE, "the value must be a JSON message") from None
        if not isinstance(message, dict):
            raise InvalidResource(SERVICE, "the value must be a JSON object")
        to = _recipients(message.get("to"), "to")
        subject = message.get("subject")
        text = message.get("text")
        html = message.get("html")
        if not to:
            raise InvalidResource(SERVICE, 'a message needs "to"')
        if not isinstance(subject, str) or not subject:
            raise InvalidResource(SERVICE, 'a message needs a "subject"')
        if not isinstance(text, str) and not isinstance(html, str):
            raise InvalidResource(SERVICE, 'a message needs "text" or "html"')
        try:
            message_id = self._email.send(
                to_emails=to,
                cc_emails=_recipients(message.get("cc"), "cc"),
                subject=subject,
                text_body=text if isinstance(text, str) else "",
                html_body=html if isinstance(html, str) else None,
                from_email=message.get("from") or self._default_from,
                from_name=message.get("from_name") or self._default_from_name,
                reply_to=message.get("reply_to"),
            )
        except ValueError as exc:
            raise InvalidResource(SERVICE, str(exc)) from None
        if message_id:
            return self._stat(message_id)
        # Sent, but this adapter keeps no copy to read back.
        return ResourceEntry(
            resource_id, subject, "item", attributes={"status": "sent; not kept by this adapter"}
        )

    def _delete(self, resource_id: str) -> None:
        try:
            self._email.delete_sent(resource_id)
        except SentEmailNotFound:
            raise ResourceNotFound(SERVICE, resource_id) from None
        except SentEmailsNotKept:
            raise UnsupportedOperation(SERVICE, "delete: this adapter keeps no sent mail") from None

    # --- ServiceResources --------------------------------------------------------------

    async def list(
        self, parent: str = "", *, cursor: str | None = None, limit: int = 100, **options: Any
    ) -> ResourcePage:
        return await asyncio.to_thread(self._list, parent, cursor, limit)

    async def stat(self, resource_id: str) -> ResourceEntry:
        return await asyncio.to_thread(self._stat, resource_id)

    async def read(self, resource_id: str, *, reveal: bool = False) -> ResourceDetail:
        return await asyncio.to_thread(self._read, resource_id)

    async def download(self, resource_id: str, *, max_bytes: int) -> bytes:
        return await asyncio.to_thread(self._download, resource_id, max_bytes)

    async def write(self, resource_id: str, content: bytes) -> ResourceEntry:
        return await asyncio.to_thread(self._write, resource_id, content)

    async def delete(self, resource_id: str) -> None:
        await asyncio.to_thread(self._delete, resource_id)
