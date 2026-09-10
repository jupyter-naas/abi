from __future__ import annotations

import datetime
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from rdflib import Graph, URIRef


@dataclass(frozen=True)
class IdentityUser:
    id: str
    name: str
    email: str
    created_at: datetime.datetime
    avatar: str | None = None
    company: str | None = None
    # users.role is the job title the user typed in their profile, not access.
    job_title: str | None = None
    bio: str | None = None
    is_superadmin: bool = False


@dataclass(frozen=True)
class IdentityOrganization:
    id: str
    name: str
    slug: str
    owner_id: str | None
    created_at: datetime.datetime
    # Branding columns, keyed by column name (logo_url, primary_color, ...).
    profile: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class IdentityOrganizationMembership:
    id: str
    organization_id: str
    user_id: str
    role: str
    created_at: datetime.datetime


@dataclass(frozen=True)
class IdentityWorkspace:
    id: str
    name: str
    owner_id: str | None
    created_at: datetime.datetime
    slug: str | None = None
    organization_id: str | None = None
    # Workspace columns, keyed by column name (logo_url, primary_color, ...).
    settings: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class IdentityMembership:
    id: str
    workspace_id: str
    user_id: str
    role: str
    created_at: datetime.datetime


@dataclass(frozen=True)
class IdentityAppConfig:
    workspace_id: str
    app_id: str
    enabled: bool


@dataclass(frozen=True)
class IdentityAgentConfig:
    id: str
    workspace_id: str
    name: str
    class_name: str | None = None
    module_path: str | None = None
    model_id: str | None = None
    provider: str | None = None
    enabled: bool = False
    is_default: bool = False


@dataclass(frozen=True)
class IdentityWorkspaceSeed:
    """What the platform configuration says about one workspace (by slug)."""

    default_agent: str | None = None
    agents: list[str] = field(default_factory=list)
    apps: list[str] = field(default_factory=list)
    ontologies: list[str] = field(default_factory=list)


@dataclass
class PlatformSnapshot:
    """The naas_abi module configuration a deployment runs with. No secrets."""

    host: str
    applied_at: datetime.datetime
    enabled_features: list[str] = field(default_factory=list)
    role_baseline: dict[str, list[str]] = field(default_factory=dict)
    # workspace slug -> feature -> enabled
    workspace_overrides: dict[str, dict[str, bool]] = field(default_factory=dict)
    # organization id -> role -> features (config overlays and organization_role_features rows)
    organization_overrides: dict[str, dict[str, list[str]]] = field(default_factory=dict)
    tenant: dict[str, Any] = field(default_factory=dict)
    settings: dict[str, str] = field(default_factory=dict)
    # email -> store_credentials_in_secrets, from the users seed
    credential_storage_by_email: dict[str, bool] = field(default_factory=dict)
    # workspace slug -> seed
    workspace_seeds: dict[str, IdentityWorkspaceSeed] = field(default_factory=dict)


@dataclass
class IdentitySnapshot:
    """Everything the identity graph is built from, read in one go."""

    users: list[IdentityUser] = field(default_factory=list)
    workspaces: list[IdentityWorkspace] = field(default_factory=list)
    memberships: list[IdentityMembership] = field(default_factory=list)
    organizations: list[IdentityOrganization] = field(default_factory=list)
    organization_memberships: list[IdentityOrganizationMembership] = field(default_factory=list)
    app_configs: list[IdentityAppConfig] = field(default_factory=list)
    agent_configs: list[IdentityAgentConfig] = field(default_factory=list)
    # organization id -> role -> features, from organization_role_features
    organization_role_features: dict[str, dict[str, list[str]]] = field(default_factory=dict)
    platform: PlatformSnapshot | None = None


class IdentitySourcePort(ABC):
    """Where Nexus users, organizations, workspaces and memberships are read from."""

    @abstractmethod
    async def load_snapshot(self) -> IdentitySnapshot:
        raise NotImplementedError


class PlatformConfigurationSourcePort(ABC):
    """Where the running platform configuration is read from."""

    @abstractmethod
    def load_platform(self) -> PlatformSnapshot | None:
        raise NotImplementedError


class IdentityGraphStorePort(ABC):
    """Where the identity graph is written. Blocking; called off the event loop."""

    @abstractmethod
    def replace_graph(self, graph_uri: URIRef, graph: Graph) -> None:
        raise NotImplementedError
