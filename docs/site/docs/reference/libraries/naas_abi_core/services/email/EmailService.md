# EmailService

## What it is
- Service layer around an injected email adapter (`IEmailAdapter`).
- Sends emails via the adapter and (when services are wired) publishes email events:
  - `EmailSent` on success
  - `EmailError` on failure

## Public API
- **Class: `EmailService(ServiceBase)`**
  - `__init__(adapter: IEmailAdapter)`
    - Stores the provided adapter.
  - `adapter -> IEmailAdapter` (property)
    - Exposes the wrapped adapter (e.g., for runtime inspection by other components).
  - `send(*, to_email: str | None = None, subject: str, text_body: str, html_body: str | None = None, from_email: str, from_name: str | None = None, reply_to: str | None = None, attachments: list[EmailAttachment] | None = None, to_emails: list[str] | str | None = None, cc_emails: list[str] | str | None = None) -> str | None`
    - Delegates sending to `adapter.send(...)`.
    - Returns the adapter’s message id when available.
    - Publishes `EmailSent`/`EmailError` events when the event service is available.
  - `list_sent(*, limit: int = 100, before: str | None = None) -> list[SentEmailSummary]`
    - Lists kept sent emails (newest first) via `adapter.list_sent(...)`.
  - `get_sent(message_id: str) -> SentEmail`
    - Fetches a kept sent email via `adapter.get_sent(...)`.
  - `delete_sent(message_id: str) -> None`
    - Deletes a kept sent email via `adapter.delete_sent(...)`.

## Configuration/Dependencies
- Inherits from: `naas_abi_core.services.ServiceBase.ServiceBase`
- Requires an adapter implementing: `naas_abi_core.services.email.EmailPorts.IEmailAdapter`
  - Must provide:
    - `send(...) -> str | None`
    - `list_sent(limit: int, before: str | None) -> list[SentEmailSummary]`
    - `get_sent(message_id: str) -> SentEmail`
    - `delete_sent(message_id: str) -> None`
- Uses:
  - `resolve_recipients(...)` to compute display recipient strings.
  - Event types: `EmailSent`, `EmailError`
  - `naas_abi_core.logger` for warning logs if event publishing fails.

## Usage
```python
from naas_abi_core.services.email.EmailService import EmailService

class DummyEmailAdapter:
    def send(self, **kwargs):
        return "msg_123"

    def list_sent(self, limit=100, before=None):
        return []

    def get_sent(self, message_id):
        raise NotImplementedError

    def delete_sent(self, message_id):
        return None

svc = EmailService(adapter=DummyEmailAdapter())

message_id = svc.send(
    to_email="user@example.com",
    subject="Test",
    text_body="Hello",
    from_email="noreply@example.com",
)
print(message_id)
```

## Caveats
- No parameter validation is performed; behavior depends on the adapter.
- Exceptions from `adapter.send(...)` are re-raised after attempting to publish `EmailError`.
- Event publishing is best-effort and will not break `send` (failures are logged as warnings).
- `to_email`/`to_emails`/`cc_emails` are combined into a display string for events using `resolve_recipients`.
