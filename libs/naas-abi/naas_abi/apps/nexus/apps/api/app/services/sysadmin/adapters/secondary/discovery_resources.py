"""NATS discovery as a tree: modules are containers, registered instances are items.

Ids are ``<module_id>`` and ``<module_id>/<instance_id>`` (neither may contain
``/``). Reading an instance shows its descriptor as JSON. Deleting evicts the
registration (``DiscoveryClient.evict``, admin identities only): a live module
registers again under the same instance id on its next heartbeat, so eviction is
for crashed or stuck registrations. Nothing is written here: modules register
themselves.

SDK transports are bound to the event loop that created them, so one client is
kept per running loop (as in ``discovery_registry``).
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import weakref
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.job_summaries import (
    summarize_job,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import SourceUnavailable
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.resources import (
    Action,
    InvalidResource,
    ResourceCapabilities,
    ResourceDetail,
    ResourceEntry,
    ResourceNotFound,
    ResourcePage,
    UnsupportedOperation,
    paginate,
    text_preview,
)

SERVICE = "discovery"
PAGE_SIZE = 100
MAX_PAGES = 64  # the registry caps live instances at 256
ACTIONS: tuple[Action, ...] = ("read", "delete")


def _iso(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, tz=UTC).isoformat()


def _unavailable(exc: BaseException) -> SourceUnavailable:
    code = getattr(exc, "code", "") or type(exc).__name__
    message = str(exc)
    return SourceUnavailable(SERVICE, f"{code}: {message}" if message else code)


def _count(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def _names(items: Any) -> list[str]:
    return sorted({str(getattr(i, "name", i)) for i in items})


def _dependencies(instance: Any) -> list[str]:
    return sorted({m for m, _ in getattr(instance, "dependencies", ())})


def _matches(name: str, query: str | None) -> bool:
    return not query or query.lower() in name.lower()


def describe(instance: Any) -> dict[str, Any]:
    return {
        "module_id": instance.module_id,
        "instance_id": instance.instance_id,
        "package_version": instance.package_version,
        "contract_major": instance.contract_major,
        "status": instance.status,
        "lease_expires_at": _iso(float(instance.expires_at)),
        "dependencies": [
            {"module_id": m, "contract_major": c} for m, c in getattr(instance, "dependencies", ())
        ],
        "agents": [
            {
                "name": a.name,
                "description": a.description,
                "contract_major": a.contract_major,
                "capabilities": list(a.capabilities),
            }
            for a in instance.agents
        ],
        "jobs": [dataclasses.asdict(summarize_job(j)) for j in instance.jobs],
    }


class DiscoveryResources:
    service = SERVICE
    # Search filters the instances already fetched for the listing: no extra calls.
    capabilities = ResourceCapabilities(browse=True, search=True)

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

    async def _instances(self) -> list[Any]:
        found: list[Any] = []
        after = ""
        try:
            client = self._client()
            for _ in range(MAX_PAGES):
                instances, after = await client.list_modules(
                    limit=PAGE_SIZE, after_instance_id=after
                )
                found.extend(instances)
                if not after:
                    break
        except Exception as exc:  # noqa: BLE001 - RPC errors, timeouts, no broker
            raise _unavailable(exc) from exc
        return sorted(found, key=lambda i: (i.module_id, i.instance_id))

    @staticmethod
    def _entry(instance: Any) -> ResourceEntry:
        agents = _names(instance.agents)
        jobs = _names(instance.jobs)
        attributes = {
            "status": instance.status,
            "version": instance.package_version,
            "contract": str(instance.contract_major),
            "lease_expires_at": _iso(float(instance.expires_at)),
            "agents": ", ".join(agents),
            "jobs": ", ".join(jobs),
            "dependencies": ", ".join(_dependencies(instance)),
            "summary": " · ".join(
                [
                    f"v{instance.package_version}",
                    _count(len(agents), "agent", "agents"),
                    _count(len(jobs), "job", "jobs"),
                ]
            ),
        }
        return ResourceEntry(
            f"{instance.module_id}/{instance.instance_id}",
            instance.instance_id,
            "item",
            ACTIONS,
            attributes=attributes,
        )

    @staticmethod
    def _module(module_id: str, instances: list[Any]) -> ResourceEntry:
        statuses = Counter(i.status for i in instances)
        agents = sorted({name for i in instances for name in _names(i.agents)})
        jobs = sorted({name for i in instances for name in _names(i.jobs)})
        attributes = {
            "instances": str(len(instances)),
            "status": ", ".join(f"{s} {n}" for s, n in sorted(statuses.items())),
            "agents": ", ".join(agents),
            "jobs": ", ".join(jobs),
            "versions": ", ".join(sorted({i.package_version for i in instances})),
            "lease_expires_at": _iso(max(float(i.expires_at) for i in instances)),
            "summary": " · ".join(
                [
                    _count(len(instances), "instance", "instances"),
                    _count(len(agents), "agent", "agents"),
                    _count(len(jobs), "job", "jobs"),
                ]
            ),
        }
        # One attribute per status (``ready``, ``starting``...) for status pills.
        for status, n in statuses.items():
            attributes[str(status).lower()] = str(n)
        return ResourceEntry(module_id, module_id, "container", attributes=attributes)

    async def _find(self, resource_id: str) -> Any:
        module_id, _, instance_id = resource_id.partition("/")
        if not module_id or not instance_id or "/" in instance_id:
            raise ResourceNotFound(SERVICE, resource_id)
        for instance in await self._instances():
            if (instance.module_id, instance.instance_id) == (module_id, instance_id):
                return instance
        raise ResourceNotFound(SERVICE, resource_id)

    async def list(
        self, parent: str = "", *, cursor: str | None = None, limit: int = 100, **options: Any
    ) -> ResourcePage:
        query = options.get("query")
        instances = await self._instances()
        if parent == "":
            modules: dict[str, list[Any]] = {}
            for instance in instances:
                modules.setdefault(instance.module_id, []).append(instance)
            entries = [
                self._module(m, found) for m, found in sorted(modules.items()) if _matches(m, query)
            ]
            return paginate("", entries, cursor, limit)
        if "/" in parent:
            await self._find(parent)
            raise InvalidResource(SERVICE, f"{parent!r} is an instance")
        mine = [i for i in instances if i.module_id == parent]
        if not mine:
            raise ResourceNotFound(SERVICE, parent)
        entries = [self._entry(i) for i in mine if _matches(i.instance_id, query)]
        return paginate(parent, entries, cursor, limit)

    async def stat(self, resource_id: str) -> ResourceEntry:
        if resource_id == "":
            return ResourceEntry("", "", "container")
        if "/" not in resource_id:
            mine = [i for i in await self._instances() if i.module_id == resource_id]
            if not mine:
                raise ResourceNotFound(SERVICE, resource_id)
            return self._module(resource_id, mine)
        return self._entry(await self._find(resource_id))

    async def read(self, resource_id: str, *, reveal: bool = False) -> ResourceDetail:
        if "/" not in resource_id:
            await self.stat(resource_id)
            raise InvalidResource(SERVICE, f"{resource_id!r} is a module")
        instance = await self._find(resource_id)
        descriptor = describe(instance)
        body = json.dumps(descriptor, indent=2).encode()
        view = {
            "type": "status",
            "phase": instance.status,
            "fields": {
                "Module": instance.module_id,
                "Instance": instance.instance_id,
                "Version": instance.package_version,
                "Contract": f"v{instance.contract_major}",
                "Lease expires": descriptor["lease_expires_at"],
            },
            "lease_expires_at": descriptor["lease_expires_at"],
            "agents": [
                {k: a[k] for k in ("name", "description", "capabilities")}
                for a in descriptor["agents"]
            ],
            "jobs": descriptor["jobs"],
            "dependencies": descriptor["dependencies"],
        }
        return ResourceDetail(self._entry(instance), text_preview(body), view=view)

    async def download(self, resource_id: str, *, max_bytes: int) -> bytes:
        raise UnsupportedOperation(SERVICE, "download")

    async def write(self, resource_id: str, content: bytes) -> ResourceEntry:
        raise UnsupportedOperation(SERVICE, "write")

    async def delete(self, resource_id: str) -> None:
        if "/" not in resource_id:
            await self.stat(resource_id)
            raise UnsupportedOperation(SERVICE, "evict a whole module")
        instance = await self._find(resource_id)
        try:
            await self._client().evict(instance.instance_id)
        except Exception as exc:  # noqa: BLE001 - mapped by RPC error code below
            code = getattr(exc, "code", "")
            if code == "INSTANCE_NOT_FOUND":
                raise ResourceNotFound(SERVICE, resource_id) from exc
            if code == "PERMISSION_DENIED":
                raise SourceUnavailable(
                    SERVICE,
                    "discovery refused the eviction: this API's identity is not one "
                    "of its admin identities",
                ) from exc
            raise _unavailable(exc) from exc
