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
| ``OfferSearchSources`` | ``nexus:UseSearchSource`` | ``${scope}/nexus:search_source/<id>`` |
| ``OfferOntologies`` | ``nexus:UseOntology`` | ``${scope}/nexus:ontology_file/<ref>`` |

A section naming more than ``policy.MAX_PATTERNS`` items (IAM's limit for one
statement) is written in parts: ``OfferAgents``, ``OfferAgents2``, ``OfferAgents3``...

The **given** sections name files outside W, absolute names only, which IAM gives to
W's people within their level (``given_files``, ADR
``20261125_offer_gives_outside_resources``): ``GivenOrgFiles``, ``GivenPlatformFiles``
and ``GivenSystemFiles``, each a mode, written as its Nexus half and its object storage
half (``<sid>2``). And the graphs W is given and what it closes of its own
(``given_graphs``): ``GivenGraphs``, ``GivenGraphsWrite``, ``GivenGraphsAll`` (Allows on
absolute names) and ``OfferGraphsDeny`` (W's only Denies, within ``${scope}``).

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

from naas_abi.apps.nexus.apps.api.app.services.iam import given_files, given_graphs
from naas_abi.apps.nexus.apps.api.app.services.iam.given_files import Mode
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
USE_SEARCH_SOURCE = "nexus:UseSearchSource"
SEARCH_SOURCES_SID = "OfferSearchSources"
USE_ONTOLOGY = "nexus:UseOntology"
ONTOLOGIES_SID = "OfferOntologies"
# The sections naming Nexus ids in the workspace (``${scope}/nexus:<type>/<id>``), by
# the ``Offer`` field they fill: its sid, its action, the resource type.
ID_SECTIONS: dict[str, tuple[str, str, str]] = {
    "features": (FEATURES_SID, USE_FEATURE, "feature"),
    "search_sources": (SEARCH_SOURCES_SID, USE_SEARCH_SOURCE, "search_source"),
    "ontologies": (ONTOLOGIES_SID, USE_ONTOLOGY, "ontology_file"),
}
OFFER_SIDS = frozenset(
    {
        *(sid for sid, _ in SECTIONS.values()),
        *(sid for sid, _a, _t in ID_SECTIONS.values()),
        *given_files.SIDS.values(),
        *given_graphs.SIDS,
    }
)
# The given sections' ``Offer`` fields (``given_files``).
GIVEN_FIELDS = tuple(given_files.SIDS)
# The Graphs part's ``Offer`` fields (``given_graphs``): sets of names, and a switch.
GRAPH_NAME_FIELDS = ("graphs_read", "graphs_write", "graphs_all", "graphs_closed")
GRAPH_FIELDS = (*GRAPH_NAME_FIELDS, "graphs_no_create")
_GRAPH_SID_FIELD = {
    given_graphs.READ_SID: "graphs_read",
    given_graphs.WRITE_SID: "graphs_write",
    given_graphs.ALL_SID: "graphs_all",
}

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
class OrgFiles:
    """Organization Files given in the workspace: its organization's, in ``mode``
    (``read`` or ``write``)."""

    organization: str
    mode: Mode


def _wider_org(a: OrgFiles | None, b: OrgFiles | None) -> OrgFiles | None:
    if a is None or b is None or a.organization != b.organization:
        return a or b
    mode = given_files.wider(a.mode, b.mode)
    return OrgFiles(a.organization, mode) if mode else None


def _org_without(a: OrgFiles | None, b: OrgFiles | None) -> OrgFiles | None:
    if a is None or b is None or a.organization != b.organization:
        return a
    return None if given_files.narrower_or_equal(a.mode, b.mode) else a


def _mode_without(a: Mode | None, b: Mode | None) -> Mode | None:
    return None if a is None or (b and given_files.narrower_or_equal(a, b)) else a


@dataclass(frozen=True)
class Offer:
    """The instances and features a workspace offers."""

    agents: frozenset[Item] = field(default_factory=frozenset)
    apps: frozenset[Item] = field(default_factory=frozenset)
    workflows: frozenset[Item] = field(default_factory=frozenset)
    pipelines: frozenset[Item] = field(default_factory=frozenset)
    features: frozenset[str] = field(default_factory=frozenset)
    # The sources a search reads: a feature (``chat``...) or ``web.<engine>``.
    search_sources: frozenset[str] = field(default_factory=frozenset)
    # The ontology files it offers, by ref (``module:file.ttl``, as its seed names them).
    ontologies: frozenset[str] = field(default_factory=frozenset)
    # The files it gives outside it (``given_files``): a mode each, None when off.
    org_files: OrgFiles | None = None
    platform_files: Mode | None = None
    system_files: Mode | None = None
    # The graphs it is given (``given_graphs``), by absolute name: read (list and read),
    # written, and every graph of its organization (``read_all``).
    graphs_read: frozenset[str] = field(default_factory=frozenset)
    graphs_write: frozenset[str] = field(default_factory=frozenset)
    graphs_all: frozenset[str] = field(default_factory=frozenset)
    # What it closes of its own, as Denies within ``${scope}``: creating graphs, and its
    # own graphs (by name, with ``given_graphs.NEW_GRAPH``'s) when it excludes them.
    graphs_no_create: bool = False
    graphs_closed: frozenset[str] = field(default_factory=frozenset)

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
        search_sources: Iterable[str] = (),
        ontologies: Iterable[str] = (),
        org_files: OrgFiles | None = None,
        platform_files: Mode | None = None,
        system_files: Mode | None = None,
        graphs_read: Iterable[str] = (),
        graphs_write: Iterable[str] = (),
        graphs_all: Iterable[str] = (),
        graphs_no_create: bool = False,
        graphs_closed: Iterable[str] = (),
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
            search_sources=frozenset(search_sources),
            ontologies=frozenset(ontologies),
            org_files=org_files,
            platform_files=platform_files,
            system_files=system_files,
            graphs_read=frozenset(graphs_read),
            graphs_write=frozenset(graphs_write),
            graphs_all=frozenset(graphs_all),
            graphs_no_create=graphs_no_create,
            graphs_closed=frozenset(graphs_closed),
        )

    def items(self, kind: str) -> frozenset[Item]:
        return getattr(self, kind)

    def ids(self, field_name: str) -> frozenset[str]:
        """The ids of an id section (``ID_SECTIONS``: features, search sources, ontologies)."""
        return getattr(self, field_name)

    def is_empty(self) -> bool:
        return not (
            any(self.items(kind) for kind in SECTIONS)
            or any(self.ids(f) for f in ID_SECTIONS)
            or any(getattr(self, f) for f in GIVEN_FIELDS)
            or any(getattr(self, f) for f in GRAPH_FIELDS)
        )

    def merged(self, other: Offer) -> Offer:
        """Both offers; a given section in the wider of its two modes; the graphs both
        name, and what either closes (merging never opens what one closes)."""
        return Offer(
            **{kind: self.items(kind) | other.items(kind) for kind in SECTIONS},
            **{f: self.ids(f) | other.ids(f) for f in ID_SECTIONS},
            org_files=_wider_org(self.org_files, other.org_files),
            platform_files=given_files.wider(self.platform_files, other.platform_files),
            system_files=given_files.wider(self.system_files, other.system_files),
            **{f: getattr(self, f) | getattr(other, f) for f in GRAPH_NAME_FIELDS},
            graphs_no_create=self.graphs_no_create or other.graphs_no_create,
        )

    def without(self, other: Offer) -> Offer:
        """This offer less ``other``'s; a given section goes when ``other`` gives it as
        wide."""
        return Offer(
            **{kind: self.items(kind) - other.items(kind) for kind in SECTIONS},
            **{f: self.ids(f) - other.ids(f) for f in ID_SECTIONS},
            org_files=_org_without(self.org_files, other.org_files),
            platform_files=_mode_without(self.platform_files, other.platform_files),
            system_files=_mode_without(self.system_files, other.system_files),
            **{f: getattr(self, f) - getattr(other, f) for f in GRAPH_NAME_FIELDS},
            graphs_no_create=self.graphs_no_create and not other.graphs_no_create,
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


def _id_of(type_name: str, pattern: str) -> str | None:
    prefix = scoped_resource(type_name, "-").rsplit("/", 1)[0] + "/"
    if not pattern.startswith(prefix) or "*" in pattern:
        return None
    return unquote(pattern[len(prefix) :])


def _feature_of(pattern: str) -> str | None:
    return _id_of("feature", pattern)


def offer_statements(offer: Offer) -> list[dict[str, Any]]:
    statements: list[dict[str, Any]] = []
    for kind, (sid, actions) in SECTIONS.items():
        statements += _parts(
            sid,
            [f"{module_scopes.SERVICE}:{a}" for a in actions],
            [item_pattern(kind, m, n) for m, n in sorted(offer.items(kind))],
        )
    for field_name, (sid, use, type_name) in ID_SECTIONS.items():
        statements += _parts(
            sid, [use], [scoped_resource(type_name, k) for k in sorted(offer.ids(field_name))]
        )
    if offer.org_files is not None:
        statements += given_files.statements(
            given_files.ORG_FILES, offer.org_files.mode, offer.org_files.organization
        )
    statements += given_files.statements(given_files.PLATFORM_FILES, offer.platform_files)
    statements += given_files.statements(given_files.SYSTEM_FILES, offer.system_files)
    statements += given_graphs.statements(
        offer.graphs_read,
        offer.graphs_write,
        offer.graphs_all,
        offer.graphs_no_create,
        offer.graphs_closed,
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
    ids: dict[str, set[str]] = {f: set() for f in ID_SECTIONS}
    sid_kind = {sid: kind for kind, (sid, _a) in SECTIONS.items()}
    sid_field = {sid: (f, type_name) for f, (sid, _u, type_name) in ID_SECTIONS.items()}
    # A given section's mode is read off its first statement, the Nexus half.
    given: dict[str, tuple[list[str], list[str]]] = {}
    graphs: dict[str, set[str]] = {f: set() for f in GRAPH_NAME_FIELDS}
    no_create = False
    for statement in _statements_of(document):
        sid, effect, actions, resources = _statement_parts(statement)
        section = offer_section(sid)
        if section == given_graphs.DENY_SID and effect == "Deny":
            if sid == section:
                no_create = True
            else:
                graphs["graphs_closed"].update(resources)
            continue
        if effect != "Allow" or section is None or section == given_graphs.DENY_SID:
            continue
        if section in _GRAPH_SID_FIELD:
            graphs[_GRAPH_SID_FIELD[section]].update(resources)
            continue
        if section in given_files.FIELD_OF_SID:
            if sid == section:
                given[given_files.FIELD_OF_SID[section]] = (actions, resources)
            continue
        if section in sid_field:
            f, type_name = sid_field[section]
            ids[f].update(i for r in resources if (i := _id_of(type_name, r)) is not None)
            continue
        kind = sid_kind[section]
        found[kind].update(i for r in resources if (i := _item_of(kind, r)) is not None)
    modes = {f: given_files.mode_of(f, actions) for f, (actions, _r) in given.items()}
    org_mode = modes.get(given_files.ORG_FILES)
    organization = given_files.organization_of(given.get(given_files.ORG_FILES, ((), ()))[1])
    return Offer(
        **{kind: frozenset(items) for kind, items in found.items()},
        **{f: frozenset(v) for f, v in ids.items()},
        org_files=OrgFiles(organization, org_mode) if org_mode and organization else None,
        platform_files=modes.get(given_files.PLATFORM_FILES),
        system_files=modes.get(given_files.SYSTEM_FILES),
        **{f: frozenset(v) for f, v in graphs.items()},
        graphs_no_create=no_create,
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
    "GIVEN_FIELDS",
    "GRAPH_FIELDS",
    "GRAPH_NAME_FIELDS",
    "OFFER_SIDS",
    "Offer",
    "OrgFiles",
    "SECTIONS",
    "WHOLE_MODULE",
    "changed",
    "item_pattern",
    "offer_document",
    "offer_from_seed",
    "offer_of",
    "offer_section",
    "graphs_only",
    "with_features",
    "with_offer",
    "without_graphs_fields",
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
        effective_seed_ontologies,
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
    offer, unresolved = offer_from_seed(
        agents=agents,
        apps=sorted(effective_seed_apps(slug, catalog_seed)),
        modules=sorted(effective_seed_modules(slug, catalog_seed)),
        features=features,
        resolve_agent=resolve_agent or engine_agent_resolver(),
    )
    return (
        replace(
            offer,
            search_sources=default_search_sources(),
            ontologies=frozenset(effective_seed_ontologies(slug, catalog_seed)),
        ),
        unresolved,
    )


def default_search_sources() -> frozenset[str]:
    """Every source of the search (``search.sources``): what a new workspace offers."""
    from naas_abi.apps.nexus.apps.api.app.services.search.sources import default_sources

    return default_sources()


def in_offer_form(document: Any) -> bool:
    """Whether ``document`` is an allow-list this module wrote: only offer sections
    (or the ``Nothing`` placeholder), Allows but for the Denies of W's own graphs
    (``OfferGraphsDeny``). A ceiling of an older version (a wildcard and its Denies, the
    sets' move's) is not: the access migration (S4) converts it."""
    from naas_abi.apps.nexus.apps.api.app.services.iam.container_defaults import NOTHING_SID

    def fits(sid: Any, effect: str) -> bool:
        section = offer_section(sid)
        if section == given_graphs.DENY_SID:
            return effect == "Deny"
        return (section is not None or sid == NOTHING_SID) and effect == "Allow"

    statements = _statements_of(document)
    return bool(statements) and all(
        fits(sid, effect) for sid, effect, _actions, _resources in map(_statement_parts, statements)
    )


def instances_only(offer: Offer) -> Offer:
    """``offer`` without its features, what it gives outside the workspace and what it
    closes: what a re-seed adds (the rest is the settings')."""
    return replace(
        offer,
        features=frozenset(),
        search_sources=frozenset(),
        ontologies=frozenset(),
        org_files=None,
        platform_files=None,
        system_files=None,
        **without_graphs_fields(),
    )


def without_graphs_fields() -> dict[str, Any]:
    """The Graphs part of an offer, empty: ``replace(offer, **without_graphs_fields())``."""
    return {**{f: frozenset() for f in GRAPH_NAME_FIELDS}, "graphs_no_create": False}


def graphs_only(offer: Offer) -> Offer:
    """The Graphs part of ``offer`` alone."""
    return Offer(**{f: getattr(offer, f) for f in GRAPH_FIELDS})
