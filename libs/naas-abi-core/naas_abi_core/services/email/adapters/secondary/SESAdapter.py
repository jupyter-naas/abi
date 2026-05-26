from __future__ import annotations

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
        source = formataddr((from_name, from_email)) if from_name else from_email

        body: dict[str, dict[str, str]] = {
            "Text": {"Data": text_body, "Charset": "UTF-8"},
        }
        if html_body is not None:
            body["Html"] = {"Data": html_body, "Charset": "UTF-8"}

        params: dict[str, Any] = {
            "Source": source,
            "Destination": {"ToAddresses": [to_email]},
            "Message": {
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": body,
            },
        }
        if reply_to is not None:
            params["ReplyToAddresses"] = [reply_to]

        self._get_client().send_email(**params)
