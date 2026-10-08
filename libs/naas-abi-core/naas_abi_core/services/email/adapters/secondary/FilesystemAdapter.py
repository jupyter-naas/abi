from __future__ import annotations

import html
import re
import threading
import time
import uuid
from datetime import UTC, datetime
from email.message import EmailMessage
from email.parser import BytesHeaderParser, BytesParser
from email.policy import default as default_policy
from pathlib import Path

from naas_abi_core.services.email.EmailMessageBuilder import build_email_message
from naas_abi_core.services.email.EmailPorts import (
    EmailAttachment,
    IEmailAdapter,
    SentEmail,
    SentEmailNotFound,
    SentEmailSummary,
)

# ``<epoch ms>-<uuid4 hex>``: sorts by send time, and is a safe file name.
_MESSAGE_ID = re.compile(r"[0-9]+-[0-9a-f]{32}")
_SUFFIX = ".eml"
# Listing reads each message's body for its snippet, up to this size.
SNIPPET_MAX_BYTES = 1024 * 1024
SNIPPET_CHARS = 160
_BLOCK_TAG = re.compile(r"(?i)<\s*(?:br|/?p|/?div|/?li|/?tr|/?h[1-6])\b[^>]*>")
_HIDDEN = re.compile(r"(?is)<(style|script)\b.*?</\1\s*>")
_TAG = re.compile(r"<[^>]+>")


def _snippet(message: EmailMessage) -> str:
    """The start of the text body on one line; the HTML body without its tags
    when there is no text."""
    for kind in ("plain", "html"):
        part = message.get_body(preferencelist=(kind,))
        if part is None:
            continue
        text = str(part.get_content())
        if kind == "html":
            text = html.unescape(
                _TAG.sub("", _BLOCK_TAG.sub(" ", _HIDDEN.sub(" ", text)))
            )
        line = " ".join(text.split())
        if line:
            return line[:SNIPPET_CHARS]
    return ""


class FilesystemAdapter(IEmailAdapter):
    """Writes every message to ``<directory>/<message id>.eml`` and keeps it."""

    def __init__(self, *, directory: str) -> None:
        self._directory = Path(directory).expanduser()
        self._last_millis = 0
        self._lock = threading.Lock()

    def _next_message_id(self) -> str:
        # Strictly increasing per adapter, so ids sort in send order even for
        # several sends within one millisecond.
        with self._lock:
            millis = max(int(time.time() * 1000), self._last_millis + 1)
            self._last_millis = millis
        return f"{millis}-{uuid.uuid4().hex}"

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
    ) -> str:
        msg = build_email_message(
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

        self._directory.mkdir(parents=True, exist_ok=True)
        message_id = self._next_message_id()
        (self._directory / f"{message_id}{_SUFFIX}").write_bytes(bytes(msg))
        return message_id

    # ------------------------------------------------------------------ kept mail

    def _path(self, message_id: str) -> Path:
        if not _MESSAGE_ID.fullmatch(message_id):
            raise SentEmailNotFound(message_id)
        path = self._directory / f"{message_id}{_SUFFIX}"
        if not path.is_file():
            raise SentEmailNotFound(message_id)
        return path

    def _summary(self, message_id: str, path: Path) -> SentEmailSummary:
        size = path.stat().st_size
        snippet = ""
        with path.open("rb") as handle:
            if size <= SNIPPET_MAX_BYTES:
                headers = BytesParser(policy=default_policy).parse(handle)
                snippet = _snippet(headers)  # type: ignore[arg-type]
            else:  # a large message (attachments): its headers only
                headers = BytesHeaderParser(policy=default_policy).parse(handle)
        millis = int(message_id.split("-", 1)[0])
        return SentEmailSummary(
            message_id=message_id,
            sent_at=datetime.fromtimestamp(millis / 1000, tz=UTC).isoformat(),
            size=size,
            subject=str(headers.get("Subject", "")),
            to=str(headers.get("To", "")),
            sender=str(headers.get("From", "")),
            snippet=snippet,
        )

    def list_sent(
        self, *, limit: int = 100, before: str | None = None
    ) -> list[SentEmailSummary]:
        if not self._directory.is_dir():
            return []
        ids = sorted(
            (
                p.stem
                for p in self._directory.glob(f"*{_SUFFIX}")
                if _MESSAGE_ID.fullmatch(p.stem)
            ),
            reverse=True,
        )
        if before is not None:
            ids = [i for i in ids if i < before]
        # Only the returned page pays for reading headers.
        return [
            self._summary(i, self._directory / f"{i}{_SUFFIX}")
            for i in ids[: max(limit, 0)]
        ]

    def get_sent(self, message_id: str) -> SentEmail:
        path = self._path(message_id)
        return SentEmail(summary=self._summary(message_id, path), raw=path.read_bytes())

    def delete_sent(self, message_id: str) -> None:
        self._path(message_id).unlink()
