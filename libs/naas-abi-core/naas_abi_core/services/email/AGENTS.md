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
│   ├── SendGridAdapter.py
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
        attachments: list[EmailAttachment] | None = None,
    ) -> None
```

## Service API (`EmailService.py`)

```python
EmailService(adapter: IEmailAdapter)

send(to_email, subject, text_body, html_body=None, *,
     from_email, from_name=None, reply_to=None, attachments=None)
# → publishes EmailSent on success, EmailError on failure
```

## Available Adapters

| Adapter | Backend / Notes |
|---|---|
| `SMTPAdapter` | SMTP — TLS/SSL, auth, custom timeout |
| `SESAdapter` | AWS SES — lazy-loads boto3 |
| `SendGridAdapter` | SendGrid Mail Send API — lazy-loads requests |
| `FilesystemAdapter` | Writes `.eml` files to disk (dev / test) |

## Factory (`EmailFactory.py`)

```python
EmailFactory.EmailServiceSMTP(host, port, username=None, password=None,
                              use_tls=False, use_ssl=False, timeout=10)
EmailFactory.EmailServiceFilesystem(directory)
EmailFactory.EmailServiceSES(region_name=None, aws_access_key_id=None,
                             aws_secret_access_key=None, aws_session_token=None)
EmailFactory.EmailServiceSendGrid(api_key, base_url="https://api.sendgrid.com/v3")
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

## NATS RPC adapters

`adapters/primary/email__primary_adapter__NATS.py` exposes the service's
protobuf endpoints. `adapters/secondary/EmailSecondaryAdapterNATSClient.py` implements the outbound
port. Wire contracts live under `naas_abi_core/proto/email/v1/`.

Clients inherit connection, JWT renewal, deadlines, and error handling from
`naas_abi_core.engine.nats_rpc.NatsRPCClient`; keep domain conversion and exception
mapping in the adapter. Primaries use `respond_protobuf` for bounded replies.
The maximum message size is 8 MiB (or a lower broker limit); oversized replies
return non-retryable `PAYLOAD_TOO_LARGE`, and micro-service error headers raise
instead of becoming an empty success. Larger results require streaming or a
storage reference. No RPC is automatically replayed after transport failure:
a timeout can hide a completed operation. Reconcile its outcome before retrying.
`close()` releases only the client's transport, including for vector storage.

Run the colocated NATS tests with `--import-mode=importlib`; shared regressions
are in `engine/nats_rpc_test.py` and `engine/nats_rpc_integration_test.py`.
The latter uses a local `nats-server` executable without Docker.
