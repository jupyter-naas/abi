"""The platform services set in the ``services:`` section of ``config.yaml``.

Only service names and adapter names are read: adapter ``config`` blocks hold
credentials (passwords, tokens, URLs with secrets) and are never returned.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


def _adapter_name(value: Any) -> str | None:
    name = getattr(value, "adapter", None)
    return name if isinstance(name, str) else None


def _adapters(service: BaseModel) -> list[str]:
    names: list[str] = []
    for field in type(service).model_fields:
        value = getattr(service, field)
        if isinstance(value, list):
            names.extend(name for name in map(_adapter_name, value) if name)
        elif (name := _adapter_name(value)) is not None:
            names.append(name)
    return names


def configured_services(services: BaseModel) -> list[dict[str, Any]]:
    """Services present in the config file (not engine defaults), in declaration order."""
    return [
        {"id": field, "adapters": _adapters(getattr(services, field))}
        for field in type(services).model_fields
        if field in services.model_fields_set and isinstance(getattr(services, field), BaseModel)
    ]
