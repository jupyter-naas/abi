from __future__ import annotations

from naas_abi_core.services.ServiceBase import ServiceBase
from naas_abi_core.services.email.EmailPorts import IEmailAdapter


class EmailService(ServiceBase):
    def __init__(self, adapter: IEmailAdapter):
        super().__init__()
        self._adapter = adapter

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
        self._adapter.send(
            to_email=to_email,
            subject=subject,
            text_body=text_body,
            html_body=html_body,
            from_email=from_email,
            from_name=from_name,
            reply_to=reply_to,
        )
