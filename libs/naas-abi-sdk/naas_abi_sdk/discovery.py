"""Portable discovery values, logical module proxies and runner registration."""

from __future__ import annotations

import asyncio
import logging
import math
import random
import re
import time
from dataclasses import dataclass
from typing import Any
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
class ModelDescriptor:
    """A chat model served by this module. Inference stays in its process."""

    name: str
    description: str = ""
    kind: str = "chat"


@dataclass(frozen=True)
class ModuleInstance:
    module_id: str
    instance_id: str
    package_version: str
    contract_major: int
    status: str
    expires_at: float
    agents: tuple[AgentDescriptor, ...]
    jobs: tuple[Any, ...] = ()
    # (module_id, contract_major) of each required module.
    dependencies: tuple[tuple[str, int], ...] = ()
    models: tuple[ModelDescriptor, ...] = ()


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
        _jobs(d),
        tuple((x.module_id, x.contract_major) for x in d.dependencies),
        tuple(ModelDescriptor(m.name, m.description, m.kind) for m in d.models),
    )


def _jobs(descriptor: pb.ModuleDescriptor) -> tuple[Any, ...]:
    from naas_abi_sdk.jobs import JobDescriptor

    return tuple(JobDescriptor.from_pb(j) for j in descriptor.jobs)


_ROLLOUT_ID = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.:-]{0,127}")


def validate_rollout_id(value: str) -> str:
    if value and not _ROLLOUT_ID.fullmatch(value):
        raise ValueError("Invalid rollout id")
    return value


@dataclass(frozen=True)
class DiscoveryConfiguration:
    project: str = "default"
    startup_timeout: float = 60
    refresh_seconds: float = 2
    # Shared by every process that must cut over together. Empty is not a rollout.
    rollout_id: str = ""
    # Module ids required before this rollout replaces the previous one.
    # Empty with a rollout id means this module alone.
    rollout_modules: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", self.project):
            raise ValueError("Invalid discovery project")
        if any(
            not math.isfinite(v) or v <= 0
            for v in (self.startup_timeout, self.refresh_seconds)
        ):
            raise ValueError("Discovery timeouts must be finite and positive")
        validate_rollout_id(self.rollout_id)
        if self.rollout_modules and not self.rollout_id:
            raise ValueError("Rollout modules require a rollout id")
        if len(self.rollout_modules) > 64 or len(set(self.rollout_modules)) != len(
            self.rollout_modules
        ):
            raise ValueError("Invalid rollout modules")
        if any(
            not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.:-]{0,255}", module_id)
            for module_id in self.rollout_modules
        ):
            raise ValueError("Invalid rollout modules")


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

    async def evict(self, instance_id: str) -> ModuleInstance:
        """Remove a registration now (platform admin identities only).

        A live instance's next renewal fails with LEASE_EXPIRED and its session
        registers again under the same instance id.
        """
        result = await self._call(
            "evict", pb.EvictRequest(instance_id=instance_id), pb.EvictResponse
        )
        return _instance(result.instance)


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

    async def get_chat_model(self, name: str):
        """A LangChain chat model served by a ready instance of this module."""
        from naas_abi_proto.model_registry.v1 import model_registry_pb2 as model_pb

        from naas_abi_sdk.model_host import ModuleModelClient, model_subject
        from naas_abi_sdk.models import (
            ChatModelProxy,
            RemoteModel,
            UnaryModelConnection,
        )

        eligible = [
            instance
            for instance in await self.ready_instances()
            if any(
                model.name == name and model.kind == "chat" for model in instance.models
            )
        ]
        if not eligible:
            raise RPCError("MODEL_NOT_FOUND", name)
        target = eligible[0]
        ref = model_pb.ModelRef(canonical_id=name, provider=self.module_id, kind="chat")
        proxy = ChatModelProxy(
            connection=UnaryModelConnection(
                ModuleModelClient(
                    self.client.transport,
                    model_subject(self.client.project, target.instance_id, name),
                )
            ),
            ref=ref,
            model_id=name,
            provider=self.module_id,
        )
        return RemoteModel(name, name, self.module_id, proxy, "chat", name, None, {})

    async def get_agent(self, name: str):
        from naas_abi_sdk.agent import AgentProxy

        descriptor = next((a for a in await self.list_agents() if a.name == name), None)
        if descriptor is None:
            raise RPCError("AGENT_NOT_FOUND", name)
        if (
            descriptor.contract_major != 1
            or "agent.invoke.v1" not in descriptor.capabilities
        ):
            raise RPCError(
                "AGENT_NOT_INVOKABLE", "Agent has no supported invocation handler"
            )
        return AgentProxy(self, descriptor)

    async def get_job(self, name: str):
        from naas_abi_sdk.jobs import JobProxy

        descriptor = next(
            (j for j in (await self.ready_instances())[0].jobs if j.name == name), None
        )
        if descriptor is None:
            raise RPCError("JOB_NOT_FOUND", name)
        return JobProxy(
            self.client.transport, self.client.project, self.module_id, descriptor
        )

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
    def __init__(
        self,
        client: DiscoveryClient,
        descriptor: pb.ModuleDescriptor,
        rollout_id: str = "",
        rollout_modules: tuple[str, ...] = (),
    ):
        validate_rollout_id(rollout_id)
        self.client, self.descriptor = client, descriptor
        self.rollout_id = rollout_id
        self.rollout_modules = tuple(rollout_modules)
        self.instance_id, self.lease_token = str(uuid4()), uuid4().hex
        self.initialized, self.draining = False, False
        self.lease_seconds, self.confirmed_until = 20.0, 0.0
        self._lock = asyncio.Lock()
        self.task: asyncio.Task | None = None
        self.status = "STARTING"
        self.on_registered = None
        self._bound = True
        # Set when this process should stop accepting work and finish what it has.
        self.drain_requested = asyncio.Event()

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
                rollout_id=self.rollout_id,
                rollout_modules=self.rollout_modules,
            ),
            pb.RegisterResponse,
        )
        self.lease_seconds = result.lease_seconds
        self.confirmed_until = started + result.lease_seconds
        self.status = result.instance.status
        self._bound = self.on_registered is None
        if self.on_registered is not None:
            await self.on_registered()
            self._bound = True

    async def start(self) -> None:
        await self.register()
        self.task = asyncio.create_task(self._heartbeat())

    async def renew(self) -> None:
        async with self._lock:
            if self.on_registered is not None and not self._bound:
                await self.on_registered()
                self._bound = True
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
            if self.status == "DRAINING":
                self.draining = True
                self.drain_requested.set()

    def _heartbeat_delay(self, failures: int) -> float:
        delay = min(30, min(5, self.lease_seconds / 4) * 2 ** min(failures, 3))
        delay *= random.uniform(0.9, 1.1)
        remaining = self.confirmed_until - time.monotonic()
        # Apply the cap after jitter. Expired leases still back off, without spinning.
        budget = remaining / 2 if remaining > 0 else self.lease_seconds / 2
        return min(delay, max(0.05, budget))

    async def _heartbeat(self) -> None:
        failures = 0
        unexpected = 0
        while True:
            await asyncio.sleep(self._heartbeat_delay(failures))
            try:
                try:
                    await self.renew()
                except RPCError as exc:
                    if exc.code != "LEASE_EXPIRED":
                        raise
                    self.status = "UNAVAILABLE"
                    async with self._lock:
                        # A fresh lease for the same instance id, so the runs
                        # and endpoints this process owns keep their address.
                        self.lease_token = uuid4().hex
                        await self.register()
                failures = unexpected = 0
            except RPCError as exc:
                self.status = "UNAVAILABLE"
                if exc.code not in {
                    "LEASE_EXPIRED",
                    "UNAVAILABLE",
                    "REGISTRY_BUSY",
                    "INTERNAL",
                    "RESOURCE_EXHAUSTED",
                }:
                    logging.getLogger(__name__).error(
                        "Discovery renewal cannot recover from %s", exc.code
                    )
                    raise
                failures += 1
                logging.getLogger(__name__).warning(
                    "Discovery renewal will retry: %s", exc.code
                )
            except (NATSError, asyncio.TimeoutError, OSError):
                self.status = "UNAVAILABLE"
                failures += 1
                logging.getLogger(__name__).warning(
                    "Discovery renewal unavailable; retrying", exc_info=True
                )
            except Exception:
                self.status = "UNAVAILABLE"
                failures += 1
                unexpected += 1
                logging.getLogger(__name__).exception(
                    "Discovery endpoint binding or renewal failed"
                )
                if unexpected >= 3:
                    raise

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
        jobs=[j.to_pb() for j in getattr(module_type, "jobs", ())],
        models=[
            pb.ModelDescriptor(name=m.name, description=m.description, kind=m.kind)
            for m in getattr(module_type, "models", ())
        ],
    )
