from __future__ import annotations

import smtplib
from email.message import EmailMessage
from email.utils import formataddr

from naas_abi_core.services.email.EmailPorts import IEmailAdapter


class SMTPAdapter(IEmailAdapter):
    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str | None = None,
        password: str | None = None,
        use_tls: bool = False,
        use_ssl: bool = False,
        timeout: int = 10,
    ) -> None:
        if use_tls and use_ssl:
            raise ValueError("SMTPAdapter cannot use TLS and SSL at the same time")
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._use_tls = use_tls
        self._use_ssl = use_ssl
        self._timeout = timeout

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

        smtp_cls = smtplib.SMTP_SSL if self._use_ssl else smtplib.SMTP
        with smtp_cls(self._host, self._port, timeout=self._timeout) as client:
            client.ehlo()
            if self._use_tls:
                client.starttls()
                client.ehlo()

            if self._username and self._password:
                client.login(self._username, self._password)

            client.send_message(msg)
