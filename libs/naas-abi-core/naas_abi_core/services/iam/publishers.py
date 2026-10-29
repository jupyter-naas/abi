"""The catalogs by publisher, with what the caller may grant (``AGENTS.md``,
"Publishers and listing").

The engine publishes the kernel services' catalogs, ``iam`` and the ``module``
catalog itself; naas_abi publishes ``nexus``; a module its declared catalog and
its own items of the ``module`` catalog (``module:<type>/<module>/<name>``). A
view by publisher shows only what the caller may grant: a type with no action
they may grant is left out, and so is a publisher with no such type.
"""

from __future__ import annotations

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
from naas_abi_core.services.iam.names import encode_segment

SCOPE = "${scope}"


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


def _at_platform(pattern: str) -> str:
    """A pattern written at ``${scope}`` read at the platform, where what a
    container holds is named after ``abi:``: compared within a type's names,
    which start there."""
    prefix = f"{SCOPE}/"
    return "abi:" + pattern[len(prefix) :] if pattern.startswith(prefix) else pattern


def _of_module(
    action: GrantableAction,
    type_name: str,
    module: str,
    within: grants.Universe = grants.EVERYTHING,
) -> GrantableAction | None:
    """What of ``action`` (a ``module`` catalog action) can name ``module``'s
    items of ``type_name``: the patterns that overlap them among the type's
    names (``within``: an id holds no step, so ``.../p/*`` never reaches
    another module's items), None when none does."""
    step = f"{module_scopes.SERVICE}:{type_name}/{encode_segment(module)}/*"
    items = (f"abi:{step}", f"abi:*/{step}")
    with grants.budget():
        try:
            kept = tuple(
                r
                for r in action.resources
                if grants.overlaps(_at_platform(r), items, within)
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
    module: str = "",
    only: Collection[str] | None = None,
    containers: frozenset[tuple[str, str]] = frozenset(),
) -> list[PublishedType]:
    found: list[PublishedType] = []
    for resource_type in catalog.resource_types:
        if only is not None and resource_type.name not in only:
            continue
        actions: list[PublishedAction] = []
        for spec in catalog.actions:
            if resource_type.name not in spec.resource_types:
                continue
            held = granted.get(catalog.qualified(spec.name))
            if held is None:
                continue
            if module:
                held = _of_module(
                    held,
                    resource_type.name,
                    module,
                    grants.universe(catalog.service, resource_type.name, containers),
                )
                if held is None:
                    continue
            actions.append(PublishedAction(spec, held))
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
) -> list[Publisher]:
    """Each publisher with the types the caller may grant something of: the
    engine, then naas_abi, then the modules by key. ``modules``: each module's
    key and the ``module`` catalog types it exposes (its agents, apps, ...);
    ``listable``: whether a type is listed."""
    granted: dict[str, GrantableAction] = {
        action.action: action for found in grantable for action in found.actions
    }
    catalogs = list(catalogs)
    containers = frozenset(
        (c.service, t.name) for c in catalogs for t in c.resource_types if t.container
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
                        module=module,
                        only=exposed,
                        containers=containers,
                    )
                )
            continue
        types.setdefault(catalog.publisher, []).extend(
            _types(catalog, granted, listable)
        )
    publishers = [
        Publisher(publisher, _kind(publisher), tuple(found))
        for publisher, found in types.items()
        if found
    ]
    return sorted(publishers, key=_order)
