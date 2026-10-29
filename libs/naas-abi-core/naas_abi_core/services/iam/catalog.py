"""Action catalogs: what each service lets a policy name.

Every service declares one next to its domain code (``iam_catalog.py`` in core,
``iam_catalog.yaml`` in a module package) and registers it while it loads.
Policies are validated against the registered catalogs, and the built-in roles
are generated from them by access level.
"""

from __future__ import annotations

import threading
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal, cast

from naas_abi_core.services.iam.names import (
    IdKind,
    has_wildcard,
    is_valid_action_name,
    is_valid_service,
    matches,
)

Level = Literal["list", "read", "write", "admin"]
Placement = Literal["placed", "platform"]

LEVELS: tuple[Level, ...] = ("list", "read", "write", "admin")
# The catalog format: 2 since the flags (``policy_only``, ``owner_only``,
# ``platform_access``) exist. A catalog stored in format 1 says nothing about
# them, which must never read as "no type is policy only". 3 since container
# paths: what formats 1 and 2 called ``container`` is ``id_prefix``.
CATALOG_FORMAT = 3
FLAGS_FORMAT = 2
_ID_KINDS = ("opaque", "path", "singleton")
_PLACEMENTS = ("placed", "platform")


class CatalogError(ValueError):
    """A catalog that cannot be registered."""


@dataclass(frozen=True)
class ResourceType:
    name: str
    id: IdKind = "opaque"
    placement: Placement = "placed"
    # A container: a step of the names of what it holds, registered with IAM
    # (``AGENTS.md``, "Containers"). Never placed, never a path type.
    container: bool = False
    # Its id is the prefix of its children's ids (a document namespace): placed
    # as a pair, the id and ``<id>/*`` (``AGENTS.md``, "Placements").
    id_prefix: bool = False
    personal: bool = False
    description: str = ""
    # A module scope: what a module exposes (its agents, apps, workflows,
    # pipelines and the actions it declares). The built-in viewer and member
    # roles never reach one (``roles.py``); admins and owners hold them all.
    module_scope: bool = False
    # Reached through a policy only: no built-in role holds it at its scope,
    # owners included (Nexus's features).
    policy_only: bool = False
    # A container type at which a role attached brings the platform companions
    # (``roles.py``; Nexus's workspace).
    platform_companions: bool = False
    # A container type: the containers it may sit in, ``<service>:<type>`` each,
    # ``-`` for the platform; empty: any (Nexus's workspace: an organization or
    # the platform).
    parents: tuple[str, ...] = ()


@dataclass(frozen=True)
class ActionSpec:
    name: str
    level: Level
    resource_types: tuple[str, ...]
    creates: bool = False
    subjects: tuple[str, ...] = ()
    description: str = ""
    # An ``admin`` action no role below owner holds (deleting the scope itself).
    owner_only: bool = False
    # Deleting a container of its type (``iam.delete_container``).
    deletes: bool = False


@dataclass(frozen=True)
class PlatformAccess:
    """Platform-level resources of a catalog that a role's platform companions
    reach (``roles.py``, "Platform types" in ``AGENTS.md``): ``viewer`` actions with
    ``builtin.platform.viewer`` and ``.member``, ``member`` actions with
    ``.member``, ``self_`` actions with ``builtin.self``. ``resources`` are
    ``<type>/<id>`` patterns, named ``abi:<service>:<type>/<id>``."""

    resources: tuple[str, ...]
    viewer: tuple[str, ...] = ()
    member: tuple[str, ...] = ()
    self_: tuple[str, ...] = ()


@dataclass(frozen=True)
class ActionCatalog:
    service: str
    version: int
    resource_types: tuple[ResourceType, ...] = ()
    actions: tuple[ActionSpec, ...] = ()
    # The module that declared this catalog (``module_scopes.py``), empty for
    # a kernel service's and Nexus's: a module's catalog is its own alone.
    module: str = ""
    # What the platform companions of the roles reach of this catalog. A
    # first-party catalog's only: a module's grants nothing to every member.
    platform_access: tuple[PlatformAccess, ...] = ()
    # The format it was written in. A first-party catalog of an older format
    # (stored before the flags existed) holds nothing for the built-in roles
    # until it is registered again (``roles.py``): its flags are unknown.
    format: int = CATALOG_FORMAT

    @property
    def flags_known(self) -> bool:
        """Whether its flags can be read: a module's catalog has none to read
        (its types are module scopes), a first-party one from format 2."""
        return bool(self.module) or self.format >= FLAGS_FORMAT

    def __post_init__(self) -> None:
        errors = _catalog_errors(self)
        if errors:
            raise CatalogError("; ".join(errors))

    def qualified(self, action: str) -> str:
        return f"{self.service}:{action}"

    def resource_type(self, name: str) -> ResourceType | None:
        return next((t for t in self.resource_types if t.name == name), None)

    def action(self, name: str) -> ActionSpec | None:
        return next((a for a in self.actions if a.name == name), None)

    def container_action(self, type_name: str, flag: str) -> ActionSpec | None:
        """The action marked ``flag`` (``creates`` or ``deletes``) on a type."""
        return next(
            (
                a
                for a in self.actions
                if getattr(a, flag) and type_name in a.resource_types
            ),
            None,
        )

    def to_dict(self, *, stored: bool = False) -> dict[str, Any]:
        """The catalog format. ``stored``: with its ``format``, as a store keeps
        it; left out otherwise, so what a module manifest hashes (its declared
        catalog) is the same as before the format existed."""
        found: dict[str, Any] = {
            "service": self.service,
            "version": self.version,
            "resource_types": [
                {
                    "name": t.name,
                    "id": t.id,
                    "placement": t.placement,
                    "container": t.container,
                    **({"id_prefix": True} if t.id_prefix else {}),
                    "personal": t.personal,
                    "description": t.description,
                    **({"module_scope": True} if t.module_scope else {}),
                    **({"policy_only": True} if t.policy_only else {}),
                    **({"platform_companions": True} if t.platform_companions else {}),
                    **({"parents": list(t.parents)} if t.parents else {}),
                }
                for t in self.resource_types
            ],
            "actions": [
                {
                    "name": a.name,
                    "level": a.level,
                    "resource_types": list(a.resource_types),
                    "creates": a.creates,
                    "subjects": list(a.subjects),
                    "description": a.description,
                    **({"owner_only": True} if a.owner_only else {}),
                    **({"deletes": True} if a.deletes else {}),
                }
                for a in self.actions
            ],
        }
        if self.module:
            found["module"] = self.module
        if stored:
            found["format"] = self.format
        if self.platform_access:
            found["platform_access"] = [
                {
                    "resources": list(row.resources),
                    "viewer": list(row.viewer),
                    "member": list(row.member),
                    "self": list(row.self_),
                }
                for row in self.platform_access
            ]
        return found

    @classmethod
    def from_dict(
        cls, data: Mapping[str, Any], *, stored: bool = False
    ) -> ActionCatalog:
        """The catalog format (``AGENTS.md``, "Action catalogs"), as loaded from YAML or JSON.
        ``stored``: read back from a store, where a catalog with no ``format`` was
        written before the flags existed (format 1); anything else is read as
        written now. A stored catalog of a format before 3 called ``id_prefix``
        ``container``."""
        format_ = int(data.get("format", 1 if stored else CATALOG_FORMAT))
        old = stored and format_ < 3
        try:
            return cls(
                service=str(data["service"]),
                version=int(data["version"]),
                resource_types=tuple(
                    ResourceType(
                        name=str(t["name"]),
                        id=cast(IdKind, t.get("id", "opaque")),
                        placement=cast(Placement, t.get("placement", "placed")),
                        container=not old and bool(t.get("container", False)),
                        id_prefix=bool(
                            t.get("container" if old else "id_prefix", False)
                        ),
                        personal=bool(t.get("personal", False)),
                        description=str(t.get("description", "")),
                        module_scope=bool(t.get("module_scope", False)),
                        policy_only=bool(t.get("policy_only", False)),
                        platform_companions=bool(t.get("platform_companions", False)),
                        parents=tuple(t.get("parents", ()) or ()),
                    )
                    for t in data.get("resource_types", ())
                ),
                actions=tuple(
                    ActionSpec(
                        name=str(a["name"]),
                        level=cast(Level, a["level"]),
                        resource_types=tuple(a.get("resource_types", ())),
                        creates=bool(a.get("creates", False)),
                        subjects=tuple(a.get("subjects", ())),
                        description=str(a.get("description", "")),
                        owner_only=bool(a.get("owner_only", False)),
                        deletes=bool(a.get("deletes", False)),
                    )
                    for a in data.get("actions", ())
                ),
                module=str(data.get("module", "") or ""),
                platform_access=tuple(
                    PlatformAccess(
                        resources=tuple(row.get("resources", ())),
                        viewer=tuple(row.get("viewer", ())),
                        member=tuple(row.get("member", ())),
                        self_=tuple(row.get("self", ())),
                    )
                    for row in data.get("platform_access", ())
                ),
                # Stored before the flags: no "format" key.
                format=format_,
            )
        except (KeyError, TypeError) as exc:
            raise CatalogError(f"Malformed catalog: {exc!r}") from exc


def _catalog_errors(catalog: ActionCatalog) -> list[str]:
    errors: list[str] = []
    if not is_valid_service(catalog.service):
        errors.append(f"invalid service name {catalog.service!r}")
    if catalog.version < 1:
        errors.append("version must be at least 1")
    type_names = [t.name for t in catalog.resource_types]
    if len(set(type_names)) != len(type_names):
        errors.append("resource type names must be unique")
    for t in catalog.resource_types:
        if not is_valid_service(t.name):
            errors.append(f"invalid resource type name {t.name!r}")
        if t.id not in _ID_KINDS:
            errors.append(f"resource type {t.name}: id must be one of {_ID_KINDS}")
        if t.placement not in _PLACEMENTS:
            errors.append(
                f"resource type {t.name}: placement must be one of {_PLACEMENTS}"
            )
        if t.module_scope and (t.placement != "placed" or t.personal or t.id_prefix):
            errors.append(
                f"resource type {t.name}: a module scope is placed in a container, "
                "neither personal nor an id prefix"
            )
        if t.container and (t.id == "path" or t.personal or t.id_prefix):
            errors.append(
                f"resource type {t.name}: a container's id is one segment, "
                "neither personal nor an id prefix"
            )
        if t.container and not any(
            a.creates and t.name in a.resource_types for a in catalog.actions
        ):
            errors.append(
                f"resource type {t.name}: a container type needs an action marked "
                "creates on it (registering one)"
            )
        if t.parents and not t.container:
            errors.append(f"resource type {t.name}: only a container type names parents")
        for parent in t.parents:
            service, colon, type_name = parent.partition(":")
            if parent != "-" and not (
                colon and is_valid_service(service) and is_valid_service(type_name)
            ):
                errors.append(
                    f"resource type {t.name}: a parent is <service>:<type> or -, "
                    f"not {parent!r}"
                )
        if t.platform_companions and not t.container:
            errors.append(
                f"resource type {t.name}: only a container type brings the "
                "platform companions"
            )
    action_names = [a.name for a in catalog.actions]
    if len(set(action_names)) != len(action_names):
        errors.append("action names must be unique within a service")
    for a in catalog.actions:
        if not is_valid_action_name(a.name):
            errors.append(f"invalid action name {a.name!r}")
        if a.level not in LEVELS:
            errors.append(f"action {a.name}: level must be one of {LEVELS}")
        if not a.resource_types:
            errors.append(f"action {a.name}: names no resource type")
        for name in a.resource_types:
            if name not in type_names:
                errors.append(f"action {a.name}: unknown resource type {name!r}")
        if a.owner_only and a.level != "admin":
            errors.append(f"action {a.name}: only an admin action is owner-only")
        if a.deletes and not any(
            t.container for t in catalog.resource_types if t.name in a.resource_types
        ):
            errors.append(
                f"action {a.name}: only an action on a container type deletes"
            )
    if catalog.platform_access and catalog.module:
        errors.append("a module's catalog declares no platform access")
    for row in catalog.platform_access:
        if not row.resources:
            errors.append("platform access names no resource")
        for resource in row.resources:
            type_name, slash, rest = resource.partition("/")
            if type_name not in type_names or not slash or not rest:
                errors.append(
                    f"platform access: {resource!r} is not <type>/<id> of this catalog"
                )
        for name in (*row.viewer, *row.member, *row.self_):
            if name not in action_names:
                errors.append(f"platform access: unknown action {name!r}")
    return errors


@dataclass
class CatalogRegistry:
    """The catalogs registered in this process, by service. Thread-safe."""

    _catalogs: dict[str, ActionCatalog] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def register(self, catalog: ActionCatalog) -> bool:
        """Keep ``catalog`` unless a higher version is registered. True when kept."""
        with self._lock:
            current = self._catalogs.get(catalog.service)
            if current is not None and current.version > catalog.version:
                return False
            self._catalogs[catalog.service] = catalog
            return True

    def get(self, service: str) -> ActionCatalog | None:
        with self._lock:
            return self._catalogs.get(service)

    def all(self) -> list[ActionCatalog]:
        with self._lock:
            return sorted(self._catalogs.values(), key=lambda c: c.service)

    def actions(self) -> list[str]:
        """Every registered action, qualified."""
        return [c.qualified(a.name) for c in self.all() for a in c.actions]

    def is_registered(self, action: str) -> bool:
        service, _, name = action.partition(":")
        catalog = self.get(service)
        return catalog is not None and catalog.action(name) is not None

    def matching(self, pattern: str) -> list[str]:
        """The registered actions ``pattern`` matches."""
        if not has_wildcard(pattern):
            return [pattern] if self.is_registered(pattern) else []
        return [action for action in self.actions() if matches(pattern, action)]

    def resource_type(self, service: str, type_name: str) -> ResourceType | None:
        catalog = self.get(service)
        return catalog.resource_type(type_name) if catalog is not None else None

    def is_container(self, service: str, type_name: str) -> bool:
        found = self.resource_type(service, type_name)
        return found is not None and found.container

    def container_types(self) -> frozenset[tuple[str, str]]:
        """Every registered container type, ``(service, type)``."""
        return frozenset(
            (c.service, t.name)
            for c in self.all()
            for t in c.resource_types
            if t.container
        )

    def actions_on(self, service: str, resource_type: str) -> list[str]:
        """The actions of ``service`` whose catalog lists ``resource_type``.

        They decide whether a resource is visible to a caller.
        """
        catalog = self.get(service)
        if catalog is None:
            return []
        return [
            catalog.qualified(a.name)
            for a in catalog.actions
            if resource_type in a.resource_types
        ]


def removed_actions(old: ActionCatalog, new: ActionCatalog) -> list[str]:
    """The actions ``old`` has and ``new`` drops, qualified."""
    kept = {a.name for a in new.actions}
    return [old.qualified(a.name) for a in old.actions if a.name not in kept]


def service_action(
    name: str,
    level: Level,
    resource_types: tuple[str, ...],
    *subjects: str,
    creates: bool = False,
    description: str = "",
) -> ActionSpec:
    """An ``ActionSpec`` for a service catalog; ``subjects`` in full."""
    return ActionSpec(
        name=name,
        level=level,
        resource_types=resource_types,
        creates=creates,
        subjects=subjects,
        description=description,
    )


def stream_subjects(transfer_prefix: str) -> tuple[str, ...]:
    """A service's transfer subjects, which its stream actions travel on (§6.4)."""
    return (
        f"{transfer_prefix}.open",
        *(
            f"{transfer_prefix}.*.{operation}"
            for operation in ("write", "start", "read", "close")
        ),
    )
