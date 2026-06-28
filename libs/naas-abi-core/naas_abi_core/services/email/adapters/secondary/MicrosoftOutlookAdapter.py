from __future__ import annotations

import base64
from typing import Any
from urllib.parse import quote

from naas_abi_core.services.email.EmailPorts import (
    EmailAttachment,
    IEmailAdapter,
    resolve_recipients,
)

_GRAPH_BASE = "https://graph.microsoft.com/v1.0"
_SCOPE = ["https://graph.microsoft.com/.default"]


class MicrosoftOutlookAdapter(IEmailAdapter):
    """Email adapter that sends via Microsoft Graph API (app-only / client-credentials).

    The sender mailbox is determined by ``from_email`` passed to ``send()``, which
    must be a UPN the registered app has ``Mail.Send`` permission on.

    Limitations:
    - ``from_name`` is accepted for interface compatibility but silently ignored:
      the Graph API always uses the Azure AD display name of the sender mailbox.
    - Attachments must be < 3 MB (Graph API ``fileAttachment`` limit).
    - When both ``html_body`` and ``text_body`` are provided, the HTML body is used.
      The Graph API structured payload does not support multipart/alternative natively.

    Args:
        tenant_id: Azure AD tenant ID.
        client_id: App registration client ID.
        client_secret: App registration client secret.
        user: Default sender mailbox UPN (used when ``from_email`` is absent).
        client: Optional injectable fake for unit tests. Must expose
            ``post(url, payload)`` and ``get_token() -> str``.
    """

    def __init__(
        self,
        *,
        tenant_id: str,
        client_id: str,
        client_secret: str,
        user: str,
        client: Any | None = None,
    ) -> None:
        self._tenant_id = tenant_id
        self._client_id = client_id
        self._client_secret = client_secret
        self._user = user
        self._client = client
        self._token: str | None = None

    # ── Auth ──────────────────────────────────────────────────────────────────

    def _get_token(self) -> str:
        if self._client is not None:
            return self._client.get_token()
        if self._token:
            return self._token

        import msal  # lazy — optional extra

        app = msal.ConfidentialClientApplication(
            client_id=self._client_id,
            authority=f"https://login.microsoftonline.com/{self._tenant_id}",
            client_credential=self._client_secret,
        )
        result = app.acquire_token_for_client(scopes=_SCOPE)
        if "access_token" not in result:
            raise RuntimeError(
                f"Microsoft Graph token error: {result.get('error')} — "
                f"{result.get('error_description')}"
            )
        self._token = result["access_token"]
        return self._token

    # ── HTTP transport ────────────────────────────────────────────────────────

    def _post(self, url: str, payload: dict[str, Any]) -> None:
        if self._client is not None:
            self._client.post(url, payload)
            return

        import requests  # lazy

        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {self._get_token()}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30,
        )
        if response.status_code >= 400:
            detail = response.text.strip() or response.reason
            raise RuntimeError(
                f"Microsoft Graph API request failed ({response.status_code}): {detail}"
            )

    # ── IEmailAdapter ─────────────────────────────────────────────────────────

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
        mailbox = quote(from_email or self._user)
        url = f"{_GRAPH_BASE}/users/{mailbox}/sendMail"

        body_payload = (
            {"contentType": "HTML", "content": html_body}
            if html_body
            else {"contentType": "Text", "content": text_body}
        )

        message: dict[str, Any] = {
            "subject": subject,
            "body": body_payload,
            "toRecipients": [
                {"emailAddress": {"address": addr}}
                for addr in resolve_recipients(to_email, to_emails)
            ],
        }

        if reply_to:
            message["replyTo"] = [{"emailAddress": {"address": reply_to}}]

        if attachments:
            message["attachments"] = [
                {
                    "@odata.type": "#microsoft.graph.fileAttachment",
                    "name": att.filename,
                    "contentType": att.mime_type,
                    "contentBytes": base64.b64encode(att.content).decode("ascii"),
                }
                for att in attachments
            ]

        self._post(url, {"message": message, "saveToSentItems": True})
