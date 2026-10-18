# SMTPAdapter

## What it is
- An `IEmailAdapter` implementation that sends emails via SMTP using Python’s `smtplib`.
- Supports plain text and optional HTML alternative bodies.
- Supports optional authentication and optional TLS or SSL.

## Public API
- `class SMTPAdapter(IEmailAdapter)`
  - `__init__(*, host: str, port: int, username: str | None = None, password: str | None = None, use_tls: bool = False, use_ssl: bool = False, timeout: int = 10) -> None`
    - Configures SMTP connection parameters.
    - Validates that `use_tls` and `use_ssl` are not both enabled.
  - `send(*, to_email: str, subject: str, text_body: str, html_body: str | None = None, from_email: str, from_name: str | None = None, reply_to: str | None = None) -> None`
    - Builds an `EmailMessage` with:
      - `To`, `Subject`, `From` (formatted with `from_name` when provided), optional `Reply-To`
      - plain text body, and optional HTML alternative
    - Connects using SMTP or SMTP-over-SSL, optionally upgrades to TLS, optionally logs in, then sends.

## Configuration/Dependencies
- Standard library:
  - `smtplib` (`SMTP`, `SMTP_SSL`)
  - `email.message.EmailMessage`
  - `email.utils.formataddr`
- Project dependency:
  - Implements `naas_abi_core.services.email.EmailPorts.IEmailAdapter`
- Parameters:
  - `host`, `port`: SMTP server address.
  - `use_ssl`: uses `smtplib.SMTP_SSL` when `True`.
  - `use_tls`: calls `starttls()` when `True` (only when not using SSL).
  - `username`/`password`: if both provided, `login()` is performed.
  - `timeout`: passed to the SMTP client constructor.

## Usage
```python
from naas_abi_core.services.email.adapters.secondary.SMTPAdapter import SMTPAdapter

adapter = SMTPAdapter(
    host="smtp.example.com",
    port=587,
    username="user",
    password="pass",
    use_tls=True,
    timeout=10,
)

adapter.send(
    to_email="recipient@example.com",
    subject="Hello",
    text_body="Plain text body",
    html_body="<p>HTML body</p>",
    from_email="sender@example.com",
    from_name="Sender Name",
    reply_to="replyto@example.com",
)
```

## Caveats
- `use_tls` and `use_ssl` cannot both be `True` (raises `ValueError`).
- Authentication occurs only if **both** `username` and `password` are provided.
- No attachments, CC/BCC, or custom headers are handled in this adapter.
