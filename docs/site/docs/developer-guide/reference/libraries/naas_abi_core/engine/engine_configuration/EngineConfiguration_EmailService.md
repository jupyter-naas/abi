# EmailServiceConfiguration

## What it is
Configuration models and loader logic for wiring an `EmailService` with a selectable email adapter (SMTP, filesystem, SES, SendGrid, Microsoft Outlook, NATS RPC, or a custom adapter).

## Public API
- `EmailAdapterSMTPConfiguration` (`pydantic.BaseModel`)
  - Purpose: Validate SMTP adapter settings.
  - Fields (defaults):
    - `host: str = "localhost"`
    - `port: int = 1025`
    - `username: str | None = None`
    - `password: str | None = None`
    - `use_tls: bool = False`
    - `use_ssl: bool = False`
    - `timeout: int = 10`
  - Notes: forbids unknown fields (`extra="forbid"`).

- `EmailAdapterFilesystemConfiguration` (`pydantic.BaseModel`)
  - Purpose: Validate filesystem adapter settings.
  - Fields (defaults):
    - `directory: str = "storage/email"`
  - Notes: forbids unknown fields.

- `EmailAdapterSESConfiguration` (`pydantic.BaseModel`)
  - Purpose: Validate AWS SES adapter settings.
  - Fields (all optional):
    - `region_name`, `aws_access_key_id`, `aws_secret_access_key`, `aws_session_token`
  - Notes: forbids unknown fields.

- `EmailAdapterSendGridConfiguration` (`pydantic.BaseModel`)
  - Purpose: Validate SendGrid adapter settings.
  - Fields:
    - `api_key: str` (required)
    - `base_url: str = "https://api.sendgrid.com/v3"`
  - Notes: forbids unknown fields.

- `EmailAdapterMicrosoftOutlookConfiguration` (`pydantic.BaseModel`)
  - Purpose: Validate Microsoft Outlook adapter settings.
  - Fields (required):
    - `tenant_id: str`, `client_id: str`, `client_secret: str`, `user: str`
  - Notes: forbids unknown fields.

- `EmailAdapterNATSConfiguration` (`pydantic.BaseModel`)
  - Purpose: Validate NATS RPC client adapter settings.
  - Fields:
    - `nats_url: str = "nats://127.0.0.1:4222"`
    - `jwt_secret: str` (required)
    - `service_identity: str = "api"`
  - Notes: forbids unknown fields.

- `EmailAdapterConfiguration` (`GenericLoader`)
  - Purpose: Select and instantiate an `IEmailAdapter`.
  - Fields:
    - `adapter: Literal["smtp", "filesystem", "ses", "sendgrid", "microsoft_outlook", "nats_rpc", "custom"]`
    - `config: dict | None = None`
  - Methods:
    - `validate_adapter(self) -> EmailAdapterConfiguration` (Pydantic `@model_validator(mode="after")`)
      - Ensures `config` is present when `adapter != "custom"`.
      - Validates `config` against the corresponding adapter configuration model using `pydantic_model_validator(...)`.
    - `load(self) -> IEmailAdapter`
      - Instantiates:
        - `"smtp"` → `SMTPAdapter(**config)`
        - `"filesystem"` → `FilesystemAdapter(**config)`
        - `"ses"` → `SESAdapter(**config)`
        - `"sendgrid"` → `SendGridAdapter(**config)`
        - `"microsoft_outlook"` → `MicrosoftOutlookAdapter(**config)`
        - `"nats_rpc"` → `EmailSecondaryAdapterNATSClient(**config)`
        - `"custom"` → delegated to `GenericLoader.load()`
      - Raises `ValueError` for unknown adapter values.
    - `local_storage(self) -> str | None`
      - `"filesystem"` → returns `"files under {directory}"` (directory derived via `config_model(...)`)
      - `"custom"` → returns `self.custom_local_storage()`
      - Otherwise → `None`

- `EmailServiceConfiguration` (`pydantic.BaseModel`)
  - Purpose: Build an `EmailService` instance.
  - Fields:
    - `email_adapter: EmailAdapterConfiguration`
  - Methods:
    - `load(self) -> EmailService`: returns `EmailService(adapter=self.email_adapter.load())`.

## Configuration/Dependencies
- Depends on:
  - `pydantic` (`BaseModel`, `ConfigDict`, `model_validator`)
  - `naas_abi_core.engine.engine_configuration.EngineConfiguration_GenericLoader.GenericLoader`
  - `naas_abi_core.engine.engine_configuration.EngineConfiguration_GenericLoader.config_model`
  - `naas_abi_core.engine.engine_configuration.utils.PydanticModelValidator.pydantic_model_validator`
  - `naas_abi_core.services.email.EmailService.EmailService`
  - `naas_abi_core.services.email.EmailPorts.IEmailAdapter`
- Adapter implementations are imported lazily inside `EmailAdapterConfiguration.load()`.

## Usage
```python
from naas_abi_core.engine.engine_configuration.EngineConfiguration_EmailService import (
    EmailServiceConfiguration,
)

cfg = EmailServiceConfiguration(
    email_adapter={
        "adapter": "smtp",
        "config": {"host": "localhost", "port": 1025, "timeout": 10},
    }
)

email_service = cfg.load()
```

## Caveats
- For any `adapter` other than `"custom"`, `config` is required (assertion failure otherwise).
- Adapter `config` dictionaries are strictly validated; extra keys are rejected (`extra="forbid"` on the configuration models).
- `"custom"` adapter loading and storage reporting are delegated to `GenericLoader` (`load()` and `custom_local_storage()`), so required `config` shape depends on that loader and the custom implementation.
