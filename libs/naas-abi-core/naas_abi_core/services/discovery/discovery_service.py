"""Registration and readiness policy over an atomic registry snapshot."""

from __future__ import annotations

import contextlib
import hashlib
import math
import re
import secrets
import time
from collections.abc import Callable, Iterable
from typing import TypeVar

Result = TypeVar("Result")

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


def _rollout_id(value: str) -> bool:
    return value == "" or bool(
        re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.:-]{0,127}", value)
    )


def _cohort(req: pb.RegisterRequest) -> tuple[str, ...]:
    """Module ids that must be up before this rollout can replace the previous one."""
    if req.rollout_modules:
        return tuple(sorted(set(req.rollout_modules)))
    if req.rollout_id:
        return (req.descriptor.module_id,)
    return ()


JOB_TRIGGER_KINDS = ("cron", "every", "event")

# Service identities allowed to evict registrations: the Nexus API (System app)
# and the engine. Stage 1 tokens name first-party processes (see nats_auth).
DEFAULT_ADMIN_IDENTITIES = ("api", "engine")


def _valid_job(job: pb.JobDescriptor) -> bool:
    return (
        _name(job.name)
        and job.contract_major > 0
        and len(job.description) <= 4096
        and 0 < job.max_concurrency <= 64
        and 0 < job.max_attempts <= 100
        and job.timeout_seconds >= 0
        and math.isfinite(job.timeout_seconds)
        and len(job.triggers) <= 16
        and all(
            t.kind in JOB_TRIGGER_KINDS
            and 0 < len(t.spec) <= 256
            and len(t.time_zone) <= 64
            for t in job.triggers
        )
    )


class DiscoveryService:
    def __init__(
        self,
        registry: RegistryPort,
        *,
        lease_seconds: float = 20,
        clock: Callable[[], float] = time.time,
        admin_identities: Iterable[str] = DEFAULT_ADMIN_IDENTITIES,
        snapshot_seconds: float = 1.0,
    ):
        if not math.isfinite(lease_seconds) or lease_seconds < 1:
            raise ValueError("lease_seconds must be finite and at least 1")
        if not math.isfinite(snapshot_seconds) or snapshot_seconds < 0:
            raise ValueError("snapshot_seconds must be finite and not negative")
        admins = frozenset(admin_identities)
        if not all(admins) or not all(isinstance(a, str) for a in admins):
            raise ValueError("admin identities must be non-empty names")
        self.registry, self.lease_seconds, self.clock = registry, lease_seconds, clock
        self.admin_identities = admins
        # The registry as this replica last read or wrote it, and when. Agent
        # polls are allowed from it for snapshot_seconds (see authorize_agent).
        self.snapshot_seconds = snapshot_seconds
        self._snapshot: tuple[float, pb.RegistryState] | None = None

    async def _read(self) -> tuple[pb.RegistryState, int]:
        data, revision = await self.registry.read()
        state = pb.RegistryState.FromString(data)
        self._snapshot = (self.clock(), state)  # never mutated: callers get copies
        live = [r for r in state.records if r.instance.expires_at > self.clock()]
        return pb.RegistryState(records=live), revision

    def _apply_rollouts(self, state: pb.RegistryState) -> dict[str, str]:
        """Choose the serving rollout per module id and drain the one it replaces.

        A rollout is every live instance that shares a rollout id. It becomes
        eligible once each of its module ids has an initialized instance and
        each dependency is either inside that rollout or already initialized
        outside it. The latest eligible rollout for a module id is the one that
        serves. Older complete rollouts, and instances with no rollout id, are
        marked draining. An incomplete rollout stays up so a partial deploy
        cannot take traffic away from the current one.
        """
        groups: dict[str, list[pb.RegistryRecord]] = {}
        for record in state.records:
            if record.rollout_id:
                groups.setdefault(record.rollout_id, []).append(record)
        starts = {
            rollout: min(record.registered_at for record in members)
            for rollout, members in groups.items()
        }
        complete = {
            rollout: self._rollout_complete(members, state)
            for rollout, members in groups.items()
        }
        serving: dict[str, str] = {}
        for rollout, members in groups.items():
            if not complete[rollout]:
                continue
            for record in members:
                module_id = record.instance.descriptor.module_id
                current = serving.get(module_id)
                if current is None or (starts[rollout], rollout) > (
                    starts[current],
                    current,
                ):
                    serving[module_id] = rollout
        for record in state.records:
            module_id = record.instance.descriptor.module_id
            winner = serving.get(module_id)
            if winner is None or record.rollout_id == winner:
                continue
            if record.rollout_id and not complete.get(record.rollout_id, False):
                continue
            record.draining = True
        return serving

    def _rollout_complete(
        self, members: list[pb.RegistryRecord], state: pb.RegistryState
    ) -> bool:
        declared = set(members[0].rollout_modules)
        if not declared or any(
            set(record.rollout_modules) != declared for record in members
        ):
            return False
        live = [
            record for record in members if record.initialized and not record.draining
        ]
        module_ids = declared
        if not module_ids <= {record.instance.descriptor.module_id for record in live}:
            return False
        cohort = {
            (
                record.instance.descriptor.module_id,
                record.instance.descriptor.contract_major,
            )
            for record in live
        }
        for record in live:
            for dep in record.instance.descriptor.dependencies:
                pair = (dep.module_id, dep.contract_major)
                if dep.module_id in module_ids:
                    if pair not in cohort:
                        return False
                    continue
                if not any(
                    other.initialized
                    and not other.draining
                    and other.instance.descriptor.module_id == dep.module_id
                    and other.instance.descriptor.contract_major == dep.contract_major
                    for other in state.records
                ):
                    return False
        return True

    def _staged(
        self,
        record: pb.RegistryRecord,
        state: pb.RegistryState,
        serving: dict[str, str],
    ) -> bool:
        """A new generation waits while the current one of that module is still up."""
        if record.draining or not record.initialized or not record.rollout_id:
            return False
        module_id = record.instance.descriptor.module_id
        if record.rollout_id == serving.get(module_id):
            return False
        return any(
            other is not record
            and not other.draining
            and other.instance.descriptor.module_id == module_id
            and other.rollout_id != record.rollout_id
            for other in state.records
        )

    def _ready(self, state: pb.RegistryState) -> None:
        serving = self._apply_rollouts(state)
        ready: set[tuple[str, int]] = set()
        for record in state.records:
            if record.draining:
                record.instance.status = "DRAINING"
            elif not record.initialized:
                record.instance.status = "STARTING"
            elif self._staged(record, state, serving):
                record.instance.status = "STAGED"
            else:
                record.instance.status = "DEGRADED"
        for _ in range(len(state.records) + 1):
            before = len(ready)
            for record in state.records:
                if record.instance.status != "DEGRADED":
                    continue
                if all(
                    (dep.module_id, dep.contract_major) in ready
                    for dep in record.instance.descriptor.dependencies
                ):
                    record.instance.status = "READY"
                    descriptor = record.instance.descriptor
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
        _require(_rollout_id(req.rollout_id), "INVALID_ARGUMENT", "Invalid rollout id")
        cohort = tuple(req.rollout_modules) or (
            (d.module_id,) if req.rollout_id else ()
        )
        _require(
            (bool(req.rollout_id) or not req.rollout_modules)
            and len(cohort) <= 64
            and len(set(cohort)) == len(cohort)
            and all(_name(module_id) for module_id in cohort)
            and (not cohort or d.module_id in cohort),
            "INVALID_ARGUMENT",
            "Invalid rollout modules",
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
        _require(
            len(d.jobs) <= 128 and len({x.name for x in d.jobs}) == len(d.jobs),
            "INVALID_ARGUMENT",
            "Too many or duplicate jobs",
        )
        _require(
            all(_valid_job(x) for x in d.jobs),
            "INVALID_ARGUMENT",
            "Invalid job descriptor",
        )
        _require(
            len(d.models) <= 128 and len({x.name for x in d.models}) == len(d.models),
            "INVALID_ARGUMENT",
            "Too many or duplicate models",
        )
        _require(
            all(
                _name(x.name) and x.kind == "chat" and len(x.description) <= 4096
                for x in d.models
            ),
            "INVALID_ARGUMENT",
            "Invalid model descriptor",
        )
        graph = {}
        for record in state.records:
            other = record.instance.descriptor
            if req.rollout_id and record.rollout_id == req.rollout_id:
                _require(
                    tuple(sorted(record.rollout_modules)) == _cohort(req),
                    "DESCRIPTOR_CONFLICT",
                    "Rollout members do not match",
                )
            if (other.module_id, other.contract_major) == (
                d.module_id,
                d.contract_major,
            ):
                _require(
                    other.dependencies == d.dependencies
                    and other.agents == d.agents
                    and other.jobs == d.jobs
                    and other.models == d.models,
                    "DESCRIPTOR_CONFLICT",
                    "Replicas of a contract must declare identical dependencies, agents, jobs and models",
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
            self._snapshot = (self.clock(), state)
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
                    record.instance.descriptor == req.descriptor
                    and record.rollout_id == req.rollout_id
                    and tuple(sorted(record.rollout_modules)) == _cohort(req),
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
                    rollout_id=req.rollout_id,
                    registered_at=self.clock(),
                    rollout_modules=_cohort(req),
                    instance=pb.Instance(
                        descriptor=req.descriptor,
                        instance_id=req.instance_id,
                        expires_at=self.clock() + self.lease_seconds,
                        rollout_id=req.rollout_id,
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

    async def evict(self, req: pb.EvictRequest, owner: str) -> pb.EvictResponse:
        """Remove a registration whatever its lease. Admin identities only.

        The evicted owner's next renewal fails with LEASE_EXPIRED; the SDK then
        registers a fresh instance, so evicting a live process only restarts its
        membership. It is meant for crashed or stuck registrations.
        """
        _require(
            owner in self.admin_identities,
            "PERMISSION_DENIED",
            "Only platform administrators can evict registrations",
        )
        _require(
            _name(req.instance_id), "INVALID_ARGUMENT", "Invalid instance identity"
        )

        def apply(state):
            self._ready(state)
            for i, record in enumerate(state.records):
                if record.instance.instance_id == req.instance_id:
                    evicted = pb.Instance()
                    evicted.CopyFrom(record.instance)
                    del state.records[i]
                    self._ready(state)
                    return pb.EvictResponse(instance=evicted)
            raise DiscoveryError("INSTANCE_NOT_FOUND", req.instance_id)

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
        if not req.new_invocation:
            # Status, event and cancel polls are allowed from a recent snapshot
            # instead of a full registry read. A submit (which needs READY), or
            # anything the snapshot would refuse, reads the registry.
            recent = self._recent_record(req.instance_id)
            if recent is not None:
                with contextlib.suppress(DiscoveryError):
                    return self._authorize_agent(recent, req, owner)
        state, _ = await self._read()
        self._ready(state)
        record = next(
            (r for r in state.records if r.instance.instance_id == req.instance_id),
            None,
        )
        return self._authorize_agent(record, req, owner)

    def _recent_record(self, instance_id: str) -> pb.RegistryRecord | None:
        """The instance's live record in a snapshot under snapshot_seconds old."""
        if self._snapshot is None:
            return None
        taken, state = self._snapshot
        now = self.clock()
        if not 0 <= now - taken < self.snapshot_seconds:
            return None
        return next(
            (
                r
                for r in state.records
                if r.instance.instance_id == instance_id and r.instance.expires_at > now
            ),
            None,
        )

    def _authorize_agent(
        self,
        record: pb.RegistryRecord | None,
        req: pb.AuthorizeAgentRequest,
        owner: str,
    ) -> pb.AuthorizeAgentResponse:
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

    async def authorize_model(
        self, req: pb.AuthorizeModelRequest, owner: str
    ) -> pb.AuthorizeModelResponse:
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
                m.name == req.model_name and m.kind == "chat"
                for m in record.instance.descriptor.models
            ),
            "MODEL_NOT_FOUND",
            req.model_name,
        )
        _require(
            record.instance.status == "READY",
            "MODULE_UNAVAILABLE",
            "Provider is not ready",
        )
        return pb.AuthorizeModelResponse()
