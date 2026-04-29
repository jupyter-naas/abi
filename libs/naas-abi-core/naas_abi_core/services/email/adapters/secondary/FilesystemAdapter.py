from __future__ import annotations

import time
import uuid
from email.message import EmailMessage
from email.utils import formataddr
from pathlib import Path

from naas_abi_core.services.email.EmailPorts import IEmailAdapter


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
    ) -> None:
        msg = EmailMessage()
        msg["To"] = to_email
        msg["Subject"] = subject
        msg["From"] = (
            formataddr((from_name or "", from_email)) if from_name else from_email
        )
        if reply_to:
            msg["Reply-To"] = reply_to

        msg.set_content(text_body)
        if html_body:
            msg.add_alternative(html_body, subtype="html")

        self._directory.mkdir(parents=True, exist_ok=True)
        filename = f"{int(time.time() * 1000)}-{uuid.uuid4().hex}.eml"
        (self._directory / filename).write_bytes(bytes(msg))
