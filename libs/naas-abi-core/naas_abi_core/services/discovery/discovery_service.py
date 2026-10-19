"""Registration and readiness policy over an atomic registry snapshot."""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import math
import re
import secrets
import time
from collections.abc import Callable, Iterable
from typing import Any, TypeVar

Result = TypeVar("Result")

from naas_abi_core.engine.call_context import (
    CallContext,
    current_call_context,
    use_call_context,
)
from naas_abi_core.services.discovery.caller import run_owner
from naas_abi_core.services.discovery.discovery_ports import (
    RegistryPort,
    RevisionConflict,
)
from naas_abi_core.services.discovery.iam_catalog import CATALOG
from naas_abi_core.services.iam.guard import ServiceGuard
from naas_abi_core.services.iam.IAMPorts import IIAMService
from naas_abi_core.services.iam.modules import subject_token
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


def _depends_on_itself(
    graph: dict[tuple[str, int], list[tuple[str, int]]], root: tuple[str, int]
) -> bool:
    """Whether ``root`` reaches itself through the dependency ``graph``."""
    seen: set[tuple[str, int]] = set()
    pending = list(graph.get(root, ()))
    while pending:
        node = pending.pop()
        if node == root:
            return True
        if node not in seen:
            seen.add(node)
            pending.extend(graph.get(node, ()))
    return False


JOB_TRIGGER_KINDS = ("cron", "every", "event")

# Who may evict registrations on a discovery with no IAM (tests, a bare
# registry): the Nexus API and the engine, by their service-account names.
# With IAM it is discovery:Evict.
DEFAULT_ADMIN_IDENTITIES = ("api", "engine")

# The service-account name form of a module (RFC §2): a module account registers
# only under its own name.
MODULE_ACCOUNT_PREFIX = "module/"
AGENT_OPERATIONS = ("submit", "status", "event", "cancel")
JOB_OPERATIONS = ("trigger", "cancel")


def _error(code: str, message: str) -> Callable[[], DiscoveryError]:
    return lambda: DiscoveryError(code, message)


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


# Apps a module serves over NATS (docs/adr/20261012_remote-module-apps.md): few
# and small, so they stay a minor part of the bounded registry snapshot.
MAX_APPS = 16
MAX_APP_BYTES = 4096


def _app_name(value: str) -> bool:
    """A URL segment under /app-html/remote/<module_id>/."""
    return bool(re.fullmatch(r"[A-Za-z0-9_-]{1,64}", value))


def _app_entry(value: str) -> bool:
    """A relative page below the app's root: no leading slash, no ``..``."""
    return value == "" or (
        len(value) <= 256
        and not value.startswith("/")
        and ".." not in value.split("/")
        and "\\" not in value
    )


def _valid_app(app: pb.AppDescriptor) -> bool:
    return (
        _app_name(app.name)
        and app.contract_major > 0
        and len(app.title) <= 256
        and len(app.description) <= 4096
        and len(app.category) <= 64
        and len(app.icon_emoji) <= 16
        and _app_entry(app.entry)
        and app.ByteSize() <= MAX_APP_BYTES
    )


class DiscoveryService:
    """Registrations, readiness, and who may use what a module serves.

    Wired with IAM (``iam``), every operation is authorized in the caller's
    ``CallContext`` with the ``discovery`` catalog: the provider's for
    registration, the forwarded caller's for ``authorize_*``. Without IAM (unit
    tests of the registry alone) nothing is authorized, as for any unwired
    domain service.
    """

    def __init__(
        self,
        registry: RegistryPort,
        *,
        lease_seconds: float = 20,
        clock: Callable[[], float] = time.time,
        snapshot_seconds: float = 1.0,
        project: str = "default",
        iam: IIAMService | None = None,
        admin_identities: Iterable[str] = DEFAULT_ADMIN_IDENTITIES,
    ):
        """Evicting is ``discovery:Evict``, a policy. ``admin_identities`` only
        serves a discovery with no IAM, which allows nothing else to evict."""
        if not math.isfinite(lease_seconds) or lease_seconds < 1:
            raise ValueError("lease_seconds must be finite and at least 1")
        if not math.isfinite(snapshot_seconds) or snapshot_seconds < 0:
            raise ValueError("snapshot_seconds must be finite and not negative")
        self.admin_identities = frozenset(admin_identities)
        self.registry, self.lease_seconds, self.clock = registry, lease_seconds, clock
        self.project = project
        self.iam = iam
        self.guard = ServiceGuard(CATALOG, lambda: self.iam)
        # The registry as this replica last read or wrote it, and when. Agent
        # polls are allowed from it for snapshot_seconds (see authorize_agent).
        self.snapshot_seconds = snapshot_seconds
        self._snapshot: tuple[float, pb.RegistryState] | None = None
        # This replica's writes, one at a time, each taking every mutation
        # waiting (group commit, see _mutate): its endpoint answers calls side by
        # side, and concurrent writes would exhaust each other's CAS retries.
        self._mutations = asyncio.Lock()
        # The module of each live instance, as last read: an instance's module
        # never changes, so a heartbeat checks it without reading the registry.
        self._modules: dict[str, str] = {}
        self._pending: list[tuple[Callable[[pb.RegistryState], Any], Any]] = []

    # -- authorization ------------------------------------------------------------

    def _parts(self, module_id: str, *rest: str) -> list[str]:
        return [self.project, module_id, *rest]

    async def _require(
        self,
        action: str,
        type: str,
        parts: list[str],
        not_found: Callable[[], BaseException],
        caller: CallContext | None = None,
    ) -> None:
        """IAM's decision for the current caller, or ``caller``; off the loop."""
        if not self.guard.enforcing:
            return

        def check() -> None:
            if caller is None:
                self.guard.require(action, type, parts, not_found=not_found)
                return
            with use_call_context(caller):
                self.guard.require(action, type, parts, not_found=not_found)

        await asyncio.to_thread(check)

    async def _filter_instances(
        self, instances: list[pb.Instance]
    ) -> list[pb.Instance]:
        """The instances of the modules the caller may list, each showing only
        the agents, apps and jobs it may list (RFC §6.4)."""
        if not self.guard.enforcing or not instances:
            return instances

        def visible() -> list[pb.Instance]:
            kept = self.guard.filter(
                "ListModules",
                "module",
                instances,
                lambda i: self._parts(i.descriptor.module_id),
            )
            shown = []
            for instance in kept:
                copy = pb.Instance()
                copy.CopyFrom(instance)
                descriptor, module_id = copy.descriptor, copy.descriptor.module_id
                for field, action, type in (
                    ("agents", "ListAgents", "agent"),
                    ("apps", "ListApps", "app"),
                    ("jobs", "ListJobs", "job"),
                ):
                    items = list(getattr(descriptor, field))

                    def parts(item: Any, module_id: str = module_id) -> list[str]:
                        return self._parts(module_id, item.name)

                    allowed = self.guard.filter(action, type, items, parts)
                    if len(allowed) != len(items):
                        del getattr(descriptor, field)[:]
                        getattr(descriptor, field).extend(allowed)
                shown.append(copy)
            return shown

        return await asyncio.to_thread(visible)

    def _bind_module(
        self, req: pb.RegisterRequest, owner: str, state: pb.RegistryState
    ) -> None:
        """A module id is held by one principal at a time (RFC §6.4, Register).

        A module account (``module/<project>/<module_id>``, recorded by IAM)
        registers only its own module. Any other principal may name a module
        freely, so a module id is bound to the principal of its live
        instances: nobody else can join them, and so nobody can take requests
        meant for a running module.
        """
        module_id = req.descriptor.module_id
        if owner.startswith(MODULE_ACCOUNT_PREFIX):
            _require(
                owner == f"{MODULE_ACCOUNT_PREFIX}{self.project}/{module_id}",
                "PERMISSION_DENIED",
                "A module registers only under its own service account",
            )
        _require(
            all(
                record.owner == owner
                for record in state.records
                if record.instance.descriptor.module_id == module_id
            ),
            "PERMISSION_DENIED",
            f"Module {module_id} is registered by another principal",
        )

    async def _read(self) -> tuple[pb.RegistryState, int]:
        data, revision = await self.registry.read()
        state = pb.RegistryState.FromString(data)
        self._snapshot = (self.clock(), state)  # never mutated: callers get copies
        live = [r for r in state.records if r.instance.expires_at > self.clock()]
        self._remember_modules(live)
        return pb.RegistryState(records=live), revision

    def _remember_modules(self, records: Iterable[pb.RegistryRecord]) -> None:
        self._modules = {
            r.instance.instance_id: r.instance.descriptor.module_id for r in records
        }

    def _apply_rollouts(self, state: pb.RegistryState) -> dict[str, str]:
        """Choose the serving generation per module id and drain the ones it replaces.

        A rollout is every live instance that shares a rollout id. It becomes
        eligible once each of its module ids has an initialized instance and
        each dependency is either inside that rollout or already initialized
        outside it. The latest eligible rollout for a module id is the one that
        serves. Older rollouts, complete or not, and instances with no rollout
        id, are marked draining. A newer incomplete rollout stays up so a
        partial deploy cannot take traffic away from the current one.

        A module id with no eligible rollout keeps the generation that served
        it at the last registry write (statuses are stored in the snapshot),
        so a serving rollout that became incomplete, for example because every
        instance of another of its modules expired, keeps serving. Failing
        that, the oldest generation with an initialized instance serves.
        Instances with no rollout id always serve and count as the oldest.

        Returns the serving rollout id per module id ("" for no rollout id).
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
            rollout = record.rollout_id
            if (
                rollout
                and not complete[rollout]
                and (starts[rollout], rollout) > (starts[winner], winner)
            ):
                continue
            record.draining = True
        candidates: dict[str, dict[str, bool]] = {}
        for record in state.records:
            module_id = record.instance.descriptor.module_id
            if module_id in serving or record.draining or not record.initialized:
                continue
            served = not record.rollout_id or record.instance.status in (
                "READY",
                "DEGRADED",
            )
            generations = candidates.setdefault(module_id, {})
            generations[record.rollout_id] = (
                generations.get(record.rollout_id, False) or served
            )
        for module_id, generations in candidates.items():
            serving[module_id] = min(
                (not served, starts.get(rollout, -math.inf), rollout)
                for rollout, served in generations.items()
            )[2]
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

    @staticmethod
    def _staged(record: pb.RegistryRecord, serving: dict[str, str]) -> bool:
        """A rollout's instance waits while another generation serves its module."""
        if record.draining or not record.initialized or not record.rollout_id:
            return False
        module_id = record.instance.descriptor.module_id
        return serving.get(module_id, record.rollout_id) != record.rollout_id

    def _ready(self, state: pb.RegistryState) -> None:
        serving = self._apply_rollouts(state)
        ready: set[tuple[str, int]] = set()
        for record in state.records:
            if record.draining:
                record.instance.status = "DRAINING"
            elif not record.initialized:
                record.instance.status = "STARTING"
            elif self._staged(record, serving):
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
        _require(
            len(d.apps) <= MAX_APPS and len({x.name for x in d.apps}) == len(d.apps),
            "INVALID_ARGUMENT",
            "Too many or duplicate apps",
        )
        _require(
            all(_valid_app(x) for x in d.apps),
            "INVALID_ARGUMENT",
            "Invalid app descriptor",
        )
        for record in state.records:
            other = record.instance.descriptor
            if req.rollout_id and record.rollout_id == req.rollout_id:
                _require(
                    tuple(sorted(record.rollout_modules)) == _cohort(req),
                    "DESCRIPTOR_CONFLICT",
                    "Rollout members do not match",
                )
            # Replicas of one generation (a rollout id, or none) must match. A
            # rollout may change what the generation it replaces declares: it
            # stays STAGED, out of READY lookups, until its cohort cuts over.
            if (other.module_id, other.contract_major) == (
                d.module_id,
                d.contract_major,
            ) and record.rollout_id == req.rollout_id:
                _require(
                    other.dependencies == d.dependencies
                    and other.agents == d.agents
                    and other.jobs == d.jobs
                    and other.models == d.models
                    and other.apps == d.apps,
                    "DESCRIPTOR_CONFLICT",
                    "Replicas of a contract in one rollout must declare identical dependencies, agents, jobs, models and apps",
                )
        self._refuse_cycles(req, state)

    def _refuse_cycles(self, req: pb.RegisterRequest, state: pb.RegistryState) -> None:
        """Refuse a registration whose module would depend on itself.

        Generations replace each other, so their edges are not merged: a
        rollout may reverse a dependency between the modules it replaces. The
        registering generation (its rollout id, or none) is checked with its
        own edges for the module ids it replaces, and the serving generation's
        for the others. Each other live generation is then checked in turn in
        place of the serving one for its module ids, as it could serve beside
        this one. Only a cycle through the registering module refuses it.
        Draining instances are ignored.
        """
        d = req.descriptor
        root = (d.module_id, d.contract_major)
        probe = pb.RegistryState()
        probe.CopyFrom(state)
        serving = self._apply_rollouts(probe)
        edges: dict[str, dict[tuple[str, int], list[tuple[str, int]]]] = {}
        cohorts: dict[str, set[str]] = {}
        for record in probe.records:
            if record.draining:
                continue
            other = record.instance.descriptor
            edges.setdefault(record.rollout_id, {})[
                (other.module_id, other.contract_major)
            ] = [(x.module_id, x.contract_major) for x in other.dependencies]
            cohorts[record.rollout_id] = set(record.rollout_modules)
        own = edges.pop(req.rollout_id, {})
        own[root] = [(x.module_id, x.contract_major) for x in d.dependencies]
        replaced = set(_cohort(req))
        current = {
            node: deps
            for rollout, nodes in edges.items()
            for node, deps in nodes.items()
            if serving.get(node[0]) == rollout and node[0] not in replaced
        }
        views = [current]
        for rollout, nodes in edges.items():
            view = {
                n: deps for n, deps in current.items() if n[0] not in cohorts[rollout]
            }
            view.update((n, deps) for n, deps in nodes.items() if n[0] not in replaced)
            views.append(view)
        for view in views:
            _require(
                not _depends_on_itself({**view, **own}, root),
                "DEPENDENCY_CYCLE",
                "Required modules form a cycle",
            )

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
        """Apply ``operation`` to the registry: group commit.

        One write at a time per replica, but a write takes every mutation that
        arrived while the previous one was in flight, applied in order in one
        compare-and-swap. The result is the one of running them one by one.
        """
        settled: asyncio.Future[Result] = asyncio.get_running_loop().create_future()
        self._pending.append((operation, settled))
        try:
            async with self._mutations:
                if not settled.done():  # not written with the previous batch
                    batch, self._pending = self._pending, []
                    await self._write(batch)
        except asyncio.CancelledError:
            # Not taken by a writer yet: drop it. Taken: it is written anyway.
            with contextlib.suppress(ValueError):
                self._pending.remove((operation, settled))
            if settled.done() and not settled.cancelled():
                settled.exception()  # read: nobody waits for it any more
            raise
        return settled.result()

    async def _write(self, batch: list[tuple[Callable[[pb.RegistryState], Any], Any]]):
        """Write ``batch`` in one compare-and-swap and settle each mutation.

        Each one is applied to its own copy of the registry: a mutation that
        fails is left out without changing what the others see.
        """
        try:
            for _ in range(5):
                state, revision = await self._read()
                outcomes: list[tuple[Any, BaseException | None, Any]] = []
                for operation, settled in batch:
                    candidate = pb.RegistryState()
                    candidate.CopyFrom(state)
                    try:
                        result = operation(candidate)
                        _require(
                            candidate.ByteSize() <= 512 * 1024,
                            "REGISTRY_FULL",
                            "Registry snapshot exceeds 512 KiB",
                        )
                    except Exception as exc:  # noqa: BLE001 - this caller's error only
                        outcomes.append((settled, exc, None))
                        continue
                    state = candidate
                    outcomes.append((settled, None, result))
                if any(error is None for _, error, _ in outcomes):
                    try:
                        await self.registry.compare_and_swap(
                            state.SerializeToString(), revision
                        )
                    except RevisionConflict:
                        continue  # another replica wrote: apply the batch again
                    self._snapshot = (self.clock(), state)
                    self._remember_modules(state.records)
                for settled, error, result in outcomes:
                    if settled.done():  # its caller was cancelled
                        continue
                    if error is None:
                        settled.set_result(result)
                    else:
                        settled.set_exception(error)
                return
            for _, settled in batch:
                if not settled.done():
                    settled.set_exception(
                        DiscoveryError(
                            "REGISTRY_BUSY",
                            "Concurrent registry updates; retry control operation",
                        )
                    )
        except BaseException as exc:
            # The registry failed (or this writer was cancelled): no caller waits forever.
            failure = (
                exc
                if isinstance(exc, Exception)
                else DiscoveryError("UNAVAILABLE", "Registry write interrupted")
            )
            for _, settled in batch:
                if not settled.done():
                    settled.set_exception(failure)
            if not isinstance(exc, Exception):
                raise

    async def register(
        self, req: pb.RegisterRequest, owner: str
    ) -> pb.RegisterResponse:
        if _name(req.descriptor.module_id):
            await self._require(
                "Register",
                "module",
                self._parts(req.descriptor.module_id),
                _error("PERMISSION_DENIED", "Registering this module is not allowed"),
            )

        def apply(state):
            self._validate(req, state)
            self._bind_module(req, owner, state)
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
                        # From the verified caller: its hosting subjects carry it.
                        service_account=subject_token(owner),
                    ),
                )
            self._ready(state)
            return pb.RegisterResponse(
                instance=record.instance,
                lease_seconds=max(0, record.instance.expires_at - self.clock()),
            )

        return await self._mutate(apply)

    async def _require_on_instance(
        self, action: str, instance_id: str, not_found: Callable[[], BaseException]
    ) -> None:
        """``action`` on the module of a live instance; nothing when it is gone
        (the operation then fails as it always did)."""
        if not self.guard.enforcing:
            return
        module_id = self._modules.get(instance_id)
        if module_id is None:
            await self._read()
            module_id = self._modules.get(instance_id)
        if module_id is not None:
            await self._require(action, "module", self._parts(module_id), not_found)

    async def renew(self, req: pb.RenewRequest, owner: str) -> pb.RenewResponse:
        await self._require_on_instance(
            "Renew",
            req.instance_id,
            _error("LEASE_EXPIRED", "Register a fresh instance after lease loss"),
        )

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
        await self._require_on_instance(
            "Unregister", req.instance_id, _error("INSTANCE_NOT_FOUND", req.instance_id)
        )

        def apply(state):
            for i, record in enumerate(state.records):
                if record.instance.instance_id == req.instance_id:
                    self._authorize(record, req.lease_token, owner)
                    del state.records[i]
                    break
            return pb.UnregisterResponse()

        return await self._mutate(apply)

    async def evict(self, req: pb.EvictRequest, owner: str) -> pb.EvictResponse:
        """Remove a registration whatever its lease: ``discovery:Evict`` on its module.

        The evicted owner's next renewal fails with LEASE_EXPIRED; the SDK then
        registers a fresh instance, so evicting a live process only restarts its
        membership. It is meant for crashed or stuck registrations.
        """
        caller = current_call_context().principal
        _require(
            _name(req.instance_id), "INVALID_ARGUMENT", "Invalid instance identity"
        )
        # Who may evict is IAM's decision, in the caller's context. With no
        # IAM to ask, only the platform's own identities may: never fail open.
        _require(
            self.guard.enforcing
            or owner in self.admin_identities
            or (
                caller.kind == "service_account"
                and caller.name in self.admin_identities
            ),
            "PERMISSION_DENIED",
            "Only platform administrators can evict registrations",
        )
        await self._require_on_instance(
            "Evict", req.instance_id, _error("INSTANCE_NOT_FOUND", req.instance_id)
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
        await self._require(
            "GetModule",
            "module",
            self._parts(req.module_id),
            _error("MODULE_NOT_FOUND", req.module_id),
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
        return pb.GetModuleResponse(instances=await self._filter_instances(ordered))

    async def list_modules(self, req: pb.ListModulesRequest) -> pb.ListModulesResponse:
        _require(1 <= req.limit <= 100, "INVALID_ARGUMENT", "Page size must be 1..100")
        state, _ = await self._read()
        self._ready(state)
        records = await self._filter_instances(
            sorted(
                (
                    r.instance
                    for r in state.records
                    if r.instance.instance_id > req.after_instance_id
                ),
                key=lambda r: r.instance_id,
            )
        )
        page = records[: req.limit]
        return pb.ListModulesResponse(
            instances=page,
            next_after_instance_id=page[-1].instance_id
            if len(records) > req.limit
            else "",
        )

    async def authorize_agent(
        self,
        req: pb.AuthorizeAgentRequest,
        owner: str,
        caller: CallContext | None = None,
    ) -> pb.AuthorizeAgentResponse:
        """The provider's lease, then the caller's policy (RFC §6.4).

        ``caller``: the provider's caller, verified from the token and the
        on-behalf-of user it forwarded. A submit needs ``InvokeAgent`` on the
        agent; status and event polls need ``GetAgentRun``, a cancel
        ``CancelAgentRun``, on ``run/<owner>/<project>/<invocation>``. The
        response names the owner of the runs this caller starts.
        """
        operation = req.operation or ("submit" if req.new_invocation else "")
        _require(
            operation in ("", *AGENT_OPERATIONS)
            and (operation != "submit" or req.new_invocation)
            and (operation in ("", "submit") or not req.new_invocation),
            "INVALID_ARGUMENT",
            "Unknown agent operation",
        )
        record: pb.RegistryRecord | None = None
        if not req.new_invocation:
            # Status, event and cancel polls are allowed from a recent snapshot
            # instead of a full registry read. A submit (which needs READY), or
            # anything the snapshot would refuse, reads the registry.
            recent = self._recent_record(req.instance_id)
            if recent is not None:
                with contextlib.suppress(DiscoveryError):
                    self._authorize_agent(recent, req, owner)
                    record = recent
        if record is None:
            state, _ = await self._read()
            self._ready(state)
            record = next(
                (r for r in state.records if r.instance.instance_id == req.instance_id),
                None,
            )
            self._authorize_agent(record, req, owner)
        assert record is not None
        response = pb.AuthorizeAgentResponse()
        if caller is None:
            return response
        module_id = record.instance.descriptor.module_id
        if operation in ("submit", ""):
            # An older provider's poll: it checks the run's owner itself.
            await self._require(
                "InvokeAgent",
                "agent",
                self._parts(module_id, req.agent_name),
                _error("AGENT_NOT_FOUND", req.agent_name),
                caller,
            )
        else:
            _require(
                bool(req.run_owner) and _name(req.invocation_id),
                "INVALID_ARGUMENT",
                "A run poll names the run and its owner",
            )
            await self._require(
                "CancelAgentRun" if operation == "cancel" else "GetAgentRun",
                "run",
                [req.run_owner, self.project, req.invocation_id],
                _error("INVOCATION_NOT_FOUND", "Invocation not found"),
                caller,
            )
            response.run_authorized = self.guard.enforcing
        response.caller_identity = run_owner(caller)
        return response

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
    ) -> None:
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

    async def _live_record(self, instance_id: str) -> pb.RegistryRecord:
        state, _ = await self._read()
        self._ready(state)
        record = next(
            (r for r in state.records if r.instance.instance_id == instance_id),
            None,
        )
        if record is None:
            raise DiscoveryError("LEASE_EXPIRED", "Provider registration expired")
        return record

    async def authorize_model(
        self,
        req: pb.AuthorizeModelRequest,
        owner: str,
        caller: CallContext | None = None,
    ) -> pb.AuthorizeModelResponse:
        """The provider's lease, then ``ChatModel`` for the caller."""
        record = await self._live_record(req.instance_id)
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
        response = pb.AuthorizeModelResponse()
        if caller is not None:
            await self._require(
                "ChatModel",
                "model",
                self._parts(record.instance.descriptor.module_id, req.model_name),
                _error("MODEL_NOT_FOUND", req.model_name),
                caller,
            )
            response.caller_identity = run_owner(caller)
        return response

    async def authorize_app(
        self,
        req: pb.AuthorizeAppRequest,
        owner: str,
        caller: CallContext | None = None,
    ) -> pb.AuthorizeAppResponse:
        """The provider's lease, then ``OpenApp`` for the caller. Every app
        request is authorized (the SDK caches the answer briefly), so a recent
        snapshot serves it when it already shows the app READY."""
        record: pb.RegistryRecord | None = None
        recent = self._recent_record(req.instance_id)
        if recent is not None:
            with contextlib.suppress(DiscoveryError):
                self._authorize_app(recent, req, owner)
                record = recent
        if record is None:
            state, _ = await self._read()
            self._ready(state)
            record = next(
                (r for r in state.records if r.instance.instance_id == req.instance_id),
                None,
            )
            self._authorize_app(record, req, owner)
        assert record is not None
        response = pb.AuthorizeAppResponse()
        if caller is not None:
            await self._require(
                "OpenApp",
                "app",
                self._parts(record.instance.descriptor.module_id, req.app_name),
                _error("APP_NOT_FOUND", req.app_name),
                caller,
            )
            response.caller_identity = run_owner(caller)
            served = caller.user
            response.caller_user_id = served.id if served is not None else ""
            response.caller_principal_id = caller.principal.id
            response.caller_principal_kind = caller.principal.kind
            response.caller_principal_name = caller.principal.name or ""
        return response

    def _authorize_app(
        self,
        record: pb.RegistryRecord | None,
        req: pb.AuthorizeAppRequest,
        owner: str,
    ) -> None:
        if record is None:
            raise DiscoveryError("LEASE_EXPIRED", "Provider registration expired")
        self._authorize(record, req.lease_token, owner)
        _require(
            any(a.name == req.app_name for a in record.instance.descriptor.apps),
            "APP_NOT_FOUND",
            req.app_name,
        )
        _require(
            record.instance.status == "READY",
            "MODULE_UNAVAILABLE",
            "Provider is not ready",
        )

    async def authorize_job(
        self,
        req: pb.AuthorizeJobRequest,
        owner: str,
        caller: CallContext | None = None,
    ) -> pb.AuthorizeJobResponse:
        """The host's lease, then ``TriggerJob`` or ``CancelJobRun`` for the
        caller whose token came with the trigger or the cancel."""
        _require(
            req.operation in JOB_OPERATIONS
            and (req.operation != "cancel" or _name(req.run_id)),
            "INVALID_ARGUMENT",
            "A job authorization names trigger, or cancel and a run",
        )
        record = await self._live_record(req.instance_id)
        self._authorize(record, req.lease_token, owner)
        _require(
            any(j.name == req.job_name for j in record.instance.descriptor.jobs),
            "JOB_NOT_FOUND",
            req.job_name,
        )
        response = pb.AuthorizeJobResponse()
        if caller is not None:
            await self.require_job(
                record.instance.descriptor.module_id,
                req.job_name,
                req.operation,
                req.run_id,
                caller,
            )
            response.caller_identity = run_owner(caller)
        return response

    async def require_job(
        self,
        module_id: str,
        job_name: str,
        operation: str,
        run_id: str,
        caller: CallContext,
    ) -> None:
        """``TriggerJob`` on ``job/…``, or ``CancelJobRun`` on ``job_run/…``."""
        if not self.guard.enforcing:
            return

        def check() -> None:
            with use_call_context(caller):
                require_job(
                    self.guard, self.project, module_id, job_name, operation, run_id
                )

        await asyncio.to_thread(check)


def require_job(
    guard: ServiceGuard,
    project: str,
    module_id: str,
    job_name: str,
    operation: str,
    run_id: str = "",
) -> None:
    """Whether the current caller may trigger a module's job, or cancel one of
    its runs (RFC §6.4); the job's or the run's not-found when it cannot see it.
    Discovery asks it for a module's job host, the engine for its own."""
    if operation == "trigger":
        guard.require(
            "TriggerJob",
            "job",
            [project, module_id, job_name],
            not_found=_error("JOB_NOT_FOUND", job_name),
        )
        return
    _require(operation == "cancel", "INVALID_ARGUMENT", "Unknown job operation")
    guard.require(
        "CancelJobRun",
        "job_run",
        [project, module_id, job_name, run_id],
        not_found=_error("RUN_NOT_FOUND", run_id),
    )
