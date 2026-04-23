# EngineConfiguration_SecretService

## What it is
Pydantic-based configuration models for wiring the `Secret` service with one or more secret adapters (`dotenv`, `naas`, `base64`, or `custom`). Provides validation and lazy loading of the configured adapter implementations.

## Public API
- `DotenvSecretConfiguration` (Pydantic model)
  - Purpose: Configuration for the `dotenv` secret adapter.
  - Fields:
    - `path: str = ".env"`: Path to the dotenv file.

- `NaasSecretConfiguration` (Pydantic model)
  - Purpose: Configuration for the `naas` secret adapter.
  - Fields:
    - `naas_api_key: str`
    - `naas_api_url: str`

- `Base64SecretConfiguration` (Pydantic model)
  - Purpose: Configuration for the `base64` adapter, which wraps another secret adapter.
  - Fields:
    - `secret_adapter: SecretAdapterConfiguration`: The underlying adapter configuration to wrap.
    - `base64_secret_key: str`
  - Methods:
    - `load() -> Base64Secret`: Instantiates the `Base64Secret` adapter (lazy import).

- `SecretAdapterConfiguration` (`GenericLoader`)
  - Purpose: Selects and validates an adapter type and loads an `ISecretAdapter`.
  - Fields:
    - `adapter: Literal["dotenv", "naas", "base64", "custom"]`
    - `config: DotenvSecretConfiguration | NaasSecretConfiguration | Base64SecretConfiguration | None`
  - Methods:
    - `validate_adapter() -> Self`: Ensures `config` is present for non-`custom` adapters and validates it against the expected config model.
    - `load() -> ISecretAdapter`: Lazily imports and instantiates the configured adapter; for `custom`, delegates to `GenericLoader.load()`.

- `SecretServiceConfiguration` (Pydantic model)
  - Purpose: Top-level configuration for the `Secret` service.
  - Fields:
    - `secret_adapters: List[SecretAdapterConfiguration]`
  - Methods:
    - `load() -> Secret`: Builds a `Secret` instance with all configured adapters loaded.

## Configuration/Dependencies
- Depends on:
  - `pydantic` (`BaseModel`, `ConfigDict`, `model_validator`)
  - `naas_abi_core.services.secret.Secret.Secret`
  - `naas_abi_core.services.secret.SecretPorts.ISecretAdapter`
  - Adapter implementations (loaded lazily):
    - `DotenvSecretSecondaryAdaptor`
    - `NaasSecret`
    - `Base64Secret`
- Validation behavior:
  - Extra fields are forbidden in `DotenvSecretConfiguration`, `NaasSecretConfiguration`, and `Base64SecretConfiguration` (`extra="forbid"`).
  - For `adapter != "custom"`, `config` must be provided.

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
- `SecretAdapterConfiguration.config` is required unless `adapter="custom"`; otherwise an assertion error is raised.
- Adapter imports are lazy; missing optional adapter packages/modules will only error when `load()` is called for that adapter.
- For `adapter="base64"`, `config` must be a `Base64SecretConfiguration` and must provide a `load()` method (asserted at runtime).
