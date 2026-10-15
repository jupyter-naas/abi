# EmailPorts

## What it is
- A small “ports” module defining the email adapter interface and supporting types.
- Provides:
  - Data models for attachments and “kept” (stored) sent emails
  - A helper to normalize recipient inputs
  - Exceptions describing whether sent mail is retained by an adapter

## Public API

- `@dataclass(frozen=True) class EmailAttachment`
  - Represents an email attachment.
  - Fields:
    - `filename: str`
    - `content: bytes`
    - `mime_type: str`
    - `content_id: str | None = None` (for inline attachments referenced as `cid:...`)
    - `is_inline: bool = False` (mark as inline vs download)

- `def resolve_recipients(to_email: str | list[str] | None = None, to_emails: list[str] | str | None = None) -> list[str]`
  - Normalizes `to_email`/`to_emails` into a de-duplicated recipient list (preserves first-seen order).
  - Accepts:
    - single email string
    - comma-separated string
    - list of strings (each may contain commas)
  - Raises `ValueError` if no recipient is found.

- `class SentEmailsNotKept(NotImplementedError)`
  - Raised by adapters that do not store copies of sent messages.

- `class SentEmailNotFound(Exception)`
  - Raised when a stored sent message cannot be found (intended for adapters that keep mail).

- `@dataclass(frozen=True) class SentEmailSummary`
  - Summary metadata for a stored sent email (as returned by listing).
  - Fields:
    - `message_id: str`
    - `sent_at: str` (ISO 8601)
    - `size: int` (bytes of RFC 5322 message)
    - `subject: str`
    - `to: str`
    - `sender: str`
    - `snippet: str = ""` (may be empty if adapter does not read bodies)

- `@dataclass(frozen=True) class SentEmail`
  - Represents a stored sent email.
  - Fields:
    - `summary: SentEmailSummary`
    - `raw: bytes` (full RFC 5322 message, `.eml`)

- `class IEmailAdapter(ABC)`
  - Abstract interface for sending mail; adapters may optionally keep a copy of sent mail.
  - Methods:
    - `send(...) -> str | None` *(abstract)*
      - Sends an email.
      - Returns a message id for the kept copy, or `None` if not kept.
      - Keyword-only parameters:
        - `to_email: str | None = None`
        - `subject: str`
        - `text_body: str`
        - `html_body: str | None = None`
        - `from_email: str`
        - `from_name: str | None = None`
        - `reply_to: str | None = None`
        - `attachments: list[EmailAttachment] | None = None`
        - `to_emails: list[str] | str | None = None`
        - `cc_emails: list[str] | str | None = None`
    - `list_sent(*, limit: int = 100, before: str | None = None) -> list[SentEmailSummary]`
      - Lists kept messages (newest first); `before` continues after a message id.
      - Default implementation raises `SentEmailsNotKept`.
    - `get_sent(message_id: str) -> SentEmail`
      - Retrieves one kept message; intended to raise `SentEmailNotFound` if missing.
      - Default implementation raises `SentEmailsNotKept`.
    - `delete_sent(message_id: str) -> None`
      - Deletes a kept copy (does not recall the delivered message).
      - Default implementation raises `SentEmailsNotKept`.

## Configuration/Dependencies
- Standard library only:
  - `abc.ABC`, `abc.abstractmethod`
  - `dataclasses.dataclass`
- No runtime configuration in this module.

## Usage

```python
from naas_abi_core.services.email.EmailPorts import IEmailAdapter, resolve_recipients

# Normalize recipients (supports comma-separated input)
recipients = resolve_recipients(to_email="a@example.com, b@example.com", to_emails=["b@example.com", "c@example.com"])
print(recipients)  # ['a@example.com', 'b@example.com', 'c@example.com']

# Implement the port
class ConsoleEmailAdapter(IEmailAdapter):
    def send(
        self,
        *,
        to_email=None,
        subject: str,
        text_body: str,
        html_body=None,
        from_email: str = "",
        from_name=None,
        reply_to=None,
        attachments=None,
        to_emails=None,
        cc_emails=None,
    ) -> str | None:
        to_list = resolve_recipients(to_email=to_email, to_emails=to_emails)
        print("TO:", to_list)
        print("SUBJECT:", subject)
        print(text_body)
        return None  # not kept

adapter = ConsoleEmailAdapter()
adapter.send(
    to_email="user@example.com",
    subject="Test",
    text_body="Hello",
    from_email="noreply@example.com",
)
```

## Caveats
- `IEmailAdapter` is abstract; you must implement `send`.
- `list_sent`, `get_sent`, and `delete_sent` raise `SentEmailsNotKept` unless an adapter overrides them.
- `resolve_recipients` raises `ValueError` when no recipients are provided (prevents silent no-op sends).
