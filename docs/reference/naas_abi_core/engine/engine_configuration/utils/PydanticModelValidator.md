# PydanticModelValidator

## What it is
A small utility function that validates a payload against a Pydantic `BaseModel` class. It logs validation errors and re-raises them.

## Public API
- `pydantic_model_validator(model: Any, payload: Any, message: str) -> None`
  - Validates `payload` using `model.model_validate(payload)`.
  - Ensures `model` is a class and a subclass of `pydantic.BaseModel`.
  - On validation failure:
    - Logs an error via `naas_abi_core.utils.Logger.logger.error`.
    - Re-raises the original `pydantic.ValidationError`.

## Configuration/Dependencies
- Depends on:
  - `pydantic.BaseModel`
  - `pydantic.ValidationError`
  - `naas_abi_core.utils.Logger.logger` (must be configured elsewhere for logging output)

## Usage
```python
from pydantic import BaseModel
from naas_abi_core.engine.engine_configuration.utils.PydanticModelValidator import (
    pydantic_model_validator,
)

class User(BaseModel):
    id: int
    name: str

payload = {"id": 1, "name": "Alice"}
pydantic_model_validator(User, payload, "Invalid user payload")  # returns None on success
```

## Caveats
- `model` must be a **class** (not an instance) and must inherit from `pydantic.BaseModel`; otherwise a `TypeError` is raised.
- The function does not return the validated model instance; it only validates and raises on error.
