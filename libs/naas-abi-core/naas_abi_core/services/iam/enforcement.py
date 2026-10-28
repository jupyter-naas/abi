"""How a domain service enforces IAM: one ``ResourceGuard`` per service.

See ``AGENTS.md``: "Placements", "Evaluation" and "Action catalogs".

* Names are built from the request and placed by IAM (``name``), never taken
  from it: the org and workspace come from placements.
* ``require`` runs before the backend is touched and raises the §5.4 outcome:
  ``PermissionDeniedError`` when the caller can see the resource, the
  service's own not-found otherwise.
* ``filter`` keeps the items a list action allows; ``id_prefixes`` turns the
  caller's prefix hints into id prefixes a store can scan (§5.5).
* ``create`` applies the placement rule of a create (§4.4) and records the
  placement once the backend has created the resource; ``forget`` drops it on
  drop or delete.

The check lives in the domain service, so in process and over NATS behave the
same: a NATS primary calls the service as the caller it verified. A service
with no IAM (not wired into an engine: a library use, a test, or a NATS facade
whose server checks) does not enforce.
"""

from __future__ import annotations

import inspect
import io
from collections.abc import Callable, Iterable, Iterator, Sequence
from contextlib import AbstractContextManager, contextmanager
from dataclasses import replace
from functools import wraps
from typing import TYPE_CHECKING, TypeVar, cast
from urllib.parse import unquote

from naas_abi_core.engine.call_context import (
    CallContext,
    current_call_context,
    service_account,
    use_call_context,
)
from naas_abi_core.services.iam.catalog import ActionCatalog, ResourceType
from naas_abi_core.services.iam.IAMPorts import (
    IIAMService,
    PermissionDeniedError,
    ResourceNotFoundError,
)
from naas_abi_core.services.iam.names import NONE, encode_id, resource_name

if TYPE_CHECKING:
    from naas_abi_core.services.ServiceBase import ServiceBase

T = TypeVar("T")
Parts = str | Sequence[str]
NotFound = Callable[[], BaseException] | None

# The service account a service's own storage runs as (§10.1 as_service_account).
ENGINE = "engine"
# Wire codes of the authorization outcomes without a service-specific error.
PERMISSION_DENIED = "PERMISSION_DENIED"
NOT_FOUND = "NOT_FOUND"


def _noop() -> None:
    return None


class ResourceGuard:
    """Authorization of one service's operations against its catalog."""

    def __init__(
        self, catalog: ActionCatalog, iam: Callable[[], IIAMService | None]
    ) -> None:
        self.catalog = catalog
        self._iam = iam

    @classmethod
    def of(cls, catalog: ActionCatalog, service: ServiceBase) -> ResourceGuard:
        """The guard of a domain service: IAM once the service is wired."""
        return cls(catalog, service.wired_iam)

    @property
    def service(self) -> str:
        return self.catalog.service

    @property
    def iam(self) -> IIAMService | None:
        """IAM when the service is wired into an engine that has it."""
        return self._iam()

    def _type(self, name: str) -> ResourceType:
        resource_type = self.catalog.resource_type(name)
        if resource_type is None:
            raise ValueError(f"{self.service} has no resource type {name!r}")
        return resource_type

    def action(self, name: str) -> str:
        if self.catalog.action(name) is None:
            raise ValueError(f"{self.service} has no action {name!r}")
        return self.catalog.qualified(name)

    # -- names ------------------------------------------------------------------

    def canonical_id(self, type: str, parts: Parts) -> str:
        return encode_id(parts, self._type(type).id)

    def name(self, type: str, parts: Parts = ()) -> str:
        """The canonical name of a resource, where IAM places it."""
        resource_type = self._type(type)
        org, workspace = NONE, NONE
        iam = self.iam
        if iam is not None and resource_type.placement == "placed":
            org, workspace = iam.resolve_placement(
                self.service, encode_id(parts, resource_type.id)
            )
        return resource_name(
            self.service,
            type,
            parts,
            kind=resource_type.id,
            org=org,
            workspace=workspace,
        )

    # -- checks -----------------------------------------------------------------

    def require(
        self, action: str, type: str, parts: Parts = (), *, not_found: NotFound = None
    ) -> None:
        """Raise unless the caller may perform ``action`` on the resource (§5.4)."""
        iam = self.iam
        if iam is None:
            return
        iam.require(self.action(action), self.name(type, parts), not_found=not_found)

    def require_visible(
        self, type: str, parts: Parts = (), *, not_found: NotFound = None
    ) -> None:
        """Raise ``not_found()`` unless the caller can see the resource: some
        action of the service on its type is allowed (§5.4). A container-scoped
        list checks its container so first (§5.5)."""
        iam = self.iam
        if iam is None:
            return
        actions = [a for a in self.catalog.actions if type in a.resource_types]
        name = self.name(type, parts)
        decision = iam.authorize(self.catalog.qualified(actions[0].name), name)
        if not decision.visible:
            raise not_found() if not_found is not None else ResourceNotFoundError(name)

    def require_all(
        self,
        action: str,
        type: str,
        parts: Iterable[Parts],
        *,
        not_found: NotFound = None,
    ) -> None:
        """``require`` on each resource with one ``filter``: the first resource
        the caller may not act on fails the call with its §5.4 outcome (§6.3)."""
        iam = self.iam
        if iam is None:
            return
        qualified = self.action(action)
        if iam.allows_every(qualified, self.service, type):
            return
        names = [self.name(type, item) for item in parts]
        allowed = set(iam.filter(qualified, names).allowed)
        for name in names:
            if name not in allowed:
                iam.require(qualified, name, not_found=not_found)

    def allowed(self, action: str, type: str, parts: Parts = ()) -> bool:
        iam = self.iam
        if iam is None:
            return True
        return iam.authorize(self.action(action), self.name(type, parts)).allowed

    def denies(self, action: str, type: str, parts: Parts = ()) -> bool:
        """Whether a Deny, a seal or a suspension refuses ``action`` on the
        resource, not merely the lack of an Allow."""
        iam = self.iam
        if iam is None:
            return False
        decision = iam.authorize(self.action(action), self.name(type, parts))
        return decision.reason in ("explicit_deny", "sealed", "suspended")

    def allows_every(self, action: str, type: str) -> bool:
        """Whether the caller may perform ``action`` on every resource of the type."""
        iam = self.iam
        if iam is None:
            return True
        return iam.allows_every(self.action(action), self.service, type)

    def filter(
        self,
        action: str,
        type: str,
        items: Iterable[T],
        parts: Callable[[T], Parts],
    ) -> list[T]:
        """The items the caller may perform ``action`` on, in order (§5.5)."""
        iam = self.iam
        if iam is None:
            return list(items)  # not enforcing: the listing as is
        listed = list(items)
        if not listed or iam.allows_every(self.action(action), self.service, type):
            return listed
        names = [self.name(type, parts(item)) for item in listed]
        allowed = set(iam.filter(self.action(action), names).allowed)
        return [item for item, name in zip(listed, names) if name in allowed]

    def id_prefixes(self, action: str, type: str) -> list[str] | None:
        """Id prefixes every item a list may return starts with (§5.5 push-down).

        ``None`` when the scan cannot be narrowed, ``[]`` when nothing can be
        allowed. The prefixes are decoded ids: a key-value key, an object path.
        Denies and placements still apply, through ``filter``.

        Every IAM gives hints with ``filter``, the NATS client included (it
        carries the server's), and ``[""]`` when it cannot bound them; none at
        all means no Allow can admit an item, as ``IAMService`` reads it too.
        """
        iam = self.iam
        if iam is None:
            return None
        hints = iam.filter(self.action(action), ()).prefix_hints
        if not hints:
            return []
        head = f"{self.service}:{type}/"
        prefixes: list[str] = []
        for hint in hints:
            fields = hint.split(":", 3)
            if len(fields) != 4 or fields[0] != "abi" or not fields[3].startswith(head):
                return None
            prefixes.append(_decoded_prefix(fields[3][len(head) :]))
        if "" in prefixes:
            return None
        kept: list[str] = []
        for prefix in sorted(set(prefixes)):
            if not any(prefix.startswith(shorter) for shorter in kept):
                kept.append(prefix)
        return kept

    # -- creates and deletes (§4.4) ----------------------------------------------

    def create(
        self,
        action: str,
        type: str,
        parts: Parts,
        *,
        container: tuple[str, Parts] | None = None,
        exists: Callable[[], bool] | None = None,
        container_exists: Callable[[], bool] | None = None,
        not_found: NotFound = None,
    ) -> Callable[[], None]:
        """Authorize a create on the name as placed; returns ``commit()``.

        Call ``commit()`` once the backend has created the resource: it records
        the placement the create decided, if any. ``container`` is the
        top-level container the resource sits in (a document or dataset
        namespace), placed with it when nothing places it yet. ``exists`` and
        ``container_exists`` tell an existing resource, on which the target
        workspace is ignored, from a new one.
        """
        iam = self.iam
        if iam is None:
            return _noop
        qualified = self.action(action)
        resource_type = self._type(type)
        if resource_type.placement == "platform":
            iam.require(qualified, self.name(type, parts), not_found=not_found)
            return _noop
        target = current_call_context().workspace_id or None
        unit_type, unit_parts = container if container is not None else (type, parts)
        unit = self._type(unit_type)
        unit_id = encode_id(unit_parts, unit.id)
        placed = iam.placement_of(self.service, encode_id(parts, resource_type.id))
        if placed is None:
            existing = (
                (container_exists is not None and container_exists())
                if container is not None
                else (exists is not None and exists())
            )
            if existing and not unit.container:
                # An existing top-level resource nothing placed: the platform's.
                iam.require(qualified, self.name(type, parts), not_found=not_found)
                return _noop
            if existing:
                # An existing container nothing placed predates placements, so it
                # is the platform's (§13): record it so, and create inside it.
                self._place(unit, unit_id, NONE, NONE, exact_only=False)
                placed = iam.placement_of(
                    self.service, encode_id(parts, resource_type.id)
                )
        if placed is not None:
            name = resource_name(
                self.service,
                type,
                parts,
                kind=resource_type.id,
                org=placed.org,
                workspace=placed.workspace,
            )
            iam.require(qualified, name, not_found=not_found)
            if target is not None and target != placed.workspace:
                # A child takes its container's placement; the target workspace
                # only decides for a new name, and never moves an existing one.
                if exists is None or not exists():
                    raise PermissionDeniedError(
                        qualified,
                        name,
                        message=f"{name} is not in workspace {target}",
                    )
            return _noop
        org = (iam.workspace_org(target) or NONE) if target is not None else NONE
        workspace = target or NONE
        name = resource_name(
            self.service,
            type,
            parts,
            kind=resource_type.id,
            org=org,
            workspace=workspace,
        )
        iam.require(qualified, name, not_found=not_found)

        def commit() -> None:
            if unit.container or workspace != NONE:
                self._place(
                    unit, unit_id, org, workspace, exact_only=not unit.container
                )

        return commit

    def forget(self, type: str, parts: Parts) -> None:
        """Drop the placements a create recorded for the resource (§4.4)."""
        iam = self.iam
        if iam is None:
            return
        resource_type = self._type(type)
        canonical = encode_id(parts, resource_type.id)
        keys = [canonical] + ([f"{canonical}/*"] if resource_type.container else [])
        with internal_call():
            for key in keys:
                iam.delete_placement(self.service, key)

    def _place(
        self,
        unit: ResourceType,
        unit_id: str,
        org: str,
        workspace: str,
        *,
        exact_only: bool,
    ) -> None:
        iam = self.iam
        assert iam is not None
        keys = [unit_id] + ([] if exact_only else [f"{unit_id}/*"])
        with internal_call():
            for key in keys:
                iam.put_placement(self.service, key, org, workspace)


def scan_allowed(
    guard: ResourceGuard,
    action: str,
    type: str,
    prefix: str,
    limit: int,
    after: str | None,
    fetch: Callable[[str, int, str | None], tuple[Sequence[str], str | None]],
) -> tuple[list[str], str | None]:
    """A page of the keys under ``prefix`` the caller may list (§5.5).

    ``fetch(prefix, limit, after)`` returns ascending keys and the cursor of
    the next page. The scan is narrowed to the caller's id prefixes, and
    paging applies after filtering: a page holds up to ``limit`` allowed keys,
    and its cursor (the last key) continues the listing.
    """
    narrowed = guard.id_prefixes(action, type)
    if narrowed is None:
        scans = [prefix]
    else:
        # Disjoint prefixes, so their keys come in the order of the prefixes.
        scans = sorted(
            {
                longer
                for hint in narrowed
                for longer in (_longer(prefix, hint),)
                if longer is not None
            }
        )
    keys: list[str] = []
    for index, scan in enumerate(scans):
        cursor = after
        while True:
            page, next_after = fetch(scan, limit, cursor)
            allowed = set(guard.filter(action, type, page, lambda key: key))
            for position, key in enumerate(page):
                if key not in allowed:
                    continue
                keys.append(key)
                if len(keys) == limit:
                    more = (
                        position < len(page) - 1
                        or next_after is not None
                        or index < len(scans) - 1
                    )
                    return keys, key if more else None
            if next_after is None:
                break
            cursor = next_after
    return keys, None


def _longer(prefix: str, hint: str) -> str | None:
    """The narrower of two prefixes when one extends the other, else None."""
    if hint.startswith(prefix):
        return hint
    if prefix.startswith(hint):
        return prefix
    return None


@contextmanager
def internal_call(name: str = ENGINE) -> Iterator[CallContext]:
    """Run a service's own bookkeeping as the engine, for no user and no
    target workspace: its own storage in another service, its placements.

    The caller was authorized on the operation that needs it.

    Core only. Inside, the user's bounds, scope and audience are cleared and
    the principal holds the engine's access (the sealed ``iam/`` secrets,
    ``dataset:QueryUnchecked``), so never wrap code a caller steers, only the
    single call of a service's own storage. Nothing outside ``naas_abi_core``
    imports it (``enforcement_boundary_test``): a module that has maintenance
    to run asks for a narrow entry point, such as ``catalog_maintenance``.
    """
    context = replace(
        current_call_context(),
        principal=service_account(name),
        on_behalf_of=None,
        audience=None,
        token_id=None,
        scope=None,
        workspace_id=None,
    )
    with use_call_context(context):
        yield context


class _OwnContext:
    """A context manager whose entry and exit run as the engine, as its body
    does for a ``@contextmanager`` function (a lock, a stream)."""

    def __init__(self, target: AbstractContextManager) -> None:
        self._target = target

    def __enter__(self):
        with internal_call():
            return self._target.__enter__()

    def __exit__(self, *exc_info):
        with internal_call():
            return self._target.__exit__(*exc_info)

    def __getattr__(self, name: str):
        return getattr(self._target, name)


class _OwnStorage:
    """``target`` with every call run as the engine (``internal_call``).

    That is the call itself; a generator's steps; and, for a method that
    returns a context manager, its entry and exit. What the caller does with
    a plain result afterwards (reading a stream's bytes) is the caller's own.
    """

    def __init__(self, target: object) -> None:
        self._target = target

    def __getattr__(self, name: str):
        value = getattr(self._target, name)
        if not callable(value):
            return value

        @wraps(value)
        def call(*args, **kwargs):
            with internal_call():
                result = value(*args, **kwargs)
            # A generator runs its body when iterated: each step as the engine.
            if inspect.isgenerator(result):
                return _own_steps(result)
            # A context manager runs its body on entry and exit.
            if isinstance(result, AbstractContextManager) and not isinstance(
                result, io.IOBase
            ):
                return _OwnContext(result)
            return result

        return call


def _own_steps(generator: Iterator[T]) -> Iterator[T]:
    while True:
        with internal_call():
            try:
                item = next(generator)
            except StopIteration:
                return
        yield item


def own_storage(target: T) -> T:
    """A service's own storage in another service, used as the engine.

    The cache stores entries in the key-value or object storage service, for
    example: the caller was authorized on the cache key, and the entries are
    the cache's, not the caller's.
    """
    return cast(T, _OwnStorage(target))


def _decoded_prefix(encoded: str) -> str:
    """Decode an encoded id prefix, dropping a trailing partial ``%XX``."""
    cut = encoded.rfind("%")
    if cut != -1 and len(encoded) - cut < 3:
        encoded = encoded[:cut]
    return unquote(encoded)


def authorization_error_code(exc: BaseException) -> str | None:
    """The wire code of an authorization outcome without a service error of its own."""
    if isinstance(exc, PermissionDeniedError):
        return PERMISSION_DENIED
    if isinstance(exc, ResourceNotFoundError):
        return NOT_FOUND
    return None


def raise_authorization_error(code: str, message: str) -> None:
    """Raise what ``authorization_error_code`` encoded, on the client side of a NATS call."""
    if code == PERMISSION_DENIED:
        raise PermissionDeniedError(message=message)
    if code == NOT_FOUND:
        error = ResourceNotFoundError("")
        error.args = (message,)
        raise error
