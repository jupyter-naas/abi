# EngineConfiguration_SecretService

## What it is
Pydantic-based configuration models for wiring the `Secret` service with one or more secret adapters (dotenv, Naas, base64-wrapped, or custom via `GenericLoader`).

## Public API
- `DotenvSecretConfiguration (BaseModel)`
  - Purpose: Configure loading secrets from a `.env` file.
  - Fields:
    - `path: str = ".env"`
- `NaasSecretConfiguration (BaseModel)`
  - Purpose: Configure loading secrets from Naas API.
  - Fields:
    - `naas_api_key: str`
    - `naas_api_url: str`
- `Base64SecretConfiguration (BaseModel)`
  - Purpose: Configure a base64 secret adapter that wraps another secret adapter.
  - Fields:
    - `secret_adapter: SecretAdapterConfiguration`
    - `base64_secret_key: str`
  - Methods:
    - `load() -> Base64Secret`: Constructs `Base64Secret(self.secret_adapter.load(), self.base64_secret_key)`.
- `SecretAdapterConfiguration (GenericLoader)`
  - Purpose: Select and validate a secret adapter type and construct the corresponding adapter instance.
  - Fields:
    - `adapter: Literal["dotenv", "naas", "base64", "custom"]`
    - `config: DotenvSecretConfiguration | NaasSecretConfiguration | Base64SecretConfiguration | None = None`
  - Methods:
    - `validate_adapter() -> Self`: Enforces `config` presence for non-`custom` adapters and validates config model type for `dotenv`, `naas`, `base64`.
    - `load() -> ISecretAdapter`: Lazily imports and instantiates the configured adapter; delegates to `GenericLoader.load()` when `adapter == "custom"`.
- `SecretServiceConfiguration (BaseModel)`
  - Purpose: Top-level configuration for the `Secret` service.
  - Fields:
    - `secret_adapters: List[SecretAdapterConfiguration]`
  - Methods:
    - `load() -> Secret`: Builds `Secret(adapters=[adapter.load() ...])`.

## Configuration/Dependencies
- Uses **Pydantic v2** (`BaseModel`, `model_validator`, `ConfigDict(extra="forbid")`).
- Adapter implementations are imported lazily:
  - `dotenv` → `DotenvSecretSecondaryAdaptor`
  - `naas` → `NaasSecret`
  - `base64` → `Base64Secret` (wraps another adapter)
- `custom` adapter relies on `GenericLoader` behavior (not defined in this file).
- Validation helper: `pydantic_model_validator(...)` is used to validate `config` against the expected model.

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

secret_service = cfg.load()  # returns naas_abi_core.services.secret.Secret.Secret
```

## Caveats
- For `adapter != "custom"`, `config` is required (assertion).
- For `adapter == "base64"`, `config` must be a `Base64SecretConfiguration` and must provide `load()` (assertions).
- All config models shown set `extra="forbid"`; unknown fields will fail validation.
