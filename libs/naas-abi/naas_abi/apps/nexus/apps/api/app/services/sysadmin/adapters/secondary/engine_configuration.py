"""Kernel services as configured in the engine (``EngineConfiguration.services``).

Only adapter kinds are read (``postgresql``, ``redis:hot``...): adapter settings
hold credentials and never leave this adapter.
"""

from __future__ import annotations

from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import ServiceConfiguration


def _fields(value: Any) -> list[str]:
    model_fields = getattr(type(value), "model_fields", None)
    if model_fields is not None:
        return list(model_fields)
    return [name for name in vars(value) if not name.startswith("_")]


def _kind(entry: Any) -> str | None:
    kind = getattr(entry, "adapter", None)
    if not isinstance(kind, str) or not kind:
        return None
    tier = getattr(entry, "tier", None)
    return f"{kind}:{tier}" if isinstance(tier, str) and tier else kind


def adapter_kinds(service: Any) -> tuple[str, ...]:
    """``x_adapter`` (one), ``x_adapters`` (a fanout) or ``adapters`` (cache tiers)."""
    kinds: list[str] = []
    for name in _fields(service):
        if not (name.endswith("_adapter") or name.endswith("_adapters") or name == "adapters"):
            continue
        value = getattr(service, name, None)
        entries = value if isinstance(value, (list, tuple)) else [value]
        kinds.extend(k for k in (_kind(e) for e in entries) if k)
    return tuple(kinds)


class EngineServiceConfiguration:
    def __init__(self, services: Any) -> None:
        self._services = services

    async def list_configured(self) -> list[ServiceConfiguration]:
        return [
            ServiceConfiguration(name, adapter_kinds(getattr(self._services, name)))
            for name in _fields(self._services)
        ]
