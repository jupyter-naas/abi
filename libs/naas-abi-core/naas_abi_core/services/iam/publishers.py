"""The catalogs by publisher, with what the caller may grant (``AGENTS.md``,
"Publishers and listing").

The engine publishes the kernel services' catalogs, ``iam`` and the ``module``
catalog itself; naas_abi publishes ``nexus``; a module its declared catalog and
its own items of the ``module`` catalog (``module:<type>/<module>/<name>``). A
view by publisher shows only what the caller may grant: a type with no action
they may grant is left out, and so is a publisher with no such type.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Collection, Iterable, Mapping
from dataclasses import dataclass

from naas_abi_core.services.iam import grants, module_scopes
from naas_abi_core.services.iam.catalog import (
    ENGINE,
    NAAS_ABI,
    ActionCatalog,
    ActionSpec,
    ResourceType,
)
from naas_abi_core.services.iam.IAMPorts import GrantableAction, GrantableCatalog
from naas_abi_core.services.iam.names import (
    PLATFORM_SCOPE,
    container_of_scope,
    encode_segment,
)

SCOPE = "${scope}"
# A literal step of a name, ``<service>:<type>`` before a ``/``, after ``abi:``
# or a ``/``. Ids are percent-encoded (a ``:`` included), so none is inside one.
_STEP = re.compile(r"(?:^abi:|(?<=/))([a-z][a-z0-9_]*:[a-z][a-z0-9_]*)(?=/)")


@dataclass(frozen=True)
class PublishedAction:
    spec: ActionSpec
    # What the caller may grant of it: the resource patterns, written at
    # ``${scope}``, and those a Deny of theirs takes back.
    grantable: GrantableAction


@dataclass(frozen=True)
class PublishedType:
    service: str
    type: ResourceType
    actions: tuple[PublishedAction, ...]
    # Whether its existing resources are listed (``list_resources``), not only
    # offered as wildcards.
    listed: bool
    # The ``module`` catalog under a module: that module's items only.
    module: str = ""


@dataclass(frozen=True)
class Publisher:
    id: str
    kind: str  # "engine", "naas_abi" or "module"
    types: tuple[PublishedType, ...]


def _kind(publisher: str) -> str:
    if publisher == ENGINE:
        return "engine"
    if publisher == NAAS_ABI:
        return "naas_abi"
    return "module"


def _order(publisher: Publisher) -> tuple[int, str]:
    rank = {"engine": 0, "naas_abi": 1}
    return (rank.get(publisher.id, 2), publisher.id)


def _at(pattern: str, scope: str) -> str:
    """A pattern written at ``${scope}`` read at ``scope`` (a container, below
    one, or the platform, where what it holds is named after ``abi:``)."""
    container = container_of_scope(scope)
    prefix = f"{SCOPE}/"
    if pattern.startswith(prefix):
        under = "abi:" if container == PLATFORM_SCOPE else f"{container}/"
        return under + pattern[len(prefix) :]
    return container if pattern == SCOPE else pattern


def _names_another_type(pattern: str, own: str, containers: frozenset[str]) -> bool:
    """Whether ``pattern`` holds a literal step of a type that is no container
    and not ``own``: a name is its containers' steps, then its own, so such a
    pattern names nothing of ``own`` (``<service>:<type>``)."""
    return any(
        step != own and step not in containers for step in _STEP.findall(pattern)
    )


def _of_type(
    action: GrantableAction,
    scope: str,
    within: grants.Universe,
    *,
    service: str,
    type_name: str,
    containers: frozenset[tuple[str, str]],
    module: str = "",
) -> GrantableAction | None:
    """What of ``action`` can name resources of one type: its patterns that
    overlap a name of the type (``within``, the type's names: an id holds no
    step, so ``.../graph/*`` names no workspace, and a module's ``.../p/*``
    none of another module's items), read at ``scope``; for a module, its own
    items only. None when none does. A pattern with a step of another type
    that holds nothing is left out before the search, which would say so too."""
    if module:
        step = f"{module_scopes.SERVICE}:{type_name}/{encode_segment(module)}/*"
        names: tuple[str, ...] = (f"abi:*{step}",)
    else:
        names = ("*",)
    own = f"{service}:{type_name}"
    holders = frozenset(f"{s}:{t}" for s, t in containers)
    with grants.budget():
        try:
            kept = tuple(
                r
                for r in action.resources
                if not _names_another_type(_at(r, scope), own, holders)
                and grants.overlaps(_at(r, scope), names, within)
            )
        except grants.Exhausted:
            # Unsure: shown, as the patterns are what the caller holds anyway.
            kept = action.resources
    if not kept:
        return None
    return GrantableAction(action.action, kept, action.excluded)


def _types(
    catalog: ActionCatalog,
    granted: Mapping[str, GrantableAction],
    listable: Callable[[str, str], bool],
    *,
    scope: str,
    containers: frozenset[tuple[str, str]],
    nesting: frozenset[tuple[str, tuple[str, ...]]] = frozenset(),
    module: str = "",
    only: Collection[str] | None = None,
) -> list[PublishedType]:
    found: list[PublishedType] = []
    for resource_type in catalog.resource_types:
        if only is not None and resource_type.name not in only:
            continue
        within = grants.universe(
            catalog.service,
            resource_type.name,
            containers,
            resource_type.parents,
            nesting,
        )
        actions: list[PublishedAction] = []
        for spec in catalog.actions:
            if resource_type.name not in spec.resource_types:
                continue
            held = granted.get(catalog.qualified(spec.name))
            if held is None:
                continue
            of_type = _of_type(
                held,
                scope,
                within,
                service=catalog.service,
                type_name=resource_type.name,
                containers=containers,
                module=module,
            )
            if of_type is None:
                continue
            actions.append(PublishedAction(spec, of_type))
        if actions:
            found.append(
                PublishedType(
                    catalog.service,
                    resource_type,
                    tuple(actions),
                    listable(catalog.service, resource_type.name),
                    module,
                )
            )
    return found


def by_publisher(
    catalogs: Iterable[ActionCatalog],
    grantable: Iterable[GrantableCatalog],
    *,
    modules: Mapping[str, Collection[str]] | None = None,
    listable: Callable[[str, str], bool] = lambda _service, _type: False,
    scope: str = PLATFORM_SCOPE,
) -> list[Publisher]:
    """Each publisher with the types the caller may grant something of: the
    engine, then naas_abi, then the modules by key. ``modules``: each module's
    key and the ``module`` catalog types it exposes (its agents, apps, ...);
    ``listable``: whether a type is listed; ``scope``: where ``grantable`` was
    read. Under a type, only its patterns that can name its resources there."""
    granted: dict[str, GrantableAction] = {
        action.action: action for found in grantable for action in found.actions
    }
    catalogs = list(catalogs)
    containers = frozenset(
        (c.service, t.name) for c in catalogs for t in c.resource_types if t.container
    )
    # Where each container may sit: a pattern listed under a type names one of
    # its resources that can exist (no organisation in a workspace).
    nesting = frozenset(
        (f"{c.service}:{t.name}", tuple(t.parents))
        for c in catalogs
        for t in c.resource_types
        if t.container and t.parents
    )
    types: dict[str, list[PublishedType]] = {}
    for catalog in catalogs:
        if catalog.service == module_scopes.SERVICE:
            for module, exposed in sorted((modules or {}).items()):
                types.setdefault(module, []).extend(
                    _types(
                        catalog,
                        granted,
                        listable,
                        scope=scope,
                        containers=containers,
                        nesting=nesting,
                        module=module,
                        only=exposed,
                    )
                )
            continue
        types.setdefault(catalog.publisher, []).extend(
            _types(
                catalog,
                granted,
                listable,
                scope=scope,
                containers=containers,
                nesting=nesting,
            )
        )
    publishers = [
        Publisher(publisher, _kind(publisher), tuple(found))
        for publisher, found in types.items()
        if found
    ]
    return sorted(publishers, key=_order)
