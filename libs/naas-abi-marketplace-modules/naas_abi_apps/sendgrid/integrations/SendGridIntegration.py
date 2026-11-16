"""SendGrid v3 API (contacts, lists, unsubscribe groups, mail), async, on
``naas_abi_sdk`` only.

Port of ``naas_abi_marketplace.applications.sendgrid.integrations``: same
endpoints and tool names. The contact import tool no longer waits for the
import job by default (up to 5 minutes, past an agent call's deadline): it
returns the job id, and ``wait=True`` polls as before.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from naas_abi_apps.common.http import HttpConfiguration, request
from naas_abi_sdk.integration import Integration

SERVICE = "SendGrid"


@dataclass
class SendGridIntegrationConfiguration(HttpConfiguration):
    api_key: str
    base_url: str = "https://api.sendgrid.com/v3"
    # Seconds between two import job polls, and how many polls at most.
    poll_interval: float = 15.0
    max_polls: int = 20


class SendGridIntegration(Integration):
    """Contacts, lists, unsubscribe groups and email sending."""

    def __init__(self, configuration: SendGridIntegrationConfiguration):
        super().__init__(configuration)
        self.configuration = configuration
        self.headers = {
            "Authorization": f"Bearer {configuration.api_key}",
            "Content-Type": "application/json",
        }

    async def _request(
        self, method: str, endpoint: str, body: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        response = await request(
            self.configuration,
            method,
            f"{self.configuration.base_url}{endpoint}",
            service=SERVICE,
            headers=self.headers,
            json=body if body is not None else None,
        )
        return response.json() if response.content else {}

    async def create_contacts(
        self, contacts: list[dict[str, Any]], list_ids: list[str], wait: bool = False
    ) -> dict[str, Any]:
        """Create or update contacts and add them to lists; ``wait``: until imported."""
        result = await self._request(
            "PUT", "/marketing/contacts", {"list_ids": list_ids, "contacts": contacts}
        )
        if wait and "job_id" in result:
            return await self.wait_for_job(result["job_id"])
        return result

    async def wait_for_job(self, job_id: str) -> dict[str, Any]:
        """Poll a contact import job until it completes, or ``max_polls`` times."""
        result: dict[str, Any] = {}
        for attempt in range(self.configuration.max_polls):
            result = await self._request("GET", f"/marketing/contacts/imports/{job_id}")
            if result.get("status") == "completed":
                return result
            if attempt + 1 < self.configuration.max_polls:
                await asyncio.sleep(self.configuration.poll_interval)
        return result

    async def search_contacts(
        self, query: str | None = None, email: str | None = None
    ) -> dict[str, Any]:
        """Search contacts with an SGQL ``query``, or by ``email``."""
        body: dict[str, Any] = {}
        if query:
            body["query"] = query
        elif email:
            body["query"] = f"email LIKE '{email}'"
        return await self._request("POST", "/marketing/contacts/search", body)

    async def get_lists(self) -> dict[str, Any]:
        """All contact lists."""
        return await self._request("GET", "/marketing/lists")

    async def get_unsubscribe_groups(self) -> Any:
        """All unsubscribe groups."""
        return await self._request("GET", "/asm/groups")

    async def send_email(
        self,
        from_email: str,
        to_emails: list[str],
        subject: str,
        html_content: str,
        plain_text_content: str | None = None,
        attachments: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Send an email. attachments: SendGrid objects (base64 ``content``,
        ``filename``, ``type``, optional ``disposition``)."""
        content = [{"type": "text/html", "value": html_content}]
        if plain_text_content:
            content.insert(0, {"type": "text/plain", "value": plain_text_content})
        body: dict[str, Any] = {
            "personalizations": [{"to": [{"email": email} for email in to_emails]}],
            "from": {"email": from_email},
            "subject": subject,
            "content": content,
        }
        if attachments:
            body["attachments"] = attachments
        return await self._request("POST", "/mail/send", body)


def as_tools(configuration: SendGridIntegrationConfiguration) -> list[Any]:
    """LangChain tools over the integration."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field

    integration = SendGridIntegration(configuration)

    class CreateContactsSchema(BaseModel):
        contacts: list[dict[str, Any]] = Field(
            ..., description="List of contact data dictionaries"
        )
        list_ids: list[str] = Field(
            ..., description="List of list IDs to add contacts to"
        )

    class SearchContactsSchema(BaseModel):
        query: str | None = Field(None, description="SGQL query string")
        email: str | None = Field(None, description="Email address to search for")

    class EmptySchema(BaseModel):
        pass

    class SendEmailSchema(BaseModel):
        from_email: str = Field(..., description="Sender email address")
        to_emails: list[str] = Field(
            ..., description="List of recipient email addresses"
        )
        subject: str = Field(..., description="Email subject line")
        html_content: str = Field(..., description="HTML content of the email")
        plain_text_content: str | None = Field(
            None, description="Plain text version of the email"
        )

    async def create_contacts(
        contacts: list[dict[str, Any]], list_ids: list[str]
    ) -> Any:
        return await integration.create_contacts(contacts, list_ids)

    async def search_contacts(
        query: str | None = None, email: str | None = None
    ) -> Any:
        return await integration.search_contacts(query, email)

    async def get_lists() -> Any:
        return await integration.get_lists()

    async def get_unsubscribe_groups() -> Any:
        return await integration.get_unsubscribe_groups()

    async def send_email(
        from_email: str,
        to_emails: list[str],
        subject: str,
        html_content: str,
        plain_text_content: str | None = None,
    ) -> Any:
        return await integration.send_email(
            from_email, to_emails, subject, html_content, plain_text_content
        )

    return [
        StructuredTool(
            name="sendgrid_create_contacts",
            description="Create or update contacts and add them to specified lists. Returns the import job.",
            coroutine=create_contacts,
            args_schema=CreateContactsSchema,
        ),
        StructuredTool(
            name="sendgrid_search_contacts",
            description="Search for contacts.",
            coroutine=search_contacts,
            args_schema=SearchContactsSchema,
        ),
        StructuredTool(
            name="sendgrid_get_lists",
            description="Get all contact lists.",
            coroutine=get_lists,
            args_schema=EmptySchema,
        ),
        StructuredTool(
            name="sendgrid_get_unsubscribe_groups",
            description="Get all unsubscribe groups.",
            coroutine=get_unsubscribe_groups,
            args_schema=EmptySchema,
        ),
        StructuredTool(
            name="sendgrid_send_email",
            description="Send an email using SendGrid.",
            coroutine=send_email,
            args_schema=SendEmailSchema,
        ),
    ]
