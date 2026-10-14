"""JSON for the SysAdmin views: dataclass fields plus their computed properties."""

from __future__ import annotations

import dataclasses
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import (
    JetStreamStream,
    JetStreamSummary,
    KernelService,
    MicroServiceInstance,
)

COMPUTED: dict[type, tuple[str, ...]] = {
    KernelService: ("status",),
    MicroServiceInstance: ("requests", "errors"),
    JetStreamStream: ("kind",),
    JetStreamSummary: ("consumers", "messages"),
}


def to_json(value: Any) -> Any:
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        body = {f.name: to_json(getattr(value, f.name)) for f in dataclasses.fields(value)}
        for name in COMPUTED.get(type(value), ()):
            body[name] = to_json(getattr(value, name))
        return body
    if isinstance(value, dict):
        return {str(k): to_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_json(v) for v in value]
    return value
