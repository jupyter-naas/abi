# EmailServiceConfiguration

## What it is
Configuration models and loader logic for wiring an `EmailService` with an email adapter (built-in SMTP or a custom adapter).

## Public API
- `EmailAdapterSMTPConfiguration` (Pydantic model)
  - Purpose: Validate SMTP adapter settings.
  - Fields (defaults):
    - `host: str = "localhost"`
    - `port: int = 1025`
    - `username: str | None = None`
    - `password: str | None = None`
    - `use_tls: bool = False`
    - `use_ssl: bool = False`
    - `timeout: int = 10`
  - Behavior: forbids unknown fields (`extra="forbid"`).

- `EmailAdapterConfiguration` (inherits `GenericLoader`)
  - Purpose: Select and instantiate an `IEmailAdapter`.
  - Fields:
    - `adapter: Literal["smtp", "custom"]`
    - `config: dict | None = None`
  - Methods:
    - `validate_adapter(self) -> EmailAdapterConfiguration` (Pydantic `@model_validator(mode="after")`)
      - Ensures `config` is present when `adapter` is not `"custom"`.
      - Validates `config` against `EmailAdapterSMTPConfiguration` when `adapter == "smtp"`.
    - `load(self) -> IEmailAdapter`
      - `"smtp"`: imports and returns `SMTPAdapter(**config)`.
      - `"custom"`: delegates to `GenericLoader.load()`.
      - Otherwise: raises `ValueError("Unknown adapter: ...")`.

- `EmailServiceConfiguration` (Pydantic model)
  - Purpose: Build an `EmailService` instance.
  - Fields:
    - `email_adapter: EmailAdapterConfiguration`
  - Methods:
    - `load(self) -> EmailService`: returns `EmailService(adapter=self.email_adapter.load())`.

## Configuration/Dependencies
- Depends on:
  - `pydantic` (`BaseModel`, `ConfigDict`, `model_validator`)
  - `naas_abi_core.engine.engine_configuration.EngineConfiguration_GenericLoader.GenericLoader` (used for custom adapter loading)
  - `naas_abi_core.engine.engine_configuration.utils.PydanticModelValidator.pydantic_model_validator` (used for SMTP config validation)
  - `naas_abi_core.services.email.EmailService.EmailService`
  - `naas_abi_core.services.email.EmailPorts.IEmailAdapter`
  - `naas_abi_core.services.email.adapters.secondary.SMTPAdapter.SMTPAdapter` (imported only when `adapter == "smtp"`)

## Usage
```python
from naas_abi_core.engine.engine_configuration.EngineConfiguration_EmailService import (
    EmailServiceConfiguration,
)

cfg = EmailServiceConfiguration(
    email_adapter={
        "adapter": "smtp",
        "config": {
            "host": "localhost",
            "port": 1025,
            "use_tls": False,
            "use_ssl": False,
            "timeout": 10,
        },
    }
)

email_service = cfg.load()
```

## Caveats
- For `adapter="smtp"`, `config` is required and must match `EmailAdapterSMTPConfiguration`; extra keys are rejected.
- For any `adapter` other than `"custom"`, `config` must be provided.
- `"custom"` adapter resolution is delegated to `GenericLoader.load()`; the required shape of `config` depends on `GenericLoader` and the custom adapter implementation.
