"""What a workspace offers: "<W> access" as an allow-list (ADR
``20261120_access_levels_and_groups``, decision 3).

"<W> access" names the instances its workspace offers, one by one: its client
module's agents and apps, the shared modules it offers (every item of each, as
``<module>/*``), its workflows and pipelines, and its features. It is W's ceiling:
nothing below it, nor any grant it bounds, reaches what it does not name. A module
added to the platform is in no workspace's offer until someone adds it there; no
``module:agent/*`` and no Deny list of other modules' agents.

The document is written in sections, one statement each, by ``sid``:

| sid | Actions | Resources |
|---|---|---|
| ``OfferAgents`` | ``module:UseAgent`` | ``${scope}/module:agent/<module>/<name or *>`` |
| ``OfferApps`` | ``module:OpenApp`` | ``${scope}/module:app/...`` |
| ``OfferWorkflows`` | ``module:RunWorkflow``, ``module:ReadWorkflowRuns`` | ``${scope}/module:workflow/...`` |
| ``OfferPipelines`` | ``module:RunPipeline``, ``module:ReadPipelineRuns`` | ``${scope}/module:pipeline/...`` |
| ``OfferFeatures`` | ``nexus:UseFeature`` | ``${scope}/nexus:feature/<key>`` |

A section naming more than ``policy.MAX_PATTERNS`` items (IAM's limit for one
statement) is written in parts: ``OfferAgents``, ``OfferAgents2``, ``OfferAgents3``...

An offer of nothing is ``container_defaults.nothing_document`` (an Allow no name
matches). ``offer_of`` reads the sections back: what the Features and Agents/Apps
settings change, and what the access migration (S4) writes from a ceiling's old
Allows and Denies. Statements in no section (a ceiling of an older version, a
statement a person wrote) are kept as they are by ``with_offer``.

Where the offer comes from (``offer_from_seed``): the workspace's configuration
seed (``nexus_config.organizations[].workspaces[]`` or its stored ``catalog_seed``):
``agents`` (``module AgentClass`` refs, resolved to their module scope), ``apps``
(app ids), ``modules`` (shared modules offered whole) and, from the deployment,
the enabled features. Pure: no IAM, no database.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field, replace
from typing import Any
from urllib.parse import unquote

from naas_abi.apps.nexus.apps.api.app.services.iam.names import scoped_resource
from naas_abi_core.services.iam import module_scopes
from naas_abi_core.services.iam.names import PLATFORM
from naas_abi_core.services.iam.policy import MAX_PATTERNS, POLICY_VERSION

USE_FEATURE = "nexus:UseFeature"
WHOLE_MODULE = "*"
SCOPE = "${scope}/"

# Each section: its sid, the module-scope type it lists, and its actions.
SECTIONS: dict[str, tuple[str, tuple[str, ...]]] = {
    "agents": ("OfferAgents", (module_scopes.USE_ACTION[module_scopes.AGENT],)),
    "apps": ("OfferApps", (module_scopes.USE_ACTION[module_scopes.APP],)),
    "workflows": (
        "OfferWorkflows",
        (
            module_scopes.USE_ACTION[module_scopes.WORKFLOW],
            module_scopes.RUNS_ACTION[module_scopes.WORKFLOW],
        ),
    ),
    "pipelines": (
        "OfferPipelines",
        (
            module_scopes.USE_ACTION[module_scopes.PIPELINE],
            module_scopes.RUNS_ACTION[module_scopes.PIPELINE],
        ),
    ),
}
TYPE_OF_KIND = {
    "agents": module_scopes.AGENT,
    "apps": module_scopes.APP,
    "workflows": module_scopes.WORKFLOW,
    "pipelines": module_scopes.PIPELINE,
}
KIND_OF_TYPE = {type_name: kind for kind, type_name in TYPE_OF_KIND.items()}
FEATURES_SID = "OfferFeatures"
OFFER_SIDS = frozenset({*(sid for sid, _ in SECTIONS.values()), FEATURES_SID})

Item = tuple[str, str]  # (module, name); name ``*`` is the whole module


def offer_section(sid: Any) -> str | None:
    """The section's sid ``sid`` is written under: the section's own, or one of its
    parts (``OfferAgents2``...); None for a statement in no section."""
    if not isinstance(sid, str):
        return None
    base = sid.rstrip("0123456789")
    if base not in OFFER_SIDS:
        return None
    part = sid[len(base) :]
    if part and (part.startswith("0") or int(part) < 2):
        return None
    return base


def _parts(sid: str, actions: list[str], resources: list[str]) -> list[dict[str, Any]]:
    return [
        {
            "sid": f"{sid}{start // MAX_PATTERNS + 1}" if start else sid,
            "effect": "Allow",
            "actions": actions,
            "resources": resources[start : start + MAX_PATTERNS],
        }
        for start in range(0, len(resources), MAX_PATTERNS)
    ]


@dataclass(frozen=True)
class Offer:
    """The instances and features a workspace offers."""

    agents: frozenset[Item] = field(default_factory=frozenset)
    apps: frozenset[Item] = field(default_factory=frozenset)
    workflows: frozenset[Item] = field(default_factory=frozenset)
    pipelines: frozenset[Item] = field(default_factory=frozenset)
    features: frozenset[str] = field(default_factory=frozenset)

    @classmethod
    def of(
        cls,
        *,
        agents: Iterable[Item] = (),
        apps: Iterable[Item] = (),
        workflows: Iterable[Item] = (),
        pipelines: Iterable[Item] = (),
        modules: Iterable[str] = (),
        features: Iterable[str] = (),
    ) -> Offer:
        """An offer; each of ``modules`` adds every agent, app, workflow and
        pipeline of that module (a shared module offered whole)."""
        whole = [(str(m), WHOLE_MODULE) for m in modules if str(m).strip()]
        return cls(
            agents=frozenset([*agents, *whole]),
            apps=frozenset([*apps, *whole]),
            workflows=frozenset([*workflows, *whole]),
            pipelines=frozenset([*pipelines, *whole]),
            features=frozenset(features),
        )

    def items(self, kind: str) -> frozenset[Item]:
        return getattr(self, kind)

    def is_empty(self) -> bool:
        return not (any(self.items(kind) for kind in SECTIONS) or self.features)

    def merged(self, other: Offer) -> Offer:
        return Offer(
            **{kind: self.items(kind) | other.items(kind) for kind in SECTIONS},
            features=self.features | other.features,
        )

    def without(self, other: Offer) -> Offer:
        return Offer(
            **{kind: self.items(kind) - other.items(kind) for kind in SECTIONS},
            features=self.features - other.features,
        )

    def offers(self, kind: str, module: str, name: str) -> bool:
        """Whether the item is offered, by name or with its whole module."""
        items = self.items(kind)
        return (module, name) in items or (module, WHOLE_MODULE) in items


def item_pattern(kind: str, module: str, name: str) -> str:
    """``${scope}/module:<type>/<module>/<name>`` (``<module>/*`` for the whole
    module), as a policy attached at a workspace names it."""
    type_name = TYPE_OF_KIND[kind]
    if name == WHOLE_MODULE:
        named = module_scopes.scope_resource(type_name, module, "-", container=PLATFORM)
        return SCOPE + named.removeprefix(PLATFORM).rsplit("/", 1)[0] + "/*"
    named = module_scopes.scope_resource(type_name, module, name, container=PLATFORM)
    return SCOPE + named.removeprefix(PLATFORM)


def _item_of(kind: str, pattern: str) -> Item | None:
    prefix = f"{SCOPE}{module_scopes.SERVICE}:{TYPE_OF_KIND[kind]}/"
    if not pattern.startswith(prefix):
        return None
    module, _, name = pattern[len(prefix) :].partition("/")
    if not module or not name or "/" in name:
        return None
    return unquote(module), (WHOLE_MODULE if name == "*" else unquote(name))


def _feature_of(pattern: str) -> str | None:
    prefix = scoped_resource("feature", "-").rsplit("/", 1)[0] + "/"
    if not pattern.startswith(prefix) or "*" in pattern:
        return None
    return unquote(pattern[len(prefix) :])


def offer_statements(offer: Offer) -> list[dict[str, Any]]:
    statements: list[dict[str, Any]] = []
    for kind, (sid, actions) in SECTIONS.items():
        statements += _parts(
            sid,
            [f"{module_scopes.SERVICE}:{a}" for a in actions],
            [item_pattern(kind, m, n) for m, n in sorted(offer.items(kind))],
        )
    statements += _parts(
        FEATURES_SID,
        [USE_FEATURE],
        [scoped_resource("feature", k) for k in sorted(offer.features)],
    )
    return statements


def offer_document(offer: Offer) -> dict[str, Any]:
    """ "<W> access" for ``offer``: its sections, or an Allow no name matches when
    it offers nothing. A section past ``policy.MAX_PATTERNS`` items is written in
    parts; IAM refuses a document of more than ``policy.MAX_STATEMENTS`` statements."""
    from naas_abi.apps.nexus.apps.api.app.services.iam.container_defaults import (
        nothing_document,
    )

    if offer.is_empty():
        return nothing_document()
    return {"version": POLICY_VERSION, "statements": offer_statements(offer)}


def _statement_parts(statement: Any) -> tuple[str | None, str, list[str], list[str]]:
    if isinstance(statement, Mapping):
        return (
            statement.get("sid"),
            str(statement.get("effect")),
            list(statement.get("actions") or []),
            list(statement.get("resources") or []),
        )
    return (
        statement.sid,
        str(statement.effect),
        list(statement.actions),
        list(statement.resources),
    )


def _statements_of(document: Any) -> list[Any]:
    if isinstance(document, Mapping):
        return list(document.get("statements") or [])
    return list(getattr(document, "statements", ()) or ())


def offer_of(document: Any) -> Offer:
    """The offer a document's sections hold (a dict or a ``PolicyDocument``);
    statements in no section are not read."""
    found: dict[str, set[Any]] = {kind: set() for kind in SECTIONS}
    features: set[str] = set()
    sid_kind = {sid: kind for kind, (sid, _a) in SECTIONS.items()}
    for statement in _statements_of(document):
        sid, effect, _actions, resources = _statement_parts(statement)
        section = offer_section(sid)
        if effect != "Allow" or section is None:
            continue
        if section == FEATURES_SID:
            features.update(f for r in resources if (f := _feature_of(r)) is not None)
            continue
        kind = sid_kind[section]
        found[kind].update(i for r in resources if (i := _item_of(kind, r)) is not None)
    return Offer(
        **{kind: frozenset(items) for kind, items in found.items()},
        features=frozenset(features),
    )


def with_offer(document: Any, offer: Offer) -> dict[str, Any]:
    """``document`` with its sections replaced by ``offer``'s; every other
    statement kept as it is (the ``Nothing`` placeholder dropped once something is
    offered)."""
    from naas_abi.apps.nexus.apps.api.app.services.iam.container_defaults import (
        NOTHING_SID,
        nothing_document,
    )

    kept: list[dict[str, Any]] = []
    for statement in _statements_of(document):
        sid, effect, actions, resources = _statement_parts(statement)
        if offer_section(sid) is not None or sid == NOTHING_SID:
            continue
        kept.append(
            {
                **({"sid": sid} if sid else {}),
                "effect": effect,
                "actions": actions,
                "resources": resources,
            }
        )
    statements = [*kept, *offer_statements(offer)]
    if not statements:
        return nothing_document()
    return {"version": POLICY_VERSION, "statements": statements}


def changed(document: Any, offer: Offer) -> bool:
    """Whether writing ``offer`` into ``document`` changes what it offers."""
    return offer_of(document) != offer or (
        not offer.is_empty()
        and any(_statement_parts(s)[0] == "Nothing" for s in _statements_of(document))
    )


# -- from the configuration -------------------------------------------------------

AgentResolver = Callable[[str], Item | None]


def offer_from_seed(
    *,
    agents: Iterable[str] | None = (),
    apps: Iterable[str] | None = (),
    modules: Iterable[str] | None = (),
    features: Iterable[str] = (),
    resolve_agent: AgentResolver,
    resolve_app: Callable[[str], Item | None] | None = None,
) -> tuple[Offer, list[str]]:
    """The offer of a workspace's seed: ``agents`` (``module AgentClass`` refs,
    each resolved to its ``(module, name)`` scope by ``resolve_agent``), ``apps``
    (app ids, ``resolve_app``: ``apps.scopes.app_scope`` by default), ``modules``
    offered whole, and ``features``. Also the refs that resolved to nothing (an
    agent whose module the engine did not load): left out, named."""
    if resolve_app is None:
        from naas_abi.apps.nexus.apps.api.app.services.apps.scopes import app_scope

        def resolve_app(app_id: str) -> Item | None:
            scope = app_scope(app_id)
            return (scope.module, scope.name) if scope is not None else None

    unresolved: list[str] = []
    agent_items: list[Item] = []
    for ref in agents or ():
        item = resolve_agent(str(ref))
        if item is None:
            unresolved.append(str(ref))
        else:
            agent_items.append(item)
    app_items: list[Item] = []
    for app_id in apps or ():
        item = resolve_app(str(app_id))
        if item is None:
            unresolved.append(str(app_id))
        else:
            app_items.append(item)
    offer = Offer.of(
        agents=agent_items,
        apps=app_items,
        modules=[m for m in modules or () if str(m).strip()],
        features=features,
    )
    return offer, unresolved


def with_features(offer: Offer, features: Iterable[str]) -> Offer:
    return replace(offer, features=frozenset(features))


__all__ = [
    "FEATURES_SID",
    "OFFER_SIDS",
    "Offer",
    "SECTIONS",
    "WHOLE_MODULE",
    "changed",
    "item_pattern",
    "offer_document",
    "offer_from_seed",
    "offer_of",
    "offer_section",
    "with_features",
    "with_offer",
]


# -- the seed of a workspace ------------------------------------------------------


def engine_agent_resolver() -> AgentResolver:
    """``module AgentClass`` to its ``(module, name)`` scope over the engine's agent
    class registry (as the roster resolves it); a ref the engine did not load
    resolves to nothing (an Allow under a guessed name would allow nothing)."""
    from naas_abi.apps.nexus.apps.api.app.core.workspace_catalog_seed import resolve_agent_ref
    from naas_abi.apps.nexus.apps.api.app.services.agents.scopes import class_scope

    try:
        from naas_abi.apps.nexus.apps.api.app.services.agents.adapters.primary import (
            agents__primary_adapter__FastAPI as agents_api,
        )

        classes = agents_api._get_agent_class_registry()
        module_of = agents_api.agent_class_modules()
    except Exception:  # noqa: BLE001 - no engine loaded: nothing resolves
        classes, module_of = {}, {}

    def resolve(ref: str) -> Item | None:
        class_name = resolve_agent_ref(ref, classes)
        if class_name is None:
            return None
        scope = class_scope(class_name, classes.get(class_name), module_of)
        return (scope.module, scope.name) if scope is not None else None

    return resolve


def engine_default_agent() -> str | None:
    """The engine's ``default_agent`` ref (``module AgentClass``), if any."""
    try:
        from naas_abi import ABIModule

        found = ABIModule.get_instance().engine.configuration.default_agent
    except Exception:  # noqa: BLE001 - no engine: none
        return None
    return str(found).strip() or None if found else None


def seeded_offer(
    slug: str | None,
    catalog_seed: dict[str, Any] | None,
    *,
    features: Iterable[str],
    resolve_agent: AgentResolver | None = None,
) -> tuple[Offer, list[str]] | None:
    """The offer a workspace's seed makes (its stored ``catalog_seed``, else its
    configuration entry): its agents, apps and shared modules, and ``features``
    (the deployment's enabled ones); None for a workspace with no seed."""
    from naas_abi.apps.nexus.apps.api.app.core.workspace_seed_catalog import (
        effective_seed_agents,
        effective_seed_apps,
        effective_seed_default_agent,
        effective_seed_modules,
        has_seed,
    )

    if not has_seed(slug, catalog_seed):
        return None
    # Its default agent is one of its agents: the seed's, else (a seed naming no
    # agent list) the engine's.
    agents = list(effective_seed_agents(slug, catalog_seed) or ())
    default = effective_seed_default_agent(slug, catalog_seed)
    if default is None and effective_seed_agents(slug, catalog_seed) is None:
        default = engine_default_agent()
    if default and default not in agents:
        agents.append(default)
    return offer_from_seed(
        agents=agents,
        apps=sorted(effective_seed_apps(slug, catalog_seed)),
        modules=sorted(effective_seed_modules(slug, catalog_seed)),
        features=features,
        resolve_agent=resolve_agent or engine_agent_resolver(),
    )


def in_offer_form(document: Any) -> bool:
    """Whether ``document`` is an allow-list this module wrote: only offer sections
    (or the ``Nothing`` placeholder). A ceiling of an older version (a wildcard and
    its Denies, the sets' move's) is not: the access migration (S4) converts it."""
    from naas_abi.apps.nexus.apps.api.app.services.iam.container_defaults import NOTHING_SID

    statements = _statements_of(document)
    return bool(statements) and all(
        (offer_section(sid) is not None or sid == NOTHING_SID) and effect == "Allow"
        for sid, effect, _actions, _resources in map(_statement_parts, statements)
    )


def instances_only(offer: Offer) -> Offer:
    """``offer`` without its features: what a re-seed adds (the features are the
    Features setting's)."""
    return replace(offer, features=frozenset())
