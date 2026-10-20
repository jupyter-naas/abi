"""Remote module instances from NATS discovery (SDK ``DiscoveryClient``).

SDK transports are bound to the event loop that created them, so one client is
kept per running loop.
"""

from __future__ import annotations

import asyncio
import weakref
from collections.abc import Callable
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.job_summaries import (
    summarize_job,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import (
    RemoteModuleInstance,
    SourceUnavailable,
)

PAGE_SIZE = 100
MAX_PAGES = 64  # the registry caps live instances at 256


class DiscoveryModuleRegistry:
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

    async def list_instances(self) -> list[RemoteModuleInstance]:
        found: list[RemoteModuleInstance] = []
        after = ""
        try:
            client = self._client()
            for _ in range(MAX_PAGES):
                instances, after = await client.list_modules(
                    limit=PAGE_SIZE, after_instance_id=after
                )
                found.extend(
                    RemoteModuleInstance(
                        module_id=i.module_id,
                        instance_id=i.instance_id,
                        package_version=i.package_version,
                        contract_major=i.contract_major,
                        status=i.status,
                        expires_at=float(i.expires_at),
                        agents=tuple(a.name for a in i.agents),
                        jobs=tuple(summarize_job(j) for j in i.jobs),
                    )
                    for i in instances
                )
                if not after:
                    break
        except Exception as exc:  # noqa: BLE001 - RPC errors, timeouts, no broker
            code = getattr(exc, "code", "") or type(exc).__name__
            message = str(exc)
            raise SourceUnavailable("discovery", f"{code}: {message}" if message else code) from exc
        return sorted(found, key=lambda i: (i.module_id, i.instance_id))
