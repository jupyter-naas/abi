from __future__ import annotations

import time
import uuid
from pathlib import Path

from naas_abi_core.services.email.EmailMessageBuilder import build_email_message
from naas_abi_core.services.email.EmailPorts import EmailAttachment, IEmailAdapter


class FilesystemAdapter(IEmailAdapter):
    def __init__(self, *, directory: str) -> None:
        self._directory = Path(directory).expanduser()

    def send(
        self,
        *,
        to_email: str,
        subject: str,
        text_body: str,
        html_body: str | None = None,
        from_email: str,
        from_name: str | None = None,
        reply_to: str | None = None,
        attachments: list[EmailAttachment] | None = None,
    ) -> None:
        msg = build_email_message(
            to_email=to_email,
            subject=subject,
            text_body=text_body,
            html_body=html_body,
            from_email=from_email,
            from_name=from_name,
            reply_to=reply_to,
            attachments=attachments,
        )

        self._directory.mkdir(parents=True, exist_ok=True)
        filename = f"{int(time.time() * 1000)}-{uuid.uuid4().hex}.eml"
        (self._directory / filename).write_bytes(bytes(msg))
