# SendGridIntegration

## What it is
- A small SendGrid API client built on `requests`.
- Supports:
  - Marketing contacts (create/update, search)
  - Marketing lists (list retrieval)
  - Unsubscribe groups (ASM groups)
  - Sending emails via `/mail/send` (optionally with attachments)
- Includes a helper to expose the integration as LangChain `StructuredTool`s.

## Public API

### `SendGridIntegrationConfiguration`
Dataclass configuration for the integration.
- `api_key: str` — SendGrid API key.
- `base_url: str = "https://api.sendgrid.com/v3"` — SendGrid API base URL.

### `SendGridIntegration`
Client for SendGrid API.

- `__init__(configuration: SendGridIntegrationConfiguration)`
  - Stores configuration and builds request headers (`Authorization: Bearer ...`, JSON content type).

- `create_contacts(contacts: list[dict], list_ids: list[str], wait: bool = True) -> dict`
  - `PUT /marketing/contacts` to create/update contacts and associate them to lists.
  - If `wait=True` and a `job_id` is returned, polls job status until completion (or retry limit).

- `search_contacts(query: str | None = None, email: str | None = None) -> dict`
  - `POST /marketing/contacts/search`.
  - If `query` is not provided but `email` is, uses `email LIKE '{email}'`.

- `get_lists() -> dict`
  - `GET /marketing/lists`.

- `get_unsubscribe_groups() -> dict`
  - `GET /asm/groups`.

- `send_email(from_email: str, to_emails: list[str], subject: str, html_content: str, plain_text_content: str | None = None, attachments: list[dict] | None = None) -> dict`
  - `POST /mail/send`.
  - Builds `content` as:
    - HTML (`text/html`) always
    - plus optional plain text (`text/plain`) prepended if `plain_text_content` is provided
  - Optionally adds `attachments` to the payload (SendGrid attachment objects with base64 `content`, `filename`, `type`, and optional `disposition`).

### `as_tools(configuration: SendGridIntegrationConfiguration)`
- Returns a list of LangChain `StructuredTool` instances wrapping:
  - `sendgrid_create_contacts`
  - `sendgrid_search_contacts`
  - `sendgrid_get_lists`
  - `sendgrid_get_unsubscribe_groups`
  - `sendgrid_send_email`

## Configuration/Dependencies
- Requires:
  - `requests`
  - `naas_abi_core.integration.integration` (`Integration`, `IntegrationConfiguration`, `IntegrationConnectionError`)
- Optional (only for `as_tools`):
  - `langchain_core.tools.StructuredTool`
  - `pydantic`

## Usage

```python
from naas_abi_marketplace.applications.sendgrid.integrations.SendGridIntegration import (
    SendGridIntegration,
    SendGridIntegrationConfiguration,
)

cfg = SendGridIntegrationConfiguration(api_key="YOUR_SENDGRID_API_KEY")
sg = SendGridIntegration(cfg)

# Send an email (HTML + optional plain text)
sg.send_email(
    from_email="sender@example.com",
    to_emails=["recipient@example.com"],
    subject="Hello",
    html_content="<p>Hi from SendGrid</p>",
    plain_text_content="Hi from SendGrid",
)

# Search contacts by email
results = sg.search_contacts(email="recipient@example.com")
print(results)
```

## Caveats
- Network/HTTP failures raise `IntegrationConnectionError` (wrapping any `requests` exception, including non-2xx responses via `raise_for_status()`).
- `create_contacts(..., wait=True)` polls every 15 seconds up to 20 retries (~5 minutes) and returns the last fetched job status if not completed.
