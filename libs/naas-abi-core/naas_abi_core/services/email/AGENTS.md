# Email Service — AGENTS.md

> Scope: `libs/naas-abi-core/naas_abi_core/services/email/`. Canonical reference for agents.

## Purpose

Send transactional email through pluggable backends. Publishes `EmailSent` / `EmailError` events through the event service when available.

## Files

```
email/
├── EmailPorts.py              # IEmailAdapter
├── EmailService.py            # public service
├── EmailFactory.py            # pre-wired builders
├── adapters/secondary/
│   ├── SMTPAdapter.py
│   ├── SESAdapter.py
│   └── FilesystemAdapter.py
├── ontologies/                # EmailSent, EmailError
└── tests/
```

## Port (`EmailPorts.py`)

```python
class IEmailAdapter:
    def send(
        to_email: str,
        subject: str,
        text_body: str,
        html_body: str | None = None,
        *,
        from_email: str,
        from_name: str | None = None,
        reply_to: str | None = None,
    ) -> None
```

## Service API (`EmailService.py`)

```python
EmailService(adapter: IEmailAdapter)

send(to_email, subject, text_body, html_body=None, *,
     from_email, from_name=None, reply_to=None)
# → publishes EmailSent on success, EmailError on failure
```

## Available Adapters

| Adapter | Backend / Notes |
|---|---|
| `SMTPAdapter` | SMTP — TLS/SSL, auth, custom timeout |
| `SESAdapter` | AWS SES — lazy-loads boto3 |
| `FilesystemAdapter` | Writes `.eml` files to disk (dev / test) |

## Factory (`EmailFactory.py`)

```python
EmailFactory.EmailServiceSMTP(host, port, username=None, password=None,
                              use_tls=False, use_ssl=False, timeout=10)
EmailFactory.EmailServiceFilesystem(directory)
EmailFactory.EmailServiceSES(region_name=None, aws_access_key_id=None,
                             aws_secret_access_key=None, aws_session_token=None)
```

## Tests

```bash
uv run pytest libs/naas-abi-core/naas_abi_core/services/email/tests/
uv run pytest libs/naas-abi-core/naas_abi_core/services/email/tests/EmailService_events_test.py
uv run pytest libs/naas-abi-core/naas_abi_core/services/email/tests/email__secondary_adapter__generic_test.py
```

## Adding a new adapter

1. Implement `IEmailAdapter.send` in `adapters/secondary/<Name>Adapter.py`. Match the exact keyword-only signature for `from_email`, `from_name`, `reply_to`.
2. Run the generic contract tests against it.
3. Add a `EmailFactory.<Name>(...)` builder for zero-config setup.
