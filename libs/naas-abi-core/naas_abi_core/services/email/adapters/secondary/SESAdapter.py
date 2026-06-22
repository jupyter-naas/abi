from __future__ import annotations

from typing import Any

from naas_abi_core.services.email.EmailMessageBuilder import build_email_message
from naas_abi_core.services.email.EmailPorts import EmailAttachment, IEmailAdapter


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

        self._get_client().send_raw_email(
            Source=from_email,
            Destinations=[to_email],
            RawMessage={"Data": bytes(msg)},
        )
