# SendGridIntegration

## What it is
- A small SendGrid API client built on `requests`.
- Supports:
  - Marketing contacts (create/update, search)
  - Marketing lists (list retrieval)
  - Unsubscribe groups (ASM groups)
  - Sending emails via `/mail/send`
- Includes a helper to expose the integration as LangChain `StructuredTool`s.

## Public API

### `SendGridIntegrationConfiguration`
Dataclass configuration for the integration.
- `api_key: str` — SendGrid API key (required).
- `base_url: str = "https://api.sendgrid.com/v3"` — SendGrid API base URL.

### `SendGridIntegration`
Client for SendGrid API.
- `__init__(configuration: SendGridIntegrationConfiguration)`
  - Initializes request headers using the provided API key.
- `create_contacts(contacts: List[Dict], list_ids: List[str], wait: bool = True) -> Dict`
  - PUT `/marketing/contacts` to create/update contacts and associate them to lists.
  - If `wait=True` and a `job_id` is returned, polls job status until completion (or max retries).
- `search_contacts(query: Optional[str] = None, email: Optional[str] = None) -> Dict`
  - POST `/marketing/contacts/search`.
  - If `email` is provided and `query` is not, uses `email LIKE '{email}'`.
- `get_lists() -> Dict`
  - GET `/marketing/lists`.
- `get_unsubscribe_groups() -> Dict`
  - GET `/asm/groups`.
- `send_email(from_email: str, to_emails: List[str], subject: str, html_content: str, plain_text_content: Optional[str] = None) -> Dict`
  - POST `/mail/send`.
  - Sends HTML content by default; if `plain_text_content` is provided, sends only plain text content.

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
  - `naas_abi_core.integration.integration` (for `Integration`, `IntegrationConfiguration`, `IntegrationConnectionError`)
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

# Send an email
sg.send_email(
    from_email="sender@example.com",
    to_emails=["recipient@example.com"],
    subject="Hello",
    html_content="<p>Hi from SendGrid</p>",
)

# Search contacts by email
results = sg.search_contacts(email="recipient@example.com")
print(results)
```

## Caveats
- `_make_request` raises `IntegrationConnectionError` for any `requests` exception (including non-2xx responses via `raise_for_status()`).
- `create_contacts(..., wait=True)` polls every 15 seconds up to 20 retries (~5 minutes max) and returns the last fetched status if not completed.
- `send_email` uses **either** HTML content **or** plain-text content:
  - If `plain_text_content` is provided, it replaces the HTML content in the request payload (it does not send multipart content).
