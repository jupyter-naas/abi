# pydantic_model_validator

## What it is
A small utility function that validates a payload against a given **Pydantic `BaseModel` class**, logs validation errors, and re-raises them.

## Public API
- `pydantic_model_validator(model: Any, payload: Any, message: str) -> None`
  - Validates `payload` using `model.model_validate(payload)`.
  - Ensures `model` is a **class** and a **subclass of `pydantic.BaseModel`**.
  - On validation failure:
    - Logs an error via `naas_abi_core.utils.Logger.logger`.
    - Re-raises the original `pydantic.ValidationError`.

## Configuration/Dependencies
- **Dependencies**
  - `pydantic.BaseModel` and `pydantic.ValidationError`
  - `naas_abi_core.utils.Logger.logger` (must be available/importable)
- **Pydantic version note**
  - Uses `model.model_validate(...)`, which is the Pydantic v2 validation API.

## Usage
```python
from pydantic import BaseModel
from naas_abi_core.engine.engine_configuration.utils.PydanticModelValidator import (
    pydantic_model_validator,
)

class User(BaseModel):
    id: int
    name: str

payload = {"id": 1, "name": "Ada"}

# Raises ValidationError on invalid payload, otherwise returns None
pydantic_model_validator(User, payload, message="Invalid user payload")
```

## Caveats
- `model` must be a **class**, not an instance (must satisfy `isinstance(model, type)`).
- `model` must inherit from `pydantic.BaseModel`; otherwise a `TypeError` is raised.
- The function does not return the validated model instance; it only validates and raises on failure.
