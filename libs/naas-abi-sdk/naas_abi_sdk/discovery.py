"""Portable discovery values, logical module proxies and runner registration."""

from __future__ import annotations

import asyncio
import logging
import math
import random
import re
import time
from dataclasses import dataclass
from uuid import uuid4

from naas_abi_proto.discovery.v1 import discovery_pb2 as pb
from nats.errors import Error as NATSError

from naas_abi_sdk.transport import RPCError, Transport


@dataclass(frozen=True)
class AgentDescriptor:
    name: str
    description: str = ""
    contract_major: int = 1
    capabilities: tuple[str, ...] = ()


@dataclass(frozen=True)
class ModuleInstance:
    module_id: str
    instance_id: str
    package_version: str
    contract_major: int
    status: str
    expires_at: float
    agents: tuple[AgentDescriptor, ...]


def _instance(value: pb.Instance) -> ModuleInstance:
    d = value.descriptor
    return ModuleInstance(
        d.module_id,
        value.instance_id,
        d.package_version,
        d.contract_major,
        value.status,
        value.expires_at,
        tuple(
            AgentDescriptor(
                a.name, a.description, a.contract_major, tuple(a.capabilities)
            )
            for a in d.agents
        ),
    )


@dataclass(frozen=True)
class DiscoveryConfiguration:
    project: str = "default"
    startup_timeout: float = 60
    refresh_seconds: float = 2

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", self.project):
            raise ValueError("Invalid discovery project")
        if any(
            not math.isfinite(v) or v <= 0
            for v in (self.startup_timeout, self.refresh_seconds)
        ):
            raise ValueError("Discovery timeouts must be finite and positive")


class DiscoveryClient:
    def __init__(self, transport: Transport, project: str = "default"):
        DiscoveryConfiguration(project=project)
        self.transport, self.project = transport, project

    async def _call(self, operation: str, request, response):
        return await self.transport.call(
            f"abi.discovery.{self.project}.v1.{operation}", request, response
        )

    async def get_module(
        self, module_id: str, contract_major: int = 1
    ) -> tuple[ModuleInstance, ...]:
        result = await self._call(
            "get_module",
            pb.GetModuleRequest(module_id=module_id, contract_major=contract_major),
            pb.GetModuleResponse,
        )
        return tuple(_instance(i) for i in result.instances)

    async def list_modules(
        self, *, limit: int = 100, after_instance_id: str = ""
    ) -> tuple[tuple[ModuleInstance, ...], str]:
        result = await self._call(
            "list_modules",
            pb.ListModulesRequest(limit=limit, after_instance_id=after_instance_id),
            pb.ListModulesResponse,
        )
        return tuple(
            _instance(i) for i in result.instances
        ), result.next_after_instance_id


class ModuleProxy:
    def __init__(
        self, client: DiscoveryClient, module_id: str, contract_major: int = 1
    ):
        self.client, self.module_id, self.contract_major = (
            client,
            module_id,
            contract_major,
        )

    async def instances(self) -> tuple[ModuleInstance, ...]:
        return await self.client.get_module(self.module_id, self.contract_major)

    async def ready_instances(self) -> tuple[ModuleInstance, ...]:
        ready = tuple(i for i in await self.instances() if i.status == "READY")
        if not ready:
            raise RPCError(
                "MODULE_UNAVAILABLE", f"{self.module_id} has no ready instances"
            )
        return ready

    async def list_agents(self) -> tuple[AgentDescriptor, ...]:
        return (await self.ready_instances())[0].agents


class ModulesProxy:
    def __init__(self, client: DiscoveryClient, dependencies: tuple[str, ...]):
        self._modules = {name: ModuleProxy(client, name) for name in dependencies}

    def __getitem__(self, name: str) -> ModuleProxy:
        if name not in self._modules:
            raise ValueError(f"Module did not declare module dependency: {name}")
        return self._modules[name]

    async def wait_ready(self, config: DiscoveryConfiguration) -> None:
        async def wait():
            while True:
                pending = False
                for proxy in self._modules.values():
                    try:
                        await proxy.ready_instances()
                    except RPCError as exc:
                        if exc.code not in (
                            "MODULE_NOT_FOUND",
                            "MODULE_UNAVAILABLE",
                            "INCOMPATIBLE_MODULE",
                            "UNAVAILABLE",
                            "REGISTRY_BUSY",
                        ):
                            raise
                        pending = True
                    except (NATSError, asyncio.TimeoutError, OSError):
                        pending = True
                if not pending:
                    return
                await asyncio.sleep(config.refresh_seconds)

        try:
            await asyncio.wait_for(wait(), config.startup_timeout)
        except asyncio.TimeoutError as exc:
            raise RPCError(
                "DEPENDENCY_TIMEOUT",
                f"Required modules did not become ready within {config.startup_timeout}s: {tuple(self._modules)}",
            ) from exc


class DiscoverySession:
    def __init__(self, client: DiscoveryClient, descriptor: pb.ModuleDescriptor):
        self.client, self.descriptor = client, descriptor
        self.instance_id, self.lease_token = str(uuid4()), uuid4().hex
        self.initialized, self.draining = False, False
        self.lease_seconds, self.confirmed_until = 20.0, 0.0
        self._lock = asyncio.Lock()
        self.task: asyncio.Task | None = None
        self.status = "STARTING"

    @property
    def current_status(self) -> str:
        return self.status if time.monotonic() < self.confirmed_until else "UNAVAILABLE"

    async def register(self) -> None:
        started = time.monotonic()
        result = await self.client._call(
            "register",
            pb.RegisterRequest(
                descriptor=self.descriptor,
                instance_id=self.instance_id,
                lease_token=self.lease_token,
            ),
            pb.RegisterResponse,
        )
        self.lease_seconds = result.lease_seconds
        self.confirmed_until = started + result.lease_seconds
        self.status = result.instance.status

    async def start(self) -> None:
        await self.register()
        self.task = asyncio.create_task(self._heartbeat())

    async def renew(self) -> None:
        async with self._lock:
            started = time.monotonic()
            result = await self.client._call(
                "renew",
                pb.RenewRequest(
                    instance_id=self.instance_id,
                    lease_token=self.lease_token,
                    initialized=self.initialized,
                    draining=self.draining,
                ),
                pb.RenewResponse,
            )
            self.lease_seconds = result.lease_seconds
            self.confirmed_until = started + result.lease_seconds
            self.status = result.instance.status

    async def _heartbeat(self) -> None:
        while True:
            await asyncio.sleep(
                min(5, self.lease_seconds / 4) * random.uniform(0.9, 1.1)
            )
            try:
                await self.renew()
            except RPCError as exc:
                if exc.code == "LEASE_EXPIRED":
                    self.status = "UNAVAILABLE"
                    try:
                        async with self._lock:
                            self.instance_id, self.lease_token = (
                                str(uuid4()),
                                uuid4().hex,
                            )
                            await self.register()
                    except (RPCError, NATSError, asyncio.TimeoutError, OSError):
                        logging.getLogger(__name__).warning(
                            "Discovery re-registration failed", exc_info=True
                        )
                elif exc.code in ("UNAVAILABLE", "REGISTRY_BUSY"):
                    self.status = "UNAVAILABLE"
                else:
                    raise
            except (NATSError, asyncio.TimeoutError, OSError):
                self.status = "UNAVAILABLE"
                logging.getLogger(__name__).warning(
                    "Discovery renewal unavailable", exc_info=True
                )

    async def close(self) -> None:
        self.status = "STOPPED"
        self.confirmed_until = 0
        if self.task:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
        try:
            await self.client._call(
                "unregister",
                pb.UnregisterRequest(
                    instance_id=self.instance_id, lease_token=self.lease_token
                ),
                pb.UnregisterResponse,
            )
        except (RPCError, NATSError, asyncio.TimeoutError, OSError):
            logging.getLogger(__name__).warning(
                "Discovery unregister failed; lease will expire", exc_info=True
            )


def module_descriptor(
    module_type, module_id: str, dependencies: tuple[str, ...]
) -> pb.ModuleDescriptor:
    return pb.ModuleDescriptor(
        module_id=module_id,
        package_version=module_type.package_version,
        contract_major=module_type.contract_major,
        dependencies=[
            pb.Dependency(module_id=d, contract_major=1) for d in dependencies
        ],
        agents=[
            pb.AgentDescriptor(
                name=a.name,
                description=a.description,
                contract_major=a.contract_major,
                capabilities=a.capabilities,
            )
            for a in module_type.agents
        ],
    )
