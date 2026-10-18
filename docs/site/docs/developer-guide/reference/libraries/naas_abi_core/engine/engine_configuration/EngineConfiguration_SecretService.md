# EngineConfiguration_SecretService

## What it is
Pydantic-based configuration models to wire the `Secret` service with one or more secret adapters. Supports `dotenv`, `naas`, `base64`, `nats_rpc` (validated only), and `custom` (delegated to `GenericLoader`). Adapter implementations are imported lazily when `load()` is called.

## Public API

- `DotenvSecretConfiguration` (`pydantic.BaseModel`)
  - Purpose: Configure the `dotenv` secret adapter.
  - Fields:
    - `path: str = ".env"`
  - Notes: `extra="forbid"`.

- `NaasSecretConfiguration` (`pydantic.BaseModel`)
  - Purpose: Configure the `naas` secret adapter.
  - Fields:
    - `naas_api_key: str`
    - `naas_api_url: str`
  - Notes: `extra="forbid"`.

- `Base64SecretConfiguration` (`pydantic.BaseModel`)
  - Purpose: Configure the `base64` adapter, which wraps another configured adapter.
  - Fields:
    - `secret_adapter: SecretAdapterConfiguration`
    - `base64_secret_key: str`
  - Methods:
    - `load() -> Base64Secret`: Instantiates `Base64Secret(self.secret_adapter.load(), self.base64_secret_key)` via lazy import.
  - Notes: `extra="forbid"`.

- `SecretAdapterNATSConfiguration` (`pydantic.BaseModel`)
  - Purpose: Configure a NATS RPC client adapter (configuration + validation only in this file).
  - Fields:
    - `nats_url: str = "nats://127.0.0.1:4222"`
    - `jwt_secret: str`
    - `service_identity: str = "api"`
  - Notes: `extra="forbid"`. This file does **not** implement loading for `nats_rpc`.

- `SecretAdapterConfiguration` (`GenericLoader`)
  - Purpose: Select and validate an adapter type, then load an `ISecretAdapter`.
  - Fields:
    - `adapter: Literal["dotenv", "naas", "base64", "nats_rpc", "custom"]`
    - `config: DotenvSecretConfiguration | NaasSecretConfiguration | Base64SecretConfiguration | SecretAdapterNATSConfiguration | None = None`
  - Methods:
    - `validate_adapter() -> Self`: Enforces presence/type of `config` for non-`custom` adapters using `pydantic_model_validator`.
    - `load() -> ISecretAdapter`:
      - `dotenv`: loads `DotenvSecretSecondaryAdaptor(**config.model_dump())`
      - `naas`: loads `NaasSecret(**config.model_dump())`
      - `base64`: delegates to `Base64SecretConfiguration.load()`
      - `custom`: delegates to `GenericLoader.load()`
      - `nats_rpc`: **not supported here** (falls into `Unknown adapter` error)
    - `local_storage() -> str | None`: returns `None` for built-ins; for `custom`, delegates to `custom_local_storage()`.

- `SecretServiceConfiguration` (`pydantic.BaseModel`)
  - Purpose: Top-level configuration for the `Secret` service.
  - Fields:
    - `secret_adapters: list[SecretAdapterConfiguration]`
  - Methods:
    - `load() -> Secret`: returns `Secret(adapters=[adapter.load() for adapter in self.secret_adapters])`.

## Configuration/Dependencies
- Depends on:
  - `pydantic` (`BaseModel`, `ConfigDict`, `model_validator`)
  - `naas_abi_core.engine.engine_configuration.EngineConfiguration_GenericLoader.GenericLoader`
  - `naas_abi_core.engine.engine_configuration.utils.PydanticModelValidator.pydantic_model_validator`
  - `naas_abi_core.services.secret.Secret.Secret`
  - `naas_abi_core.services.secret.SecretPorts.ISecretAdapter`
- Lazy-loaded adapter implementations:
  - `DotenvSecretSecondaryAdaptor`
  - `NaasSecret`
  - `Base64Secret`

## Usage
```python
from naas_abi_core.engine.engine_configuration.EngineConfiguration_SecretService import (
    SecretServiceConfiguration,
    SecretAdapterConfiguration,
    DotenvSecretConfiguration,
)

cfg = SecretServiceConfiguration(
    secret_adapters=[
        SecretAdapterConfiguration(
            adapter="dotenv",
            config=DotenvSecretConfiguration(path=".env"),
        )
    ]
)

secret_service = cfg.load()  # naas_abi_core.services.secret.Secret.Secret
```

## Caveats
- For `adapter != "custom"`, `config` is required (assertion).
- `adapter="nats_rpc"` is validated but **cannot be loaded** by `SecretAdapterConfiguration.load()` in this file (will raise `ValueError("Unknown adapter: nats_rpc")`).
- Adapter imports are lazy; missing optional modules will fail at `load()` time.
- `extra="forbid"` on the configuration models rejects unknown fields.
