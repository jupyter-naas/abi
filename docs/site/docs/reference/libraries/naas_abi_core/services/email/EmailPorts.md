# IEmailAdapter

## What it is
- An abstract interface (port) defining how an email adapter must send emails.
- Intended to be implemented by concrete email providers (e.g., SMTP, API-based services).

## Public API
- `class IEmailAdapter(ABC)`
  - `send(*, to_email: str, subject: str, text_body: str, html_body: str | None = None, from_email: str, from_name: str | None = None, reply_to: str | None = None) -> None`
    - Sends an email with required metadata and body content.
    - Parameters:
      - `to_email`: recipient email address (required)
      - `subject`: email subject (required)
      - `text_body`: plain-text body (required)
      - `html_body`: HTML body (optional)
      - `from_email`: sender email address (required)
      - `from_name`: sender display name (optional)
      - `reply_to`: reply-to email address (optional)
    - Returns: `None`

## Configuration/Dependencies
- Depends only on Python standard library:
  - `abc.ABC`, `abc.abstractmethod`
- No configuration is defined in this module.

## Usage
```python
from naas_abi_core.services.email.EmailPorts import IEmailAdapter

class ConsoleEmailAdapter(IEmailAdapter):
    def send(
        self,
        *,
        to_email: str,
        subject: str,
        text_body: str,
        html_body: str | None = None,
        from_email: str = "",
        from_name: str | None = None,
        reply_to: str | None = None,
    ) -> None:
        print(f"To: {to_email}")
        print(f"From: {from_name or ''} <{from_email}>")
        if reply_to:
            print(f"Reply-To: {reply_to}")
        print(f"Subject: {subject}")
        print(text_body)

adapter: IEmailAdapter = ConsoleEmailAdapter()
adapter.send(
    to_email="user@example.com",
    subject="Test",
    text_body="Hello",
    from_email="noreply@example.com",
)
```

## Caveats
- `IEmailAdapter` is abstract; it cannot be instantiated directly.
- Concrete implementations must provide the `send` method with the same keyword-only signature.
