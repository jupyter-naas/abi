"""Registration and readiness policy over an atomic registry snapshot."""

from __future__ import annotations

import hashlib
import math
import re
import secrets
import time
from typing import TypeVar

Result = TypeVar("Result")
from collections.abc import Callable

from naas_abi_core.services.discovery.discovery_ports import (
    RegistryPort,
    RevisionConflict,
)
from naas_abi_proto.discovery.v1 import discovery_pb2 as pb


class DiscoveryError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(f"{code}: {message}")


def _require(ok: bool, code: str, message: str) -> None:
    if not ok:
        raise DiscoveryError(code, message)


def _name(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.:-]{0,255}", value))


class DiscoveryService:
    def __init__(
        self,
        registry: RegistryPort,
        *,
        lease_seconds: float = 20,
        clock: Callable[[], float] = time.time,
    ):
        if not math.isfinite(lease_seconds) or lease_seconds < 1:
            raise ValueError("lease_seconds must be finite and at least 1")
        self.registry, self.lease_seconds, self.clock = registry, lease_seconds, clock

    async def _read(self) -> tuple[pb.RegistryState, int]:
        data, revision = await self.registry.read()
        state = pb.RegistryState.FromString(data)
        live = [r for r in state.records if r.instance.expires_at > self.clock()]
        return pb.RegistryState(records=live), revision

    def _ready(self, state: pb.RegistryState) -> None:
        ready: set[tuple[str, int]] = set()
        for r in state.records:
            r.instance.status = (
                "DRAINING"
                if r.draining
                else ("DEGRADED" if r.initialized else "STARTING")
            )
        for _ in range(len(state.records) + 1):
            before = len(ready)
            for r in state.records:
                if (
                    r.initialized
                    and not r.draining
                    and all(
                        (d.module_id, d.contract_major) in ready
                        for d in r.instance.descriptor.dependencies
                    )
                ):
                    r.instance.status = "READY"
                    descriptor = r.instance.descriptor
                    ready.add((descriptor.module_id, descriptor.contract_major))
            if len(ready) == before:
                break

    def _validate(self, req: pb.RegisterRequest, state: pb.RegistryState) -> None:
        d = req.descriptor
        _require(
            _name(d.module_id) and _name(req.instance_id),
            "INVALID_ARGUMENT",
            "Invalid module or instance identity",
        )
        _require(
            32 <= len(req.lease_token) <= 256,
            "INVALID_ARGUMENT",
            "Lease token must contain 32 to 256 characters",
        )
        _require(
            0 < d.contract_major and len(d.package_version) <= 128,
            "INVALID_ARGUMENT",
            "Invalid contract or package version",
        )
        _require(
            len(d.dependencies) <= 64 and len(d.agents) <= 128,
            "INVALID_ARGUMENT",
            "Too many dependencies or agents",
        )
        _require(
            len({(x.module_id, x.contract_major) for x in d.dependencies})
            == len(d.dependencies),
            "INVALID_ARGUMENT",
            "Duplicate dependencies",
        )
        _require(
            all(_name(x.module_id) and x.contract_major > 0 for x in d.dependencies),
            "INVALID_ARGUMENT",
            "Invalid dependency",
        )
        _require(
            len({x.name for x in d.agents}) == len(d.agents),
            "INVALID_ARGUMENT",
            "Duplicate agents",
        )
        _require(
            all(
                _name(x.name)
                and x.contract_major > 0
                and len(x.description) <= 4096
                and len(x.capabilities) <= 32
                and all(_name(c) for c in x.capabilities)
                for x in d.agents
            ),
            "INVALID_ARGUMENT",
            "Invalid agent descriptor",
        )
        graph = {}
        for record in state.records:
            other = record.instance.descriptor
            if (other.module_id, other.contract_major) == (
                d.module_id,
                d.contract_major,
            ):
                _require(
                    other.dependencies == d.dependencies and other.agents == d.agents,
                    "DESCRIPTOR_CONFLICT",
                    "Replicas of a contract must declare identical dependencies and agents",
                )
            graph[(other.module_id, other.contract_major)] = [
                (x.module_id, x.contract_major) for x in other.dependencies
            ]
        graph[(d.module_id, d.contract_major)] = [
            (x.module_id, x.contract_major) for x in d.dependencies
        ]
        visiting, done = set(), set()

        def visit(node):
            _require(
                node not in visiting,
                "DEPENDENCY_CYCLE",
                "Required modules form a cycle",
            )
            if node in done:
                return
            visiting.add(node)
            for child in graph.get(node, []):
                visit(child)
            visiting.remove(node)
            done.add(node)

        for node in graph:
            visit(node)

    @staticmethod
    def _authorize(record: pb.RegistryRecord, token: str, owner: str) -> None:
        _require(
            record.owner == owner
            and secrets.compare_digest(
                record.lease_hash, hashlib.sha256(token.encode()).hexdigest()
            ),
            "PERMISSION_DENIED",
            "Registration belongs to another lease or caller",
        )

    async def _mutate(self, operation: Callable[[pb.RegistryState], Result]) -> Result:
        for _ in range(5):
            state, revision = await self._read()
            result = operation(state)
            payload = state.SerializeToString()
            _require(
                len(payload) <= 512 * 1024,
                "REGISTRY_FULL",
                "Registry snapshot exceeds 512 KiB",
            )
            try:
                await self.registry.compare_and_swap(payload, revision)
            except RevisionConflict:
                continue
            return result
        raise DiscoveryError(
            "REGISTRY_BUSY", "Concurrent registry updates; retry control operation"
        )

    async def register(
        self, req: pb.RegisterRequest, owner: str
    ) -> pb.RegisterResponse:
        def apply(state):
            self._validate(req, state)
            record = next(
                (r for r in state.records if r.instance.instance_id == req.instance_id),
                None,
            )
            if record is not None:
                self._authorize(record, req.lease_token, owner)
                _require(
                    record.instance.descriptor == req.descriptor,
                    "DESCRIPTOR_CONFLICT",
                    "Registration identity cannot change",
                )
            else:
                _require(
                    len(state.records) < 256,
                    "REGISTRY_FULL",
                    "Registry supports at most 256 live instances",
                )
                record = state.records.add(
                    owner=owner,
                    lease_hash=hashlib.sha256(req.lease_token.encode()).hexdigest(),
                    instance=pb.Instance(
                        descriptor=req.descriptor,
                        instance_id=req.instance_id,
                        expires_at=self.clock() + self.lease_seconds,
                    ),
                )
            self._ready(state)
            return pb.RegisterResponse(
                instance=record.instance,
                lease_seconds=max(0, record.instance.expires_at - self.clock()),
            )

        return await self._mutate(apply)

    async def renew(self, req: pb.RenewRequest, owner: str) -> pb.RenewResponse:
        def apply(state):
            record = next(
                (r for r in state.records if r.instance.instance_id == req.instance_id),
                None,
            )
            _require(
                record is not None,
                "LEASE_EXPIRED",
                "Register a fresh instance after lease loss",
            )
            self._authorize(record, req.lease_token, owner)
            # Initialization and draining are monotonic within an incarnation.
            record.initialized = record.initialized or req.initialized
            record.draining = record.draining or req.draining
            record.instance.expires_at = self.clock() + self.lease_seconds
            self._ready(state)
            return pb.RenewResponse(
                instance=record.instance,
                lease_seconds=max(0, record.instance.expires_at - self.clock()),
            )

        return await self._mutate(apply)

    async def unregister(
        self, req: pb.UnregisterRequest, owner: str
    ) -> pb.UnregisterResponse:
        def apply(state):
            for i, record in enumerate(state.records):
                if record.instance.instance_id == req.instance_id:
                    self._authorize(record, req.lease_token, owner)
                    del state.records[i]
                    break
            return pb.UnregisterResponse()

        return await self._mutate(apply)

    async def get_module(self, req: pb.GetModuleRequest) -> pb.GetModuleResponse:
        _require(
            _name(req.module_id) and req.contract_major > 0,
            "INVALID_ARGUMENT",
            "Module identity and contract required",
        )
        state, _ = await self._read()
        self._ready(state)
        records = [
            r.instance
            for r in state.records
            if r.instance.descriptor.module_id == req.module_id
        ]
        _require(bool(records), "MODULE_NOT_FOUND", req.module_id)
        matches = [
            r for r in records if r.descriptor.contract_major == req.contract_major
        ]
        _require(bool(matches), "INCOMPATIBLE_MODULE", req.module_id)
        ordered: list[pb.Instance] = sorted(matches, key=lambda r: r.instance_id)
        return pb.GetModuleResponse(instances=ordered)

    async def list_modules(self, req: pb.ListModulesRequest) -> pb.ListModulesResponse:
        _require(1 <= req.limit <= 100, "INVALID_ARGUMENT", "Page size must be 1..100")
        state, _ = await self._read()
        self._ready(state)
        records = sorted(
            (
                r.instance
                for r in state.records
                if r.instance.instance_id > req.after_instance_id
            ),
            key=lambda r: r.instance_id,
        )
        page = records[: req.limit]
        return pb.ListModulesResponse(
            instances=page,
            next_after_instance_id=page[-1].instance_id
            if len(records) > req.limit
            else "",
        )

    async def authorize_agent(
        self, req: pb.AuthorizeAgentRequest, owner: str
    ) -> pb.AuthorizeAgentResponse:
        state, _ = await self._read()
        self._ready(state)
        record = next(
            (r for r in state.records if r.instance.instance_id == req.instance_id),
            None,
        )
        if record is None:
            raise DiscoveryError("LEASE_EXPIRED", "Provider registration expired")
        self._authorize(record, req.lease_token, owner)
        _require(
            any(
                a.name == req.agent_name and "agent.invoke.v1" in a.capabilities
                for a in record.instance.descriptor.agents
            ),
            "AGENT_NOT_FOUND",
            req.agent_name,
        )
        if req.new_invocation:
            _require(
                record.instance.status == "READY",
                "MODULE_UNAVAILABLE",
                "Provider is not ready",
            )
        return pb.AuthorizeAgentResponse()
