"""Job definitions from engine modules and from NATS discovery (SDK descriptors)."""

from __future__ import annotations

import asyncio
import weakref
from collections.abc import Callable, Mapping
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.sysadmin.jobs import (
    JobDefinition,
    Location,
    TriggerSpec,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import SourceUnavailable

PAGE_SIZE = 100
MAX_PAGES = 64


def trigger_spec(trigger: Any) -> TriggerSpec:
    """Cron, Every and OnEvent (SDK or core stand-ins) as plain values."""
    kind = str(getattr(trigger, "kind", "") or "")
    spec = (
        getattr(trigger, "spec", None)
        or getattr(trigger, "expression", None)
        or getattr(trigger, "interval", None)
        or getattr(trigger, "subject", None)
        or ""
    )
    return TriggerSpec(kind, str(spec), str(getattr(trigger, "time_zone", "") or ""))


def definition(
    module_id: str, descriptor: Any, location: Location, instances: int = 1
) -> JobDefinition:
    timeout = getattr(descriptor, "timeout", None)
    return JobDefinition(
        module_id=module_id,
        name=str(descriptor.name),
        description=str(getattr(descriptor, "description", "") or ""),
        location=location,
        triggers=tuple(trigger_spec(t) for t in getattr(descriptor, "triggers", ()) or ()),
        max_concurrency=int(getattr(descriptor, "max_concurrency", 1) or 1),
        max_attempts=int(getattr(descriptor, "max_attempts", 1) or 1),
        timeout_seconds=timeout.total_seconds() if timeout is not None else None,
        instances=instances,
    )


class EngineJobCatalog:
    """Jobs of the modules loaded in this engine (hosted in-process)."""

    source = "engine"

    def __init__(self, modules: Callable[[], Mapping[str, Any]]) -> None:
        self._modules = modules

    async def list_jobs(self) -> list[JobDefinition]:
        found: list[JobDefinition] = []
        for module_id, module in sorted(self._modules().items()):
            try:
                descriptors = tuple(getattr(module, "jobs", ()) or ())
            except Exception:  # noqa: BLE001 - one broken module must not hide the others
                continue
            found.extend(definition(module_id, d, "engine") for d in descriptors)
        return found


class DiscoveryJobCatalog:
    """Jobs of remote modules registered in discovery, one per (module, job)."""

    source = "discovery"

    def __init__(self, discovery_factory: Callable[[], Any]) -> None:
        self._factory = discovery_factory
        self._clients: weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, Any] = (
            weakref.WeakKeyDictionary()
        )

    def _client(self) -> Any:
        loop = asyncio.get_running_loop()
        if loop not in self._clients:
            self._clients[loop] = self._factory()
        return self._clients[loop]

    async def list_jobs(self) -> list[JobDefinition]:
        descriptors: dict[tuple[str, str], Any] = {}
        instances: dict[tuple[str, str], int] = {}
        after = ""
        try:
            client = self._client()
            for _ in range(MAX_PAGES):
                page, after = await client.list_modules(limit=PAGE_SIZE, after_instance_id=after)
                for instance in page:
                    for descriptor in instance.jobs:
                        key = (instance.module_id, descriptor.name)
                        descriptors.setdefault(key, descriptor)
                        instances[key] = instances.get(key, 0) + 1
                if not after:
                    break
        except Exception as exc:  # noqa: BLE001 - RPC errors, timeouts, no broker
            code = getattr(exc, "code", "") or type(exc).__name__
            raise SourceUnavailable("discovery", f"{code}: {exc}" if str(exc) else code) from exc
        return [
            definition(module_id, descriptor, "remote", instances[(module_id, name)])
            for (module_id, name), descriptor in sorted(descriptors.items())
        ]
