"""The Nexus feature office agents, by feature key (mirrors the web map).

Strings only, imported lazily: agent modules import this package, so this
module must not import them at load time. Keep in sync with
``FEATURE_OFFICE_AGENTS`` in ``apps/web/src/lib/feature-office-agents.ts``
(a test checks both sides).
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass


@dataclass(frozen=True)
class FeatureAgentSpec:
    name: str
    class_name: str
    feature_keys: tuple[str, ...]
    summary: str

    @property
    def module(self) -> str:
        return f"naas_abi.agents.{self.class_name}"

    @property
    def roster_ref(self) -> str:
        return f"naas_abi {self.class_name}"

    def load(self) -> type:
        return getattr(importlib.import_module(self.module), self.class_name)


FEATURE_AGENTS: tuple[FeatureAgentSpec, ...] = (
    FeatureAgentSpec(
        "Slides", "SlidesAgent", ("slides",), "decks, presentations, slides"
    ),
    FeatureAgentSpec(
        "Apps",
        "AppsAgent",
        ("apps",),
        "workspace apps: list, open, enable or disable, embeds and SSO",
    ),
    FeatureAgentSpec(
        "Marketplace",
        "MarketplaceAgent",
        ("marketplace",),
        "ABI modules catalog, tiers, pricing, installing a module",
    ),
    FeatureAgentSpec(
        "Ontology",
        "OntologyAgent",
        ("ontology",),
        "the workspace ontology catalog, classes, relations, import/export, BFO modeling",
    ),
    FeatureAgentSpec(
        "Knowledge Graph",
        "KnowledgeGraphAgent",
        ("graph",),
        "knowledge graphs (NodeGraph): graphs, KPIs, individuals, saved views, import/export",
    ),
    FeatureAgentSpec(
        "Files",
        "FilesAgent",
        ("files",),
        "workspace drive and My drive: folders, reading and writing files",
    ),
    FeatureAgentSpec(
        "Datasets",
        "DatasetsAgent",
        ("datasets",),
        "structured datasets: schemas, previews, read-only SQL",
    ),
    FeatureAgentSpec(
        "Search", "SearchAgent", ("search",), "the Search page: web and ontology search"
    ),
    FeatureAgentSpec("Maps", "MapsAgent", ("maps",), "map layers and their data feeds"),
    FeatureAgentSpec(
        "Code",
        "CodeAgent",
        ("code",),
        "repositories, branches, pull requests, Coder workspaces, and code workspace vs business workspace",
    ),
    FeatureAgentSpec(
        "Settings",
        "SettingsAgent",
        ("settings", "settings.workspace", "settings.organization"),
        "workspace and organization settings, members and roles, the user's own role and feature access, feature flags, secret names",
    ),
    FeatureAgentSpec(
        "Agent Catalog",
        "AgentCatalogAgent",
        ("agents", "skills"),
        "the workspace's agents roster and skills",
    ),
)


def spec_for_agent(name: str) -> FeatureAgentSpec:
    for spec in FEATURE_AGENTS:
        if name in (spec.name, spec.class_name):
            return spec
    raise KeyError(name)


def spec_for_feature(feature_key: str) -> FeatureAgentSpec | None:
    return next((s for s in FEATURE_AGENTS if feature_key in s.feature_keys), None)


def abi_handoff_line() -> str:
    """One line per feature agent for Abi's system prompt."""
    return "; ".join(f"{spec.name} for {spec.summary}" for spec in FEATURE_AGENTS)
