# EmailService

## What it is
- A thin service wrapper around an email adapter (`IEmailAdapter`) that sends emails.
- Delegates all sending logic to the injected adapter.

## Public API
- **Class: `EmailService`**
  - `__init__(adapter: IEmailAdapter)`
    - Stores the provided adapter for later use.
  - `send(*, to_email: str, subject: str, text_body: str, html_body: str | None = None, from_email: str, from_name: str | None = None, reply_to: str | None = None) -> None`
    - Sends an email by forwarding all parameters to `self._adapter.send(...)`.

## Configuration/Dependencies
- Inherits from: `naas_abi_core.services.ServiceBase.ServiceBase`
- Requires an adapter implementing: `naas_abi_core.services.email.EmailPorts.IEmailAdapter`
  - The adapter must provide a `.send(...)` method compatible with the arguments used.

## Usage
```python
from naas_abi_core.services.email.EmailService import EmailService

# Example adapter stub (must satisfy IEmailAdapter at runtime)
class ConsoleEmailAdapter:
    def send(self, *, to_email, subject, text_body, html_body=None, from_email=None, from_name=None, reply_to=None):
        print("Sending email:", to_email, subject)

service = EmailService(adapter=ConsoleEmailAdapter())

service.send(
    to_email="user@example.com",
    subject="Hello",
    text_body="Plain text content",
    from_email="noreply@example.com",
)
```

## Caveats
- `EmailService` does not validate parameters or handle errors; behavior depends entirely on the provided adapter implementation.
