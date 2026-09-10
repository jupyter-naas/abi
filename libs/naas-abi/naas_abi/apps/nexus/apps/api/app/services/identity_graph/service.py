"""Materialise Nexus identity and access as a BFO 7-bucket graph.

Event logs only carry ids (``actor_user_id``, ``actor_workspace_id``, ...).
This graph is how an id gets back to a person, a workspace and a role:

- WHO: ``abi:Person`` carries its ``nexus:User`` account; ``nexus:Organization``
  (a material entity) carries its profile and workspaces and has persons as
  members.
- HOW WE KNOW: accounts, workspaces, organization profiles, memberships, app
  and agent configurations, the platform configuration with its settings,
  tenant branding, features, role baselines and workspace overrides.
- WHY: superadmin, organization and workspace access roles, borne by persons
  and concretizing the record that grants them.
- WHAT / WHEN / WHERE: the setup processes (``nexus:CreateUser``,
  ``nexus:AddUserToWorkspace``, ...) at their Postgres timestamps, occurring in
  the deployment site, plus ``nexus:ApplyPlatformConfiguration`` at boot.

It is rebuilt from Postgres and the running configuration on every boot and
after identity changes. IRIs come from ``iris.py`` so runtime events name the
same individuals. See docs/adr/20260910_nexus-identity-graph-for-events.md.
"""

from __future__ import annotations

import asyncio
import datetime
from dataclasses import dataclass
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.identity_graph import iris
from naas_abi.apps.nexus.apps.api.app.services.identity_graph.port import (
    IdentityGraphStorePort,
    IdentitySnapshot,
    IdentitySourcePort,
    PlatformConfigurationSourcePort,
    PlatformSnapshot,
)
from naas_abi.ontologies.modules.ABIOntology import Person, TemporalInstant
from naas_abi.ontologies.modules.NexusPlatformOntology import (
    AddUserToOrganization,
    AddUserToWorkspace,
    ApplyPlatformConfiguration,
    ConfigurationSetting,
    CreateOrganization,
    CreateUser,
    CreateWorkspace,
    DeploymentSite,
    Feature,
    FeatureAccessPolicy,
    NexusOrganization,
    OrganizationAccessRole,
    OrganizationAdminRole,
    OrganizationMemberRole,
    OrganizationMembership,
    OrganizationOwnerRole,
    OrganizationProfile,
    PlatformConfiguration,
    PlatformSuperadminRole,
    TenantBranding,
    User,
    Workspace,
    WorkspaceAccessRole,
    WorkspaceAdminRole,
    WorkspaceAgentConfiguration,
    WorkspaceAppConfiguration,
    WorkspaceFeatureOverride,
    WorkspaceMemberRole,
    WorkspaceMembership,
    WorkspaceOwnerRole,
    WorkspaceViewerRole,
)
from rdflib import Graph, Literal, URIRef

NEXUS = iris.NEXUS

# Not graph/nexus: NexusPlatformPipeline clears that graph whenever its agent
# signature changes and drops it when disabled.
IDENTITY_GRAPH_URI = URIRef("http://ontology.naas.ai/graph/nexus-identity")

WORKSPACE_ROLE_CLASSES: dict[str, type] = {
    "owner": WorkspaceOwnerRole,
    "admin": WorkspaceAdminRole,
    "member": WorkspaceMemberRole,
    "viewer": WorkspaceViewerRole,
}
ORGANIZATION_ROLE_CLASSES: dict[str, type] = {
    "owner": OrganizationOwnerRole,
    "admin": OrganizationAdminRole,
    "member": OrganizationMemberRole,
}

# Postgres column -> generated field, where the two differ.
_PROFILE_FIELD_BY_COLUMN = {"login_bg_image_url": "login_background_image_url"}
_ORGANIZATION_PROFILE_FIELDS = set(OrganizationProfile.model_fields)
_WORKSPACE_FIELDS = set(Workspace.model_fields)
_TENANT_FIELDS = set(TenantBranding.model_fields)


def _present(values: dict[str, Any], allowed: set[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for column, value in values.items():
        name = _PROFILE_FIELD_BY_COLUMN.get(column, column)
        if name in allowed and value is not None and value != "":
            out[name] = value
    return out


class _Builder:
    def __init__(self, snapshot: IdentitySnapshot):
        self.snapshot = snapshot
        self.platform: PlatformSnapshot | None = snapshot.platform
        self.graph = Graph()
        self.graph.bind("nexus", NEXUS)
        self.site: URIRef | None = (
            iris.deployment_site_iri(self.platform.host) if self.platform else None
        )
        self.config: URIRef | None = (
            iris.platform_configuration_iri(self.platform.host) if self.platform else None
        )
        self.names = {user.id: user.name for user in snapshot.users}
        self.workspace_names = {w.id: w.name for w in snapshot.workspaces}
        self.organization_names = {o.id: o.name for o in snapshot.organizations}

    def add(self, entity: Any) -> URIRef:
        self.graph += entity.rdf()
        return URIRef(entity._uri)

    def instant(self, at: datetime.datetime) -> list[URIRef]:
        label = at.isoformat()
        return [self.add(TemporalInstant(_uri=str(iris.instant_iri(label)), label=label))]

    def where(self) -> list[URIRef]:
        return [self.site] if self.site is not None else []

    def process(
        self, cls: type, iri: URIRef, label: str, at: datetime.datetime, **links: Any
    ) -> URIRef:
        return self.add(
            cls(
                _uri=str(iri),
                label=label,
                created_at=self.instant(at),
                occurs_in=self.where(),
                **links,
            )
        )

    # --- building -----------------------------------------------------------

    def build(self) -> Graph:
        if self.platform is not None:
            self.platform_configuration(self.platform)
        for user in self.snapshot.users:
            self.user(user)
        for organization in self.snapshot.organizations:
            self.organization(organization)
        for membership in self.snapshot.organization_memberships:
            self.organization_membership(membership)
        for workspace in self.snapshot.workspaces:
            self.workspace(workspace)
        for membership in self.snapshot.memberships:
            self.workspace_membership(membership)
        for app in self.snapshot.app_configs:
            self.add(
                WorkspaceAppConfiguration(
                    _uri=str(iris.workspace_app_iri(app.workspace_id, app.app_id)),
                    label=app.app_id,
                    app_id=app.app_id,
                    app_enabled=app.enabled,
                    is_part_of=[iris.workspace_iri(app.workspace_id)],
                )
            )
        for agent in self.snapshot.agent_configs:
            fields = {
                "class_name": agent.class_name,
                "module_path": agent.module_path,
                "model_id": agent.model_id,
                "provider": agent.provider,
            }
            self.add(
                WorkspaceAgentConfiguration(
                    _uri=str(iris.workspace_agent_iri(agent.id)),
                    label=agent.name,
                    agent_name=agent.name,
                    agent_enabled=agent.enabled,
                    is_default_agent=agent.is_default,
                    is_part_of=[iris.workspace_iri(agent.workspace_id)],
                    **{k: v for k, v in fields.items() if v},
                )
            )
        return self.graph

    def platform_configuration(self, platform: PlatformSnapshot) -> None:
        assert self.site is not None and self.config is not None
        self.add(DeploymentSite(_uri=str(self.site), label=platform.host))
        features = sorted(
            set(platform.enabled_features)
            | {f for fs in platform.role_baseline.values() for f in fs}
            | {f for fs in platform.workspace_overrides.values() for f in fs}
            | {
                f
                for roles in platform.organization_overrides.values()
                for fs in roles.values()
                for f in fs
            }
            | {
                f
                for roles in self.snapshot.organization_role_features.values()
                for fs in roles.values()
                for f in fs
            }
        )
        for key in features:
            self.add(Feature(_uri=str(iris.feature_iri(key)), label=key, feature_key=key))

        parts: list[URIRef] = []
        for key, value in sorted(platform.settings.items()):
            parts.append(
                self.add(
                    ConfigurationSetting(
                        _uri=str(iris.configuration_setting_iri(platform.host, key)),
                        label=key,
                        setting_key=key,
                        setting_value=value,
                        is_part_of=[self.config],
                    )
                )
            )
        tenant = _present(platform.tenant, _TENANT_FIELDS)
        if tenant:
            parts.append(
                self.add(
                    TenantBranding(
                        _uri=str(iris.tenant_branding_iri(platform.host)),
                        label=str(tenant.get("tab_title") or platform.host),
                        is_part_of=[self.config],
                        **tenant,
                    )
                )
            )
        for role, allowed in sorted(platform.role_baseline.items()):
            parts.append(self.feature_policy(role, allowed, None))
        overlays: dict[str, dict[str, list[str]]] = {}
        for source in (platform.organization_overrides, self.snapshot.organization_role_features):
            for org_id, roles in source.items():
                overlays.setdefault(org_id, {}).update(roles)
        for org_id, roles in sorted(overlays.items()):
            for role, allowed in sorted(roles.items()):
                parts.append(self.feature_policy(role, allowed, org_id))
        workspace_by_slug = {w.slug: w.id for w in self.snapshot.workspaces if w.slug}
        for slug, flags in sorted(platform.workspace_overrides.items()):
            workspace_id = workspace_by_slug.get(slug)
            if workspace_id is None:
                continue
            for key, enabled in sorted(flags.items()):
                parts.append(
                    self.add(
                        WorkspaceFeatureOverride(
                            _uri=str(iris.feature_override_iri(workspace_id, key)),
                            label=f"{slug}: {key} {'on' if enabled else 'off'}",
                            feature_enabled=enabled,
                            overrides_feature=[iris.feature_iri(key)],
                            overrides_workspace=[iris.workspace_iri(workspace_id)],
                        )
                    )
                )
        self.add(
            PlatformConfiguration(
                _uri=str(self.config),
                label=f"Platform configuration of {platform.host}",
                enables_feature=[
                    iris.feature_iri(k) for k in sorted(set(platform.enabled_features))
                ],
                has_part=parts,
            )
        )
        self.process(
            ApplyPlatformConfiguration,
            iris.process_iri("apply-platform-configuration", platform.host),
            f"Apply platform configuration of {platform.host}",
            platform.applied_at,
            concretizes=[self.config],
        )

    def feature_policy(self, role: str, allowed: list[str], organization_id: str | None) -> URIRef:
        scope = (
            self.organization_names.get(organization_id or "", organization_id)
            if organization_id
            else None
        )
        return self.add(
            FeatureAccessPolicy(
                _uri=str(iris.feature_policy_iri(role, organization_id)),
                label=f"{role} features" + (f" in {scope}" if scope else ""),
                policy_role=role,
                grants_feature=[iris.feature_iri(k) for k in sorted(set(allowed))],
                **(
                    {"applies_to_organization": [iris.organization_iri(organization_id)]}
                    if organization_id
                    else {}
                ),
            )
        )

    def user(self, user: Any) -> None:
        person = iris.person_iri(user.id)
        account = iris.user_account_iri(user.id)
        self.add(Person(_uri=str(person), label=user.name, full_name=user.name))
        profile = {
            "avatar_url": user.avatar,
            "company": user.company,
            "job_title": user.job_title,
            "bio": user.bio,
        }
        credential_storage = (
            self.platform.credential_storage_by_email.get(user.email.lower())
            if self.platform
            else None
        )
        if credential_storage is not None:
            profile["store_credentials_in_secrets"] = credential_storage
        self.add(
            User(
                _uri=str(account),
                label=user.email,
                user_id=user.id,
                user_email=user.email,
                is_user_account_of=[person],
                **{k: v for k, v in profile.items() if v is not None and v != ""},
            )
        )
        self.process(
            CreateUser,
            iris.process_iri("create-user", user.id),
            f"Create user {user.name}",
            user.created_at,
            created_for=[person],
            creates=[account],
            target_user_id=user.id,
        )
        if user.is_superadmin:
            role = PlatformSuperadminRole(
                _uri=str(iris.superadmin_role_iri(user.id)),
                label=f"{user.name} — platform superadmin",
                inheres_in=[person],
            )
            if self.config is not None:
                role.concretizes = [self.config]
            self.add(role)

    def organization(self, organization: Any) -> None:
        org = iris.organization_iri(organization.id)
        profile = iris.organization_profile_iri(organization.id)
        self.add(
            OrganizationProfile(
                _uri=str(profile),
                label=organization.name,
                organization_id=organization.id,
                organization_name=organization.name,
                slug=organization.slug,
                is_organization_profile_of=[org],
                **_present(organization.profile, _ORGANIZATION_PROFILE_FIELDS),
            )
        )
        members = [
            iris.person_iri(m.user_id)
            for m in self.snapshot.organization_memberships
            if m.organization_id == organization.id
        ]
        workspaces = [
            iris.workspace_iri(w.id)
            for w in self.snapshot.workspaces
            if w.organization_id == organization.id
        ]
        self.add(
            NexusOrganization(
                _uri=str(org),
                label=organization.name,
                has_organization_profile=[profile],
                has_user=members,
                has_workspace=workspaces,
            )
        )
        creation = (
            {"created_by": [iris.person_iri(organization.owner_id)]}
            if organization.owner_id
            else {}
        )
        self.process(
            CreateOrganization,
            iris.process_iri("create-organization", organization.id),
            f"Create organization {organization.name}",
            organization.created_at,
            creates=[profile],
            has_participant=[org],
            target_organization_id=organization.id,
            **creation,
        )

    def organization_membership(self, membership: Any) -> None:
        person = iris.person_iri(membership.user_id)
        record = iris.organization_membership_iri(membership.organization_id, membership.user_id)
        who = self.names.get(membership.user_id, membership.user_id)
        where = self.organization_names.get(membership.organization_id, membership.organization_id)
        self.add(
            OrganizationMembership(
                _uri=str(record),
                label=f"{who} is {membership.role} of {where}",
                membership_role=membership.role,
                is_membership_of_account=[iris.user_account_iri(membership.user_id)],
                is_membership_of_organization=[iris.organization_iri(membership.organization_id)],
            )
        )
        role_cls = ORGANIZATION_ROLE_CLASSES.get(membership.role, OrganizationAccessRole)
        self.add(
            role_cls(
                _uri=str(
                    iris.organization_role_iri(membership.organization_id, membership.user_id)
                ),
                label=f"{who} — {membership.role} of {where}",
                inheres_in=[person],
                concretizes=[record],
            )
        )
        self.process(
            AddUserToOrganization,
            iris.process_iri(
                "add-user-to-organization", membership.organization_id, membership.user_id
            ),
            f"Add {who} to {where}",
            membership.created_at,
            created_for=[person],
            creates=[record],
            membership_role=membership.role,
            target_user_id=membership.user_id,
            target_organization_id=membership.organization_id,
        )

    def workspace(self, workspace: Any) -> None:
        iri = iris.workspace_iri(workspace.id)
        seed = (
            self.platform.workspace_seeds.get(workspace.slug or "")
            if self.platform is not None
            else None
        )
        seeded: dict[str, Any] = {}
        if seed is not None and seed.default_agent:
            seeded["default_agent"] = seed.default_agent
        organization = (
            {"is_workspace_of": [iris.organization_iri(workspace.organization_id)]}
            if workspace.organization_id
            else {}
        )
        self.add(
            Workspace(
                _uri=str(iri),
                label=workspace.name,
                workspace_id=workspace.id,
                workspace_name=workspace.name,
                **({"slug": workspace.slug} if workspace.slug else {}),
                **_present(workspace.settings, _WORKSPACE_FIELDS),
                **seeded,
                **organization,
            )
        )
        # Generated data properties are single-valued; these are lists.
        if seed is not None:
            for prop, values in (
                (NEXUS.seeded_agent, seed.agents),
                (NEXUS.seeded_app, seed.apps),
                (NEXUS.seeded_ontology, seed.ontologies),
            ):
                for value in values:
                    self.graph.add((iri, prop, Literal(value)))
        creation = (
            {"created_by": [iris.person_iri(workspace.owner_id)]} if workspace.owner_id else {}
        )
        self.process(
            CreateWorkspace,
            iris.process_iri("create-workspace", workspace.id),
            f"Create workspace {workspace.name}",
            workspace.created_at,
            creates=[iri],
            target_workspace_id=workspace.id,
            **creation,
        )

    def workspace_membership(self, membership: Any) -> None:
        person = iris.person_iri(membership.user_id)
        record = iris.workspace_membership_iri(membership.workspace_id, membership.user_id)
        who = self.names.get(membership.user_id, membership.user_id)
        where = self.workspace_names.get(membership.workspace_id, membership.workspace_id)
        self.add(
            WorkspaceMembership(
                _uri=str(record),
                label=f"{who} is {membership.role} of {where}",
                membership_role=membership.role,
                is_membership_of_account=[iris.user_account_iri(membership.user_id)],
                is_membership_of_workspace=[iris.workspace_iri(membership.workspace_id)],
            )
        )
        role_cls = WORKSPACE_ROLE_CLASSES.get(membership.role, WorkspaceAccessRole)
        self.add(
            role_cls(
                _uri=str(iris.workspace_role_iri(membership.workspace_id, membership.user_id)),
                label=f"{who} — {membership.role} of {where}",
                inheres_in=[person],
                concretizes=[record],
            )
        )
        # The workspace access process.
        self.process(
            AddUserToWorkspace,
            iris.process_iri("add-user-to-workspace", membership.workspace_id, membership.user_id),
            f"Add {who} to {where}",
            membership.created_at,
            created_for=[person],
            creates=[record],
            updates=[
                iris.user_account_iri(membership.user_id),
                iris.workspace_iri(membership.workspace_id),
            ],
            membership_role=membership.role,
            target_user_id=membership.user_id,
            target_workspace_id=membership.workspace_id,
        )


def build_identity_graph(snapshot: IdentitySnapshot) -> Graph:
    return _Builder(snapshot).build()


@dataclass(frozen=True)
class IdentityGraphSyncResult:
    users: int
    workspaces: int
    memberships: int
    organizations: int
    triples: int


class IdentityGraphService:
    def __init__(
        self,
        source: IdentitySourcePort,
        store: IdentityGraphStorePort,
        platform: PlatformConfigurationSourcePort | None = None,
    ):
        self._source = source
        self._store = store
        self._platform = platform

    async def sync(self) -> IdentityGraphSyncResult:
        snapshot = await self._source.load_snapshot()
        if self._platform is not None:
            snapshot.platform = self._platform.load_platform()
        graph = build_identity_graph(snapshot)
        await asyncio.to_thread(self._store.replace_graph, IDENTITY_GRAPH_URI, graph)
        return IdentityGraphSyncResult(
            users=len(snapshot.users),
            workspaces=len(snapshot.workspaces),
            memberships=len(snapshot.memberships),
            organizations=len(snapshot.organizations),
            triples=len(graph),
        )
