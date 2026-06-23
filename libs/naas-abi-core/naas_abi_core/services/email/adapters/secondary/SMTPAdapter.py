from __future__ import annotations

import smtplib

from naas_abi_core.services.email.EmailMessageBuilder import build_email_message
from naas_abi_core.services.email.EmailPorts import EmailAttachment, IEmailAdapter


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
        )

        smtp_cls = smtplib.SMTP_SSL if self._use_ssl else smtplib.SMTP
        with smtp_cls(self._host, self._port, timeout=self._timeout) as client:
            client.ehlo()
            if self._use_tls:
                client.starttls()
                client.ehlo()

            if self._username and self._password:
                client.login(self._username, self._password)

            client.send_message(msg)
