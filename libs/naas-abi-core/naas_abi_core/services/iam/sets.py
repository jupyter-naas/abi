"""Organisation and workspace sets (``AGENTS.md``, "Sets").

A set is what an org or a workspace may use: module scopes and Nexus features.
IAM bounds every decision a user's Allow makes on them by the set of the
resource's org and the set of its workspace (``evaluator.py``), and every grant
made there (``grants.py``): the platform admin and the service accounts are not
bound.

A set has two parts, each ``None`` when nothing is recorded (everything):

* ``modules``: items, each one of

  * ``<module>``: the whole module, every agent, app, workflow and pipeline of
    it (``module:<type>/<module>/*``) and every action of the catalog it
    declares;
  * ``<type>/<module>/<name>``: one agent, app, workflow or pipeline of it
    (``<type>`` is ``agent``, ``app``, ``workflow`` or ``pipeline``);
    ``<type>/<module>/*`` is every one of that type, ``<type>/*/*`` every one
    of that type of every module, installed now or later;
  * ``<service>:<Action>``: one action of the catalog a module declares
    (``<service>`` is ``module_service(<module>)``); ``<service>:*`` every
    action of it, ``*:*`` every action every module declares.

  The wildcards say "every module but only these agents" without listing the
  modules installed today (a catalog seed narrowing an org with no set:
  ``agent/acme.people/Recruiter``, ``app/*/*``, ``workflow/*/*``,
  ``pipeline/*/*``, ``*:*``).

  ``<module>`` is the module's stable identifier (``module_scopes``); names are
  written decoded, as the module names them.
* ``features``: Nexus feature keys (``nexus:feature/<key>``).

The effective set of a workspace is its org's set and its own, intersected
(``intersect``). A workspace's recorded items must each be within its org's
(``outside``).
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from naas_abi_core.services.iam.catalog import CatalogError, CatalogRegistry
from naas_abi_core.services.iam.IAMPorts import ScopeSet
from naas_abi_core.services.iam.module_scopes import SERVICE as MODULE_SERVICE
from naas_abi_core.services.iam.module_scopes import TYPES, module_service
from naas_abi_core.services.iam.names import (
    NONE,
    ResourceName,
    encode_segment,
    resource_name,
)

FEATURE_TYPE = ("nexus", "feature")
# ``<type>/<module>/*``: every item of that type of the module.
ANY = "*"
USE_FEATURE = "nexus:UseFeature"

_MODULE = re.compile(r"^[^\s/:]{1,200}$")
_DECLARED = re.compile(r"^([a-z][a-z0-9_]*|\*):([A-Z][A-Za-z0-9]*|\*)$")
_FEATURE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_MAX_ITEMS = 2000


class SetValidationError(ValueError):
    """A set that cannot be recorded: malformed items, or a workspace's set
    wider than its org's."""


# -- items ---------------------------------------------------------------------


@dataclass(frozen=True)
class Item:
    """One parsed module item: ``kind`` is ``module``, ``scope`` or ``action``."""

    kind: str
    module: str = ""
    type: str = ""
    name: str = ""
    service: str = ""
    action: str = ""


def parse_item(item: str) -> Item:
    """``SetValidationError`` for anything that is not an item of the grammar."""
    if not isinstance(item, str) or not item:
        raise SetValidationError(f"Invalid set item {item!r}")
    declared = _DECLARED.match(item)
    if declared:
        if declared.group(1) == ANY and declared.group(2) != ANY:
            raise SetValidationError(
                f"Invalid set item {item!r}: an action of every module is *:*"
            )
        return Item("action", service=declared.group(1), action=item)
    if "/" not in item:
        if not _MODULE.match(item) or _service_of(item) is None:
            raise SetValidationError(
                f"Invalid module {item!r}: a module's identifier (<type>/*/* and "
                "*:* say every module)"
            )
        return Item("module", module=item)
    type_name, _, rest = item.partition("/")
    module, slash, name = rest.partition("/")
    if (
        type_name not in TYPES
        or not slash
        or not name
        or not _MODULE.match(module)
        or (module == ANY and name != ANY)
        or (module != ANY and _service_of(module) is None)
    ):
        raise SetValidationError(
            f"Invalid set item {item!r}: <module>, <type>/<module>/<name> with type "
            f"one of {', '.join(TYPES)} (<type>/*/* for every module), or "
            "<service>:<Action>"
        )
    return Item("scope", module=module, type=type_name, name=name)


def _service_of(module: str) -> str | None:
    """``module_service(module)``, None for a name that has no catalog name
    (``*``, ``--``): no module can be called that."""
    try:
        return module_service(module)
    except CatalogError:
        return None


def normalize(
    modules: Iterable[str] | None, features: Iterable[str] | None
) -> tuple[tuple[str, ...] | None, tuple[str, ...] | None]:
    """Sorted, without duplicates, every item checked (``SetValidationError``
    listing each bad one)."""
    errors: list[str] = []
    kept_modules: tuple[str, ...] | None = None
    if modules is not None:
        found = sorted(set(modules))
        for item in found:
            try:
                parse_item(item)
            except SetValidationError as exc:
                errors.append(str(exc))
        kept_modules = tuple(found)
    kept_features: tuple[str, ...] | None = None
    if features is not None:
        found = sorted(set(features))
        errors += [
            f"Invalid feature {key!r}"
            for key in found
            if not isinstance(key, str) or not _FEATURE.match(key)
        ]
        kept_features = tuple(found)
    if len(kept_modules or ()) + len(kept_features or ()) > _MAX_ITEMS:
        errors.append(f"A set holds at most {_MAX_ITEMS} items")
    if errors:
        raise SetValidationError("; ".join(errors))
    return kept_modules, kept_features


def within(items: Sequence[str], item: str) -> bool:
    """Whether ``item`` is in a list of module items: itself, through its whole
    module, or through a wildcard of its type or service."""
    if item in items:
        return True
    parsed = parse_item(item)
    if parsed.kind == "scope":
        if parsed.module == ANY:
            return False  # only itself holds every module's items
        return scope_within(items, parsed.type, parsed.module, parsed.name)
    if parsed.kind == "action":
        if parsed.service == ANY or f"{ANY}:{ANY}" in items:
            return f"{ANY}:{ANY}" in items
        if (
            parsed.action != f"{parsed.service}:{ANY}"
            and f"{parsed.service}:{ANY}" in items
        ):
            return True
        return any(
            _is_module(other) and _service_of(other) == parsed.service
            for other in items
        )
    return False


def scope_within(items: Sequence[str], type_name: str, module: str, name: str) -> bool:
    """Whether one agent, app, workflow or pipeline of a module is in a list of
    module items: itself, its whole module, or a wildcard of its type. The one
    rule of IAM's decisions (``allows``) and of what a workspace lists."""
    return (
        module in items
        or f"{type_name}/{module}/{name}" in items
        or f"{type_name}/{module}/{ANY}" in items
        or f"{type_name}/{ANY}/{ANY}" in items
    )


def _is_module(item: str) -> bool:
    return "/" not in item and ":" not in item


def outside(child: ScopeSet, parent: ScopeSet | None) -> list[str]:
    """The items of ``child`` its ``parent`` does not have: a workspace's set
    must be within its org's. A part ``child`` leaves unrecorded follows the
    parent's, so it is never outside."""
    if parent is None:
        return []
    extra: list[str] = []
    if child.modules is not None and parent.modules is not None:
        extra += [m for m in child.modules if not within(parent.modules, m)]
    if child.features is not None and parent.features is not None:
        extra += [f"feature {f}" for f in child.features if f not in parent.features]
    return extra


def _intersect_items(
    a: tuple[str, ...] | None, b: tuple[str, ...] | None
) -> tuple[str, ...] | None:
    if a is None:
        return b
    if b is None:
        return a
    kept = {item for item in b if within(a, item)}
    kept |= {item for item in a if within(b, item)}
    # A whole module on one side, a wildcard of every module on the other: that
    # module's part of it.
    for one, other in ((a, b), (b, a)):
        for module in (m for m in one if _is_module(m)):
            for item in other:
                parsed = parse_item(item)
                if parsed.kind == "scope" and parsed.module == ANY:
                    kept.add(f"{parsed.type}/{module}/{ANY}")
                elif parsed.kind == "action" and parsed.service == ANY:
                    service = _service_of(module)
                    if service is not None:
                        kept.add(f"{service}:{ANY}")
    # An item its whole module also holds adds nothing.
    return tuple(
        sorted(
            item
            for item in kept
            if _is_module(item) or not within(sorted(kept - {item}), item)
        )
    )


def intersect(org_set: ScopeSet | None, workspace_set: ScopeSet | None) -> ScopeSet:
    """The effective set of a workspace (or of an org, ``workspace_set`` None)."""
    org = org_set.org if org_set else workspace_set.org if workspace_set else NONE
    workspace = workspace_set.workspace if workspace_set else NONE
    features: tuple[str, ...] | None
    a = org_set.features if org_set else None
    b = workspace_set.features if workspace_set else None
    if a is None or b is None:
        features = a if b is None else b
    else:
        features = tuple(sorted(set(a) & set(b)))
    return ScopeSet(
        org,
        workspace,
        _intersect_items(
            org_set.modules if org_set else None,
            workspace_set.modules if workspace_set else None,
        ),
        features,
    )


# -- decisions -------------------------------------------------------------------


def bounded(catalogs: CatalogRegistry, service: str, type_name: str) -> bool:
    """Whether a set bounds the resources of the type: module scopes and features."""
    if (service, type_name) == FEATURE_TYPE:
        return True
    catalog = catalogs.get(service)
    declared = catalog.resource_type(type_name) if catalog is not None else None
    return declared is not None and declared.module_scope


def allows(
    scope_set: ScopeSet,
    catalogs: CatalogRegistry,
    action: str,
    name: ResourceName,
) -> bool:
    """Whether ``scope_set`` has ``action`` on ``name`` (a bounded resource)."""
    if (name.service, name.type) == FEATURE_TYPE:
        if scope_set.features is None:
            return True
        segments = name.segments
        return len(segments) == 1 and segments[0] in scope_set.features
    if scope_set.modules is None:
        return True
    items = scope_set.modules
    if name.service == MODULE_SERVICE:
        segments = name.segments
        if len(segments) < 2:
            return False
        return scope_within(items, name.type, segments[0], "/".join(segments[1:]))
    catalog = catalogs.get(name.service)
    owner = catalog.module if catalog is not None else None
    if not owner:
        return False
    return (
        owner in items
        or action in items
        or f"{name.service}:{ANY}" in items
        or f"{ANY}:{ANY}" in items
    )


def held_patterns(
    scope_set: ScopeSet,
    catalogs: CatalogRegistry,
    action: str,
    scope: str,
) -> tuple[str, ...]:
    """What ``scope_set`` lets anyone hold of ``action`` at ``scope``, as
    resource patterns: ``*`` for an action it does not bound. The grant check
    (``grants.Holdings``) takes them as one more side."""
    service, _, action_name = action.partition(":")
    catalog = catalogs.get(service)
    spec = catalog.action(action_name) if catalog is not None else None
    if spec is None:
        return ("*",)
    types = [t for t in spec.resource_types if bounded(catalogs, service, t)]
    if not types:
        return ("*",)
    patterns: list[str] = []
    for type_name in types:
        if (service, type_name) == FEATURE_TYPE:
            if scope_set.features is None:
                patterns.append(f"{scope}:{service}:{type_name}/*")
            else:
                patterns += [
                    f"{scope}:{service}:{type_name}/{encode_segment(key)}"
                    for key in scope_set.features
                ]
            continue
        if scope_set.modules is None:
            patterns.append(f"{scope}:{service}:{type_name}/*")
            continue
        for item in scope_set.modules:
            parsed = parse_item(item)
            if service == MODULE_SERVICE:
                if parsed.kind == "module":
                    patterns.append(
                        f"{scope}:{service}:{type_name}/{encode_segment(parsed.module)}/*"
                    )
                elif parsed.kind == "scope" and parsed.type == type_name:
                    if parsed.module == ANY:
                        patterns.append(f"{scope}:{service}:{type_name}/*")
                        continue
                    last = "*" if parsed.name == ANY else encode_segment(parsed.name)
                    patterns.append(
                        f"{scope}:{service}:{type_name}/"
                        f"{encode_segment(parsed.module)}/{last}"
                    )
            elif (
                parsed.kind == "module"
                and catalog is not None
                and catalog.module == parsed.module
            ) or (
                parsed.kind == "action"
                and parsed.action in (action, f"{service}:{ANY}", f"{ANY}:{ANY}")
            ):
                patterns.append(f"{scope}:{service}:{type_name}/*")
    return tuple(dict.fromkeys(patterns))


# -- names ---------------------------------------------------------------------------


def read_resource(org: str, workspace: str = NONE) -> str:
    """Where a set is read (``iam:GetSet``): at its own scope, so the admins of
    an org read the org's and those of a workspace the workspace's."""
    own = workspace if workspace != NONE else org
    return resource_name("iam", "set", own, org=org, workspace=workspace)


def write_resource(org: str, workspace: str = NONE) -> str:
    """Where a set is written (``iam:PutSet``): an org's at
    ``abi:%2A:%2A:iam:set/<org>``, which only grants for every org reach (the
    platform admin's); a workspace's at ``abi:<org>:%2A:iam:set/<ws>``, which an
    org-wide role reaches (the org's owners and admins) and a role at the
    workspace does not."""
    from naas_abi_core.services.iam.names import ALL_ORGS, ALL_WORKSPACES

    if workspace == NONE:
        return resource_name("iam", "set", org, org=ALL_ORGS, workspace=ALL_WORKSPACES)
    return resource_name("iam", "set", workspace, org=org, workspace=ALL_WORKSPACES)
