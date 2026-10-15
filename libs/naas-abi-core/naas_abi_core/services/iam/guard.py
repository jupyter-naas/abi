"""Authorization inside a kernel domain service (RFC §4.4, §5.4, §5.5, §6.3).

A domain service builds one ``ServiceGuard`` from its catalog and checks every
operation through it, before the backend is touched:

* ``require(action, type, parts)``: the caller may perform ``action`` on the
  resource, else ``PermissionDeniedError`` (it can see the resource) or the
  service's own not-found error (it cannot);
* ``filter(action, type, items, parts)``: the items of a list the caller may
  see, in order;
* ``create(action, type, parts)``: the create rule of §4.4, which places a new
  resource and records its placement once the create succeeded;
* ``forget(type, parts)``: drop the placements a create recorded.

The guard reads IAM from the engine services its domain service is wired with.
An owner is always wired with IAM. A facade calling the owner over NATS (the
dependency container, a client engine) is not, and checks nothing itself: the
owner it calls checks, once, with the caller the request's credentials name.

Names are canonical (``names.resource_name``); the org and workspace come from
IAM's placements, never from the request.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeVar

from naas_abi_core.engine.call_context import as_service_account, current_call_context
from naas_abi_core.services.iam.catalog import ActionCatalog, ResourceType
from naas_abi_core.services.iam.IAMPorts import (
    IIAMService,
    PermissionDeniedError,
    ResourceNotFoundError,
)
from naas_abi_core.services.iam.names import NONE, encode_id, resource_name

if TYPE_CHECKING:
    from naas_abi_core.services.ServiceBase import ServiceBase

Item = TypeVar("Item")
Parts = str | Sequence[str]
NotFound = Callable[[], BaseException]

# Who writes the placements a create records: the engine, for the caller whose
# create it authorized. The caller needs the create action, never iam:PutPlacement.
PLACEMENT_WRITER = "engine"

# Wire codes shared by every kernel service (RFC §5.4).
PERMISSION_DENIED = "PERMISSION_DENIED"
NOT_FOUND = "NOT_FOUND"


def wired_iam(service: ServiceBase) -> IIAMService | None:
    """The IAM a domain service checks with: the one it is wired with, if any."""
    if not service.services_wired:
        return None
    services = service.services
    return services.iam if services.iam_available() else None


@dataclass(frozen=True)
class Creation:
    """A create the guard allowed: the name as placed, and what to record."""

    name: str
    service: str
    canonical_id: str
    org: str
    workspace: str
    record_exact: bool
    record_prefix: bool
    iam: IIAMService | None

    def record(self) -> None:
        """Record the placement, once the create succeeded (RFC §4.4)."""
        if self.iam is None or not (self.record_exact or self.record_prefix):
            return
        with as_service_account(PLACEMENT_WRITER):
            if self.record_exact:
                self.iam.put_placement(
                    self.service, self.canonical_id, self.org, self.workspace
                )
            if self.record_prefix:
                self.iam.put_placement(
                    self.service, f"{self.canonical_id}/*", self.org, self.workspace
                )


class ServiceGuard:
    """One service's checks, against its catalog."""

    def __init__(
        self,
        catalog: ActionCatalog,
        iam: Callable[[], IIAMService | None],
    ) -> None:
        self.catalog = catalog
        self._iam = iam

    @classmethod
    def of(cls, catalog: ActionCatalog, service: ServiceBase) -> ServiceGuard:
        """The guard of a ``ServiceBase``: it checks once the service is wired with IAM."""
        return cls(catalog, lambda: wired_iam(service))

    @property
    def service(self) -> str:
        return self.catalog.service

    @property
    def iam(self) -> IIAMService | None:
        return self._iam()

    @property
    def enforcing(self) -> bool:
        return self.iam is not None

    def action(self, name: str) -> str:
        if self.catalog.action(name) is None:
            raise ValueError(f"{self.service} has no action {name!r}")
        return self.catalog.qualified(name)

    def _type(self, type: str) -> ResourceType:
        resource_type = self.catalog.resource_type(type)
        if resource_type is None:
            raise ValueError(f"{self.service} has no resource type {type!r}")
        return resource_type

    def canonical_id(self, type: str, parts: Parts) -> str:
        return encode_id(parts, self._type(type).id)

    # -- naming -----------------------------------------------------------------

    def name(self, type: str, parts: Parts = ()) -> str:
        """The resource's canonical name, in the org and workspace that own it."""
        resource_type = self._type(type)
        org = workspace = NONE
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
        self,
        action: str,
        type: str,
        parts: Parts = (),
        *,
        not_found: NotFound | None = None,
    ) -> str | None:
        """Raise unless the caller may perform ``action``; the name checked, or
        None when this service is not wired with IAM."""
        iam = self.iam
        if iam is None:
            return None
        name = self.name(type, parts)
        iam.require(self.action(action), name, not_found=not_found)
        return name

    def allowed(self, action: str, type: str, parts: Parts = ()) -> bool:
        """Whether the caller may perform ``action``, without raising."""
        iam = self.iam
        if iam is None:
            return True
        return iam.authorize(self.action(action), self.name(type, parts)).allowed

    def filter(
        self,
        action: str,
        type: str,
        items: Iterable[Item],
        parts: Callable[[Item], Parts],
    ) -> list[Item]:
        """The items the caller may perform the list ``action`` on, in order (§5.5)."""
        items = list(items)
        iam = self.iam
        if iam is None or not items:
            return items
        names = [self.name(type, parts(item)) for item in items]
        allowed = set(iam.filter(self.action(action), names).allowed)
        return [item for item, name in zip(items, names) if name in allowed]

    def create(
        self,
        action: str,
        type: str,
        parts: Parts,
        *,
        not_found: NotFound | None = None,
    ) -> Creation:
        """The create rule of RFC §4.4 for a resource that may not exist yet.

        A name an existing placement covers takes that placement, and the call's
        target workspace must be empty or match it. Otherwise the target
        workspace places the new resource (the platform when empty). The create
        action must be allowed on the name as placed. Call ``record()`` on the
        result once the create succeeded.
        """
        resource_type = self._type(type)
        canonical = encode_id(parts, resource_type.id)
        iam = self.iam
        if iam is None:
            return Creation(
                resource_name(self.service, type, parts, kind=resource_type.id),
                self.service,
                canonical,
                NONE,
                NONE,
                False,
                False,
                None,
            )
        qualified = self.action(action)
        target = current_call_context().workspace_id or None
        if resource_type.placement == "platform":
            name = resource_name(self.service, type, parts, kind=resource_type.id)
            iam.require(qualified, name, not_found=not_found)
            return Creation(
                name, self.service, canonical, NONE, NONE, False, False, iam
            )
        covering = iam.placement_of(self.service, canonical)
        if covering is not None:
            # A child of an existing container, or a placed name: as placed.
            name = resource_name(
                self.service,
                type,
                parts,
                kind=resource_type.id,
                org=covering.org,
                workspace=covering.workspace,
            )
            mismatch = target is not None and target != covering.workspace
            if mismatch:
                self._deny(iam, qualified, name, not_found)
            iam.require(qualified, name, not_found=not_found)
            return Creation(
                name, self.service, canonical, NONE, NONE, False, False, iam
            )
        org = workspace = NONE
        if target is not None:
            registered = iam.workspace_org(target)
            # TRANSITIONAL (#65 registers Nexus's orgs and workspaces with
            # iam:PutScope): a target workspace IAM has no scope for places the
            # new resource on the platform, where no workspace role reaches it.
            if registered is not None:
                org, workspace = registered, target
        name = resource_name(
            self.service,
            type,
            parts,
            kind=resource_type.id,
            org=org,
            workspace=workspace,
        )
        iam.require(qualified, name, not_found=not_found)
        container = resource_type.container
        return Creation(
            name,
            self.service,
            canonical,
            org,
            workspace,
            # Nothing can be created inside a platform-level top-level resource.
            record_exact=container or workspace != NONE,
            record_prefix=container,
            iam=iam,
        )

    def place_new(self, type: str, parts: Parts) -> None:
        """Place a resource the backend just created under an id it chose (a sent
        message), in the call's target workspace (RFC §4.4). The create was
        authorized on what names it (the sender); nothing is recorded for the
        platform or for a workspace IAM does not know."""
        iam = self.iam
        target = current_call_context().workspace_id or None
        if iam is None or target is None:
            return
        org = iam.workspace_org(target)
        if org is None:
            return
        resource_type = self._type(type)
        Creation(
            self.name(type, parts),
            self.service,
            encode_id(parts, resource_type.id),
            org,
            target,
            record_exact=True,
            record_prefix=resource_type.container,
            iam=iam,
        ).record()

    def forget(self, type: str, parts: Parts) -> None:
        """Drop the placements a create recorded for this resource (RFC §4.4)."""
        iam = self.iam
        if iam is None:
            return
        resource_type = self._type(type)
        canonical = encode_id(parts, resource_type.id)
        with as_service_account(PLACEMENT_WRITER):
            iam.delete_placement(self.service, canonical)
            if resource_type.container:
                iam.delete_placement(self.service, f"{canonical}/*")

    @staticmethod
    def _deny(
        iam: IIAMService, action: str, name: str, not_found: NotFound | None
    ) -> None:
        """Refuse with the §5.4 outcome computed on ``name``."""
        if iam.authorize(action, name).visible:
            raise PermissionDeniedError(action, name)
        raise _not_found(not_found, name)


def _not_found(not_found: NotFound | None, name: str | None) -> BaseException:
    if not_found is not None:
        return not_found()
    return ResourceNotFoundError(name or "", message="Resource not found")


# -- the wire (every kernel NATS adapter) ---------------------------------------------


def authorization_error_code(exc: BaseException) -> str | None:
    """The wire code of an authorization outcome, or None for any other error.

    A service's own not-found error keeps its own code: the service maps it.
    """
    if isinstance(exc, PermissionDeniedError):
        return PERMISSION_DENIED
    if isinstance(exc, ResourceNotFoundError):
        return NOT_FOUND
    return None


def raise_authorization_error(code: str, message: str) -> None:
    """Raise what the server raised, for ``PERMISSION_DENIED`` and ``NOT_FOUND``;
    return for any other code."""
    if code == PERMISSION_DENIED:
        raise PermissionDeniedError(message=message)
    if code == NOT_FOUND:
        raise ResourceNotFoundError(message=message)
