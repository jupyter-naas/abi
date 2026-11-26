"""How far people go with a feature or a core service in a workspace: its access level.

Two kinds of groups of actions, kept apart:

* a **Nexus feature** (``feature:<key>``): the ``nexus:`` actions the catalog ties to the
  feature (``feature=`` in ``catalog/``), on the types placed in a workspace;
* a **core service** (``service:<service>``): the actions of an engine service (the triple
  store's graphs, object storage, vector store, secrets, datasets, documents...), on its types
  placed in a workspace.

Each action has a level (``list``, ``read``, ``write``, ``admin``); a group's access level is
one of ``none``, ``read`` (``list`` and ``read``), ``write``, ``admin``, those its actions have.

A policy holds the levels in sections of their own, apart from the offer's
(``workspace_offer.with_offer`` keeps them as they are):

* in "<W> access", a bound, **caps** (``AccessLevelCap``, Deny): the actions above the level,
  denied to everyone in the workspace, admins included (a bound's Denies apply to its members;
  its Allows do not reach the built-in roles). No statement: no cap (``admin``);
* in another policy of the workspace, **grants** (``AccessLevelGrant``, Allow): the actions up to
  the level, granted to whoever holds it, within the offer. No statement: ``none``.

Pure (the catalogs are read at import): ``FeatureAccessService`` reads and writes them.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Literal

from naas_abi.apps.nexus.apps.api.app.services.iam.catalog import (
    NEXUS_ACTIONS,
    NEXUS_CATALOG,
    TYPES_BY_NAME,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.names import scoped_resource
from naas_abi_core.services.cache.iam_catalog import CATALOG as CACHE
from naas_abi_core.services.dataset.iam_catalog import CATALOG as DATASET
from naas_abi_core.services.document.iam_catalog import CATALOG as DOCUMENT
from naas_abi_core.services.event.iam_catalog import CATALOG as EVENT
from naas_abi_core.services.iam.catalog import ActionCatalog
from naas_abi_core.services.keyvalue.iam_catalog import CATALOG as KEYVALUE
from naas_abi_core.services.object_storage.iam_catalog import CATALOG as OBJECT_STORAGE
from naas_abi_core.services.secret.iam_catalog import CATALOG as SECRET
from naas_abi_core.services.triple_store.iam_catalog import CATALOG as TRIPLE_STORE
from naas_abi_core.services.vector_store.iam_catalog import CATALOG as VECTOR_STORE

Level = Literal["none", "read", "write", "admin"]
Mode = Literal["cap", "grant"]
Kind = Literal["feature", "service"]

LEVELS: tuple[Level, ...] = ("none", "read", "write", "admin")
_RANK: dict[str, int] = {"none": -1, "list": 0, "read": 0, "write": 1, "admin": 2}

CAP_SID = "AccessLevelCap"
GRANT_SID = "AccessLevelGrant"
SID_OF_MODE: dict[str, str] = {"cap": CAP_SID, "grant": GRANT_SID}

# The engine services whose resources a workspace holds, in the order the page lists them.
CORE_CATALOGS: tuple[ActionCatalog, ...] = (
    TRIPLE_STORE,
    OBJECT_STORAGE,
    VECTOR_STORE,
    DATASET,
    DOCUMENT,
    SECRET,
    KEYVALUE,
    CACHE,
    EVENT,
)
CORE_LABELS: dict[str, str] = {
    "triple_store": "Knowledge graph (triple store)",
    "object_storage": "Object storage",
    "vector_store": "Vector store",
    "dataset": "Datasets",
    "document": "Documents",
    "secret": "Secrets",
    "keyvalue": "Key-value store",
    "cache": "Cache",
    "event": "Events",
}


@dataclass(frozen=True)
class LevelAction:
    action: str  # qualified: ``nexus:CreateView``, ``triple_store:InsertTriples``
    level: str  # its catalog level: list, read, write, admin
    resource: str  # the pattern naming its resources in the workspace


@dataclass(frozen=True)
class LevelGroup:
    key: str  # ``feature:<key>`` or ``service:<service>``
    kind: Kind
    name: str  # the feature key or the service name
    label: str
    actions: tuple[LevelAction, ...]

    def choices(self, mode: Mode) -> list[Level]:
        """The levels it may take: those its actions have (``read`` for ``list`` too),
        and ``none``."""
        ranks = {_RANK[a.level] for a in self.actions}
        found: list[Level] = ["none"]
        found += [level for level in ("read", "write", "admin") if _RANK[level] in ranks]
        return found

    def by_level(self) -> dict[str, list[str]]:
        """Its actions by the level that brings them (``read``: list and read)."""
        out: dict[str, list[str]] = {"read": [], "write": [], "admin": []}
        for a in self.actions:
            out["read" if _RANK[a.level] == 0 else a.level].append(a.action)
        return {level: sorted(names) for level, names in out.items() if names}

    def resources(self) -> list[str]:
        return sorted({a.resource for a in self.actions})


def _every(type_name: str) -> str:
    """``${scope}/nexus:<type>/*``: every resource of a type in the workspace."""
    return scoped_resource(type_name, "-").rsplit("/", 1)[0] + "/*"


USE_FEATURE = "nexus:UseFeature"


def _feature_groups() -> list[LevelGroup]:
    """Every feature: its gate (``UseFeature`` on the feature, at the read level, so ``none``
    denies the feature itself), and the ``nexus:`` actions the catalog ties to it."""
    from typing import get_args

    from naas_abi.apps.nexus.apps.api.app.core.config import FeatureKey
    from naas_abi.apps.nexus.apps.api.app.services.feature_access.service import feature_label

    found: dict[str, list[LevelAction]] = {
        key: [LevelAction(USE_FEATURE, "list", f"${{scope}}/nexus:feature/{key}")]
        for key in get_args(FeatureKey)
    }
    for a in NEXUS_ACTIONS:
        if a.feature is None:
            continue
        type_name = a.spec.resource_types[0]
        rtype = TYPES_BY_NAME.get(type_name)
        # A workspace caps what is in it: not a platform type, a container or a type only
        # a policy grants (the offer's own sections name those).
        if rtype is None or rtype.placement != "placed" or rtype.container or rtype.policy_only:
            continue
        found.setdefault(a.feature, []).append(
            LevelAction(NEXUS_CATALOG.qualified(a.spec.name), a.spec.level, _every(type_name))
        )
    return [
        LevelGroup(f"feature:{key}", "feature", key, feature_label(key), tuple(actions))
        for key, actions in sorted(found.items())
    ]


def _service_groups() -> list[LevelGroup]:
    groups: list[LevelGroup] = []
    for catalog in CORE_CATALOGS:
        placed = {
            t.name for t in catalog.resource_types if t.placement == "placed" and not t.container
        }
        actions = tuple(
            LevelAction(catalog.qualified(a.name), a.level, f"${{scope}}/{catalog.service}:*")
            for a in catalog.actions
            if any(t in placed for t in a.resource_types)
        )
        if actions:
            groups.append(
                LevelGroup(
                    f"service:{catalog.service}",
                    "service",
                    catalog.service,
                    CORE_LABELS.get(catalog.service, catalog.service),
                    actions,
                )
            )
    return groups


_GROUPS: list[LevelGroup] | None = None


def groups(kind: Kind | None = None) -> list[LevelGroup]:
    """The Nexus features' groups, then the core services'."""
    global _GROUPS
    if _GROUPS is None:
        _GROUPS = [*_feature_groups(), *_service_groups()]
    return [g for g in _GROUPS if kind is None or g.kind == kind]


def group(key: str) -> LevelGroup | None:
    return next((g for g in groups() if g.key == key), None)


def _groups_of_action() -> dict[tuple[str, str], LevelGroup]:
    """(action, the pattern naming its resources) -> its group: ``UseFeature`` is every
    feature's, told apart by the feature it names."""
    return {(a.action, a.resource): g for g in groups() for a in g.actions}


def _section(sid: Any) -> str | None:
    if not isinstance(sid, str):
        return None
    base = sid.rstrip("0123456789")
    return base if base in (CAP_SID, GRANT_SID) else None


def _statements(document: Any) -> list[Mapping[str, Any]]:
    raw = (
        document.get("statements")
        if isinstance(document, Mapping)
        else getattr(document, "statements", ())
    )
    out: list[Mapping[str, Any]] = []
    for s in raw or ():
        if isinstance(s, Mapping):
            out.append(s)
        else:
            out.append(
                {
                    "sid": s.sid,
                    "effect": str(s.effect),
                    "actions": list(s.actions),
                    "resources": list(s.resources),
                }
            )
    return out


def levels_of(document: Any, mode: Mode) -> dict[str, Level]:
    """Each group's level in ``document``, as ``mode``'s section holds it: a cap (no
    statement: ``admin``, the highest) or a grant (no statement: ``none``)."""
    sid = SID_OF_MODE[mode]
    effect = "Deny" if mode == "cap" else "Allow"
    named: dict[str, set[str]] = {}
    of = _groups_of_action()
    for s in _statements(document):
        if _section(s.get("sid")) != sid or str(s.get("effect")) != effect:
            continue
        for action in s.get("actions") or ():
            for resource in s.get("resources") or ():
                g = of.get((action, resource))
                if g is not None:
                    named.setdefault(g.key, set()).add(action)
    out: dict[str, Level] = {}
    for g in groups():
        choices = g.choices(mode)
        named_here = named.get(g.key, set())
        if mode == "cap":
            if not named_here:
                out[g.key] = choices[-1]
                continue
            lowest = min(_RANK[a.level] for a in g.actions if a.action in named_here)
            out[g.key] = max(
                (c for c in choices if _RANK[c] < lowest), key=lambda c: _RANK[c], default="none"
            )
        else:
            level: Level = "none"
            for c in choices[1:]:
                if all(a.action in named_here for a in g.actions if _RANK[a.level] <= _RANK[c]):
                    level = c
            out[g.key] = level
    return out


def statements(levels: Mapping[str, str], mode: Mode) -> list[dict[str, Any]]:
    """``mode``'s section for ``levels`` (group key -> level), one statement a group."""
    sid = SID_OF_MODE[mode]
    found: list[dict[str, Any]] = []
    for g in groups():
        level = levels.get(g.key)
        if level is None:
            continue
        rank = _RANK[level]
        if mode == "cap":
            actions = sorted({a.action for a in g.actions if _RANK[a.level] > rank})
        else:
            actions = sorted({a.action for a in g.actions if _RANK[a.level] <= rank})
        if not actions:
            continue
        number = len(found) + 1
        found.append(
            {
                "sid": sid if number == 1 else f"{sid}{number}",
                "effect": "Deny" if mode == "cap" else "Allow",
                "actions": actions,
                "resources": g.resources(),
            }
        )
    return found


def with_levels(document: Any, mode: Mode, levels: Mapping[str, str]) -> dict[str, Any]:
    """``document`` with ``mode``'s section replaced by ``levels``' (every group's level,
    as ``levels_of`` answers them); every other statement kept as it is."""
    sid = SID_OF_MODE[mode]
    kept = [
        {
            **({"sid": s["sid"]} if s.get("sid") else {}),
            "effect": str(s.get("effect")),
            "actions": list(s.get("actions") or []),
            "resources": list(s.get("resources") or []),
        }
        for s in _statements(document)
        if _section(s.get("sid")) != sid
    ]
    version = (
        document.get("version")
        if isinstance(document, Mapping)
        else getattr(document, "version", None)
    )
    return {"version": version, "statements": [*kept, *statements(levels, mode)]}


def check_changes(changes: Mapping[str, str], mode: Mode) -> None:
    """A change names a group and one of its levels (``ValueError`` otherwise)."""
    if not changes:
        raise ValueError("No change")
    for key, level in changes.items():
        g = group(key)
        if g is None:
            raise ValueError(f"{key!r} is not a feature or a core service with access levels")
        if level not in g.choices(mode):
            raise ValueError(f"{g.label} has no {level!r} level")


def rows(
    document: Any, mode: Mode, kind: Kind, keys: Iterable[str] | None = None
) -> list[dict[str, Any]]:
    """The page's rows: each group of ``kind`` with its level in ``document``."""
    levels = levels_of(document, mode)
    wanted = set(keys) if keys is not None else None
    return [
        {
            "key": g.key,
            "kind": g.kind,
            "name": g.name,
            "label": g.label,
            "level": levels[g.key],
            "choices": g.choices(mode),
            "actions": g.by_level(),
        }
        for g in groups(kind)
        if wanted is None or g.name in wanted
    ]


__all__ = [
    "CAP_SID",
    "GRANT_SID",
    "LEVELS",
    "LevelGroup",
    "check_changes",
    "group",
    "groups",
    "levels_of",
    "rows",
    "statements",
    "with_levels",
]
