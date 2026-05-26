from __future__ import annotations

from email.message import EmailMessage
from email.utils import formataddr
from typing import Any

from naas_abi_core.services.email.EmailPorts import IEmailAdapter


class SESAdapter(IEmailAdapter):
    def __init__(
        self,
        *,
        region_name: str | None = None,
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
        aws_session_token: str | None = None,
        client: Any | None = None,
    ) -> None:
        self._region_name = region_name
        self._aws_access_key_id = aws_access_key_id
        self._aws_secret_access_key = aws_secret_access_key
        self._aws_session_token = aws_session_token
        self._client = client

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client

        import boto3

        kwargs: dict[str, Any] = {}
        if self._region_name is not None:
            kwargs["region_name"] = self._region_name
        if self._aws_access_key_id is not None:
            kwargs["aws_access_key_id"] = self._aws_access_key_id
        if self._aws_secret_access_key is not None:
            kwargs["aws_secret_access_key"] = self._aws_secret_access_key
        if self._aws_session_token is not None:
            kwargs["aws_session_token"] = self._aws_session_token

        self._client = boto3.client("ses", **kwargs)
        return self._client

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

        self._get_client().send_raw_email(
            Source=from_email,
            Destinations=[to_email],
            RawMessage={"Data": bytes(msg)},
        )
