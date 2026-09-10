from __future__ import annotations

import datetime

import pytest
from naas_abi.apps.nexus.apps.api.app.services.identity_graph.iris import (
    deployment_site_iri,
    feature_iri,
    feature_override_iri,
    feature_policy_iri,
    organization_iri,
    organization_membership_iri,
    organization_profile_iri,
    organization_role_iri,
    person_iri,
    platform_configuration_iri,
    superadmin_role_iri,
    user_account_iri,
    workspace_agent_iri,
    workspace_app_iri,
    workspace_iri,
    workspace_membership_iri,
    workspace_role_iri,
)
from naas_abi.apps.nexus.apps.api.app.services.identity_graph.port import (
    IdentityAgentConfig,
    IdentityAppConfig,
    IdentityGraphStorePort,
    IdentityMembership,
    IdentityOrganization,
    IdentityOrganizationMembership,
    IdentitySnapshot,
    IdentitySourcePort,
    IdentityUser,
    IdentityWorkspace,
    IdentityWorkspaceSeed,
    PlatformConfigurationSourcePort,
    PlatformSnapshot,
)
from naas_abi.apps.nexus.apps.api.app.services.identity_graph.service import (
    IDENTITY_GRAPH_URI,
    IdentityGraphService,
    build_identity_graph,
)
from rdflib import RDF, Graph, Literal, Namespace, URIRef

ABI = Namespace("http://ontology.naas.ai/abi/")
NEXUS = Namespace("http://ontology.naas.ai/nexus/")

T0 = datetime.datetime(2026, 5, 1, 9, 30)
BOOT = datetime.datetime(2026, 9, 10, 8, 0)
HOST = "bob.example.com"

ALICE = IdentityUser(
    id="usr-1",
    name="Alice Martin",
    email="alice@example.com",
    created_at=T0,
    company="Acme",
    job_title="CTO",
    is_superadmin=True,
)
BOB = IdentityUser(id="usr-2", name="Bob Stone", email="bob@example.com", created_at=T0)
ORG = IdentityOrganization(
    id="org-1",
    name="Acme Group",
    slug="acme-group",
    owner_id="usr-1",
    created_at=T0,
    profile={"primary_color": "#0057B8", "show_powered_by": False, "login_footer_text": "© Acme"},
)
ACME = IdentityWorkspace(
    id="ws-1",
    name="Acme",
    slug="acme",
    owner_id="usr-1",
    organization_id="org-1",
    created_at=T0,
    settings={"primary_color": "#0057B8", "platform_drive_enabled": True},
)
BOB_IN_ACME = IdentityMembership(
    id="mem-1", workspace_id="ws-1", user_id="usr-2", role="member", created_at=T0
)
ALICE_OWNS_ACME = IdentityMembership(
    id="mem-2", workspace_id="ws-1", user_id="usr-1", role="owner", created_at=T0
)
BOB_IN_ORG = IdentityOrganizationMembership(
    id="om-1", organization_id="org-1", user_id="usr-2", role="admin", created_at=T0
)
PLATFORM = PlatformSnapshot(
    host=HOST,
    applied_at=BOOT,
    enabled_features=["chat", "files", "slides"],
    role_baseline={"owner": ["chat", "files", "slides"], "viewer": ["chat"]},
    workspace_overrides={"acme": {"files": False}},
    organization_overrides={"org-1": {"member": ["chat", "slides"]}},
    tenant={"tab_title": "Bob AI Platform", "primary_color": "#0057B8", "show_powered_by": False},
    settings={"abi_agent_model": "qwen-3.8", "nexus_config.magic_link_allow_signup": "false"},
    credential_storage_by_email={"alice@example.com": False},
    workspace_seeds={
        "acme": IdentityWorkspaceSeed(
            default_agent="bob BobAgent",
            agents=["bob BobAgent", "naas_abi SlidesAgent"],
            apps=["external.acme:web"],
            ontologies=["naas_abi:BFO7BucketsProcessOntology.ttl"],
        )
    },
)


def _snapshot(**overrides) -> IdentitySnapshot:
    values: dict = {
        "users": [ALICE, BOB],
        "workspaces": [ACME],
        "memberships": [BOB_IN_ACME, ALICE_OWNS_ACME],
        "organizations": [ORG],
        "organization_memberships": [BOB_IN_ORG],
        "app_configs": [
            IdentityAppConfig(workspace_id="ws-1", app_id="external.acme:web", enabled=True)
        ],
        "agent_configs": [
            IdentityAgentConfig(
                id="agc-1",
                workspace_id="ws-1",
                name="Bob",
                class_name="BobAgent",
                module_path="bob",
                enabled=True,
                is_default=True,
            )
        ],
        "organization_role_features": {},
        "platform": PLATFORM,
    }
    values.update(overrides)
    return IdentitySnapshot(**values)


def _process(graph: Graph, cls: URIRef, **links: URIRef) -> URIRef:
    candidates = [
        p
        for p in graph.subjects(RDF.type, cls)
        if all((p, NEXUS[prop], target) in graph for prop, target in links.items())
    ]
    assert len(candidates) == 1, f"{cls} {links}: {candidates}"
    return candidates[0]


def _select(graph: Graph, query: str) -> list[tuple[str, ...]]:
    prefixes = "PREFIX nexus: <http://ontology.naas.ai/nexus/> PREFIX abi: <http://ontology.naas.ai/abi/>\n"
    return sorted(tuple(str(v) for v in row) for row in graph.query(prefixes + query))


# --- WHO / HOW WE KNOW: persons carry accounts ------------------------------


def test_person_carries_the_user_account_with_its_profile() -> None:
    graph = build_identity_graph(_snapshot())

    account, person = user_account_iri("usr-1"), person_iri("usr-1")
    assert (account, RDF.type, NEXUS.User) in graph
    assert (person, RDF.type, ABI.Person) in graph
    assert (account, NEXUS.isUserAccountOf, person) in graph
    assert (person, ABI.full_name, Literal("Alice Martin")) in graph
    assert (account, NEXUS.user_id, Literal("usr-1")) in graph
    assert (account, NEXUS.company, Literal("Acme")) in graph
    assert (account, NEXUS.job_title, Literal("CTO")) in graph
    assert (account, NEXUS.store_credentials_in_secrets, Literal(False)) in graph


def test_user_id_in_an_event_resolves_to_the_person() -> None:
    """The event log only holds the Nexus user id; the graph gets us the person."""
    graph = build_identity_graph(_snapshot())

    rows = _select(
        graph,
        """SELECT ?name WHERE {
          ?account nexus:user_id "usr-2" ; nexus:isUserAccountOf ?person .
          ?person abi:full_name ?name . }""",
    )
    assert rows == [("Bob Stone",)]


# --- WHY: access roles ------------------------------------------------------


def test_superadmin_role_is_borne_by_the_person_and_granted_by_the_configuration() -> None:
    graph = build_identity_graph(_snapshot())

    role = superadmin_role_iri("usr-1")
    assert (role, RDF.type, NEXUS.PlatformSuperadminRole) in graph
    assert (role, ABI.inheresIn, person_iri("usr-1")) in graph
    assert (role, ABI.concretizes, platform_configuration_iri(HOST)) in graph
    assert not list(graph.triples((superadmin_role_iri("usr-2"), None, None)))


def test_workspace_role_leads_to_its_workspace_through_the_membership() -> None:
    graph = build_identity_graph(_snapshot())

    rows = _select(
        graph,
        """SELECT ?type ?workspace ?level WHERE {
          ?role abi:inheresIn ?person ; a ?type ; abi:concretizes ?membership .
          ?membership nexus:isMembershipOfWorkspace ?ws ; nexus:membership_role ?level .
          ?ws nexus:workspace_name ?workspace .
          ?account nexus:user_id "usr-2" ; nexus:isUserAccountOf ?person .
          FILTER(STRSTARTS(STR(?type), STR(nexus:)))
          FILTER(?type != <http://ontology.naas.ai/nexus/WorkspaceAccessRole>) }""",
    )
    assert rows == [(str(NEXUS.WorkspaceMemberRole), "Acme", "member")]
    assert (workspace_role_iri("ws-1", "usr-1"), RDF.type, NEXUS.WorkspaceOwnerRole) in graph


def test_unknown_role_level_still_yields_an_access_role() -> None:
    odd = IdentityMembership(
        id="m", workspace_id="ws-1", user_id="usr-2", role="guest", created_at=T0
    )
    graph = build_identity_graph(_snapshot(memberships=[odd]))

    assert (workspace_role_iri("ws-1", "usr-2"), RDF.type, NEXUS.WorkspaceAccessRole) in graph


def test_organization_role_concretizes_the_organization_membership() -> None:
    graph = build_identity_graph(_snapshot())

    role, membership = (
        organization_role_iri("org-1", "usr-2"),
        organization_membership_iri("org-1", "usr-2"),
    )
    assert (role, RDF.type, NEXUS.OrganizationAdminRole) in graph
    assert (role, ABI.inheresIn, person_iri("usr-2")) in graph
    assert (role, ABI.concretizes, membership) in graph
    assert (membership, NEXUS.isMembershipOfOrganization, organization_iri("org-1")) in graph
    assert (membership, NEXUS.isMembershipOfAccount, user_account_iri("usr-2")) in graph


# --- WHO: organizations -----------------------------------------------------


def test_organization_is_a_material_entity_carrying_its_profile_and_workspaces() -> None:
    graph = build_identity_graph(_snapshot())

    org, profile = organization_iri("org-1"), organization_profile_iri("org-1")
    assert (org, RDF.type, NEXUS.Organization) in graph
    assert (org, NEXUS.hasOrganizationProfile, profile) in graph
    assert (profile, RDF.type, NEXUS.OrganizationProfile) in graph
    assert (profile, NEXUS.slug, Literal("acme-group")) in graph
    assert (profile, NEXUS.primary_color, Literal("#0057B8")) in graph
    assert (profile, NEXUS.show_powered_by, Literal(False)) in graph
    assert (org, NEXUS.hasWorkspace, workspace_iri("ws-1")) in graph
    assert (workspace_iri("ws-1"), NEXUS.isWorkspaceOf, org) in graph
    # Members are persons, not accounts.
    assert (org, NEXUS.hasUser, person_iri("usr-2")) in graph
    assert (org, NEXUS.hasUser, user_account_iri("usr-2")) not in graph


# --- HOW WE KNOW: workspaces and their configuration -----------------------


def test_workspace_records_its_settings_and_configured_seeds() -> None:
    graph = build_identity_graph(_snapshot())

    ws = workspace_iri("ws-1")
    assert (ws, NEXUS.slug, Literal("acme")) in graph
    assert (ws, NEXUS.primary_color, Literal("#0057B8")) in graph
    assert (ws, NEXUS.platform_drive_enabled, Literal(True)) in graph
    assert (ws, NEXUS.default_agent, Literal("bob BobAgent")) in graph
    assert (ws, NEXUS.seeded_agent, Literal("naas_abi SlidesAgent")) in graph
    assert (ws, NEXUS.seeded_app, Literal("external.acme:web")) in graph
    assert (ws, NEXUS.seeded_ontology, Literal("naas_abi:BFO7BucketsProcessOntology.ttl")) in graph


def test_app_and_agent_configurations_are_parts_of_the_workspace() -> None:
    graph = build_identity_graph(_snapshot())

    app, agent = workspace_app_iri("ws-1", "external.acme:web"), workspace_agent_iri("agc-1")
    assert (app, NEXUS.isPartOf, workspace_iri("ws-1")) in graph
    assert (app, NEXUS.app_enabled, Literal(True)) in graph
    assert (agent, NEXUS.isPartOf, workspace_iri("ws-1")) in graph
    assert (agent, NEXUS.class_name, Literal("BobAgent")) in graph
    assert (agent, NEXUS.is_default_agent, Literal(True)) in graph


def test_platform_configuration_enables_features_and_holds_policies() -> None:
    graph = build_identity_graph(_snapshot())

    config = platform_configuration_iri(HOST)
    assert {str(f) for f in graph.objects(config, NEXUS.enablesFeature)} == {
        str(feature_iri(k)) for k in ("chat", "files", "slides")
    }
    viewer = feature_policy_iri("viewer")
    assert (viewer, NEXUS.policy_role, Literal("viewer")) in graph
    assert set(graph.objects(viewer, NEXUS.grantsFeature)) == {feature_iri("chat")}
    overlay = feature_policy_iri("member", "org-1")
    assert (overlay, NEXUS.appliesToOrganization, organization_iri("org-1")) in graph
    override = feature_override_iri("ws-1", "files")
    assert (override, NEXUS.overridesWorkspace, workspace_iri("ws-1")) in graph
    assert (override, NEXUS.feature_enabled, Literal(False)) in graph
    for part in (viewer, overlay, override):
        assert (config, NEXUS.hasPart, part) in graph


def test_organization_role_feature_rows_overlay_the_baseline() -> None:
    graph = build_identity_graph(
        _snapshot(organization_role_features={"org-1": {"viewer": ["chat", "files"]}})
    )

    overlay = feature_policy_iri("viewer", "org-1")
    assert set(graph.objects(overlay, NEXUS.grantsFeature)) == {
        feature_iri("chat"),
        feature_iri("files"),
    }


def test_settings_and_tenant_branding_are_parts_of_the_configuration() -> None:
    graph = build_identity_graph(_snapshot())

    rows = _select(
        graph,
        """SELECT ?key ?value WHERE {
          ?s a nexus:ConfigurationSetting ; nexus:setting_key ?key ; nexus:setting_value ?value . }""",
    )
    assert rows == [
        ("abi_agent_model", "qwen-3.8"),
        ("nexus_config.magic_link_allow_signup", "false"),
    ]
    branding = next(graph.subjects(RDF.type, NEXUS.TenantBranding))
    assert (branding, NEXUS.tab_title, Literal("Bob AI Platform")) in graph
    assert (platform_configuration_iri(HOST), NEXUS.hasPart, branding) in graph


# --- WHAT / WHEN / WHERE: the setup processes -------------------------------


def test_create_user_process_creates_the_account_for_the_person() -> None:
    graph = build_identity_graph(_snapshot())

    process = _process(graph, NEXUS.CreateUser, creates=user_account_iri("usr-1"))
    assert (process, NEXUS.createdFor, person_iri("usr-1")) in graph
    instant = graph.value(process, NEXUS.createdAt)
    assert (instant, RDF.type, ABI.TemporalInstant) in graph


def test_create_workspace_and_organization_are_created_by_the_owner() -> None:
    graph = build_identity_graph(_snapshot())

    ws = _process(graph, NEXUS.CreateWorkspace, creates=workspace_iri("ws-1"))
    assert (ws, NEXUS.createdBy, person_iri("usr-1")) in graph
    org = _process(graph, NEXUS.CreateOrganization, creates=organization_profile_iri("org-1"))
    assert (org, NEXUS.createdBy, person_iri("usr-1")) in graph
    assert (org, ABI.hasParticipant, organization_iri("org-1")) in graph


def test_workspace_without_owner_has_no_creator() -> None:
    orphan = IdentityWorkspace(id="ws-9", name="Orphan", owner_id=None, created_at=T0)
    graph = build_identity_graph(IdentitySnapshot(workspaces=[orphan]))

    process = _process(graph, NEXUS.CreateWorkspace, creates=workspace_iri("ws-9"))
    assert graph.value(process, NEXUS.createdBy) is None


def test_workspace_access_process_writes_the_membership_for_the_member() -> None:
    graph = build_identity_graph(_snapshot())

    membership = workspace_membership_iri("ws-1", "usr-2")
    process = _process(graph, NEXUS.AddUserToWorkspace, creates=membership)
    assert (process, NEXUS.createdFor, person_iri("usr-2")) in graph
    assert (process, NEXUS.updates, user_account_iri("usr-2")) in graph
    assert (process, NEXUS.updates, workspace_iri("ws-1")) in graph
    assert (membership, NEXUS.membership_role, Literal("member")) in graph
    _process(
        graph, NEXUS.AddUserToOrganization, creates=organization_membership_iri("org-1", "usr-2")
    )


def test_every_setup_process_has_a_when_and_a_where() -> None:
    graph = build_identity_graph(_snapshot())

    processes = set(graph.subjects(NEXUS.createdAt, None))
    # 2 users, 1 organization, 1 organization member, 1 workspace, 2 members, boot
    assert len(processes) == 8
    for process in processes:
        assert (process, ABI.occursIn, deployment_site_iri(HOST)) in graph, process
    assert (deployment_site_iri(HOST), RDF.type, NEXUS.DeploymentSite) in graph


def test_booting_applies_the_platform_configuration() -> None:
    graph = build_identity_graph(_snapshot())

    process = next(graph.subjects(RDF.type, NEXUS.ApplyPlatformConfiguration))
    assert (process, ABI.concretizes, platform_configuration_iri(HOST)) in graph
    instant = graph.value(process, NEXUS.createdAt)
    assert (
        str(graph.value(instant, URIRef("http://www.w3.org/2000/01/rdf-schema#label")))
        == BOOT.isoformat()
    )


def test_participants_are_persons_or_organizations_never_accounts() -> None:
    graph = build_identity_graph(_snapshot())

    information = {
        s
        for cls in (
            NEXUS.User,
            NEXUS.Workspace,
            NEXUS.WorkspaceMembership,
            NEXUS.OrganizationProfile,
        )
        for s in graph.subjects(RDF.type, cls)
    }
    for prop in (ABI.hasParticipant, NEXUS.createdBy, NEXUS.createdFor):
        assert not information & set(graph.objects(None, prop))


def test_without_platform_configuration_the_graph_still_builds() -> None:
    graph = build_identity_graph(_snapshot(platform=None))

    assert (user_account_iri("usr-1"), NEXUS.isUserAccountOf, person_iri("usr-1")) in graph
    assert not list(graph.subjects(RDF.type, NEXUS.PlatformConfiguration))


def test_building_twice_gives_the_same_triples() -> None:
    assert set(build_identity_graph(_snapshot())) == set(build_identity_graph(_snapshot()))


# --- service ----------------------------------------------------------------


class _FakeSource(IdentitySourcePort):
    async def load_snapshot(self) -> IdentitySnapshot:
        return _snapshot(platform=None)


class _FakePlatform(PlatformConfigurationSourcePort):
    def load_platform(self) -> PlatformSnapshot | None:
        return PLATFORM


class _FakeStore(IdentityGraphStorePort):
    def __init__(self) -> None:
        self.replaced: list[tuple[URIRef, Graph]] = []

    def replace_graph(self, graph_uri: URIRef, graph: Graph) -> None:
        self.replaced.append((graph_uri, graph))


@pytest.mark.asyncio
async def test_sync_merges_postgres_and_configuration_into_one_graph() -> None:
    store = _FakeStore()

    result = await IdentityGraphService(
        source=_FakeSource(), store=store, platform=_FakePlatform()
    ).sync()

    [(uri, graph)] = store.replaced
    assert uri == IDENTITY_GRAPH_URI
    assert (result.users, result.workspaces, result.memberships, result.organizations) == (
        2,
        1,
        2,
        1,
    )
    assert result.triples == len(graph)
    assert (superadmin_role_iri("usr-1"), RDF.type, NEXUS.PlatformSuperadminRole) in graph


def test_account_carries_the_hash_terminal_events_use() -> None:
    import hashlib

    graph = build_identity_graph(_snapshot())

    digest = hashlib.sha256(b"alice@example.com").hexdigest()
    assert (user_account_iri("usr-1"), NEXUS.user_email_sha256, Literal(digest)) in graph
