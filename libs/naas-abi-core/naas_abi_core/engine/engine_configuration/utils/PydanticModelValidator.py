from typing import Any

from naas_abi_core.utils.Logger import logger
from pydantic import BaseModel, ValidationError


def pydantic_model_validator(model: Any, payload: Any, message: str):
    if not isinstance(model, type) or not issubclass(model, BaseModel):
        raise TypeError(
            "The model argument must be a class that inherits from pydantic.BaseModel"
        )
    try:
        model.model_validate(payload)
    except ValidationError as e:
        logger.error(f"{message}: {e}")
