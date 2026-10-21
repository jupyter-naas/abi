# EmailFactory

## What it is
- A small factory for creating `EmailService` instances configured with an SMTP adapter.

## Public API
- `EmailFactory.EmailServiceSMTP(...) -> EmailService`
  - Creates an `EmailService` wired to `SMTPAdapter` with the provided SMTP connection settings.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.services.email.EmailService.EmailService`
  - `naas_abi_core.services.email.adapters.secondary.SMTPAdapter.SMTPAdapter`
- Parameters:
  - `host: str` — SMTP server hostname
  - `port: int` — SMTP server port
  - `username: str | None = None` — optional username
  - `password: str | None = None` — optional password
  - `use_tls: bool = False` — enable STARTTLS (if supported by adapter/server)
  - `use_ssl: bool = False` — enable SSL/TLS from connection start
  - `timeout: int = 10` — connection timeout in seconds (passed to adapter)

## Usage
```python
from naas_abi_core.services.email.EmailFactory import EmailFactory

email_service = EmailFactory.EmailServiceSMTP(
    host="smtp.example.com",
    port=587,
    username="user",
    password="secret",
    use_tls=True,
    timeout=10,
)

# Use email_service according to EmailService's API.
```

## Caveats
- `use_tls` and `use_ssl` are both exposed; ensure you set them consistently with your SMTP server expectations.
