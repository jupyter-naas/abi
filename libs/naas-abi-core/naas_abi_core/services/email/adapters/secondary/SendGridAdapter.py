from __future__ import annotations

import base64
from typing import Any

from naas_abi_core.services.email.EmailPorts import (
    EmailAttachment,
    IEmailAdapter,
    resolve_recipients,
)


class SendGridAdapter(IEmailAdapter):
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.sendgrid.com/v3",
        client: Any | None = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._client = client

    def _post(self, endpoint: str, payload: dict[str, Any]) -> None:
        if self._client is not None:
            self._client.post(endpoint, payload)
            return

        import requests

        response = requests.post(
            f"{self._base_url}{endpoint}",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30,
        )
        if response.status_code >= 400:
            detail = response.text.strip() or response.reason
            raise RuntimeError(
                f"SendGrid API request failed ({response.status_code}): {detail}"
            )

    @staticmethod
    def _sendgrid_attachments(
        attachments: list[EmailAttachment] | None,
    ) -> list[dict[str, str]] | None:
        if not attachments:
            return None
        return [
            {
                "content": base64.b64encode(attachment.content).decode("ascii"),
                "filename": attachment.filename,
                "type": attachment.mime_type,
                "disposition": "attachment",
            }
            for attachment in attachments
        ]

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
        content: list[dict[str, str]] = []
        if text_body:
            content.append({"type": "text/plain", "value": text_body})
        if html_body:
            content.append({"type": "text/html", "value": html_body})
        if not content:
            content.append({"type": "text/plain", "value": ""})

        from_payload: dict[str, str] = {"email": from_email}
        if from_name:
            from_payload["name"] = from_name

        payload: dict[str, Any] = {
            "personalizations": [
                {"to": [{"email": addr} for addr in resolve_recipients(to_email, to_emails)]}
            ],
            "from": from_payload,
            "subject": subject,
            "content": content,
        }
        if reply_to:
            payload["reply_to"] = {"email": reply_to}

        sendgrid_attachments = self._sendgrid_attachments(attachments)
        if sendgrid_attachments:
            payload["attachments"] = sendgrid_attachments

        self._post("/mail/send", payload)
