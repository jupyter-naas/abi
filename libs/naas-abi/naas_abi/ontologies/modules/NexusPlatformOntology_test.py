from pathlib import Path

from rdflib import OWL, RDFS, Graph, Namespace, URIRef

ABI = Namespace("http://ontology.naas.ai/abi/")
NEXUS = Namespace("http://ontology.naas.ai/nexus/")

_MODULES = Path(__file__).parent


def _graph() -> Graph:
    graph = Graph()
    graph.parse(_MODULES / "ABIOntology.ttl")
    graph.parse(_MODULES / "NexusPlatformOntology.ttl")
    return graph


def _sub_properties_of(graph: Graph, prop: URIRef) -> set[URIRef]:
    return {
        p
        for p in graph.transitive_subjects(RDFS.subPropertyOf, prop)
        if isinstance(p, URIRef)
    }


def _is_subclass_of(graph: Graph, cls: URIRef, ancestor: URIRef) -> bool:
    return ancestor in set(graph.transitive_objects(cls, RDFS.subClassOf))


def test_participant_restrictions_never_target_a_gdc() -> None:
    """abi:Process only admits material entities and qualities as participants.

    A GDC (user account, workspace, ...) as participant makes the ontology
    inconsistent, since BFO keeps GDCs disjoint from both. Persons participate;
    accounts are what processes create or update.
    """
    graph = _graph()
    participant_props = _sub_properties_of(graph, ABI.hasParticipant)
    offenders = []
    for restriction in graph.subjects(OWL.onProperty, None):
        prop = graph.value(restriction, OWL.onProperty)
        if prop not in participant_props:
            continue
        for filler_pred in (OWL.someValuesFrom, OWL.allValuesFrom):
            filler = graph.value(restriction, filler_pred)
            if isinstance(filler, URIRef) and _is_subclass_of(
                graph, filler, ABI.GenericallyDependentContinuant
            ):
                owner = graph.value(None, RDFS.subClassOf, restriction)
                offenders.append((owner, prop, filler))
    assert offenders == []


def test_participant_properties_never_range_over_a_gdc() -> None:
    graph = _graph()
    offenders = [
        (prop, rng)
        for prop in _sub_properties_of(graph, ABI.hasParticipant)
        for rng in graph.objects(prop, RDFS.range)
        if isinstance(rng, URIRef)
        and _is_subclass_of(graph, rng, ABI.GenericallyDependentContinuant)
    ]
    assert offenders == []


def test_user_account_is_carried_by_a_person() -> None:
    graph = _graph()
    assert (NEXUS.isUserAccountOf, RDFS.range, ABI.Person) in graph
    assert _is_subclass_of(graph, NEXUS.User, ABI.GenericallyDependentContinuant)


def test_member_parts_are_never_information_entities() -> None:
    """hasMemberPart relates material entities; an organization's members are persons."""
    graph = _graph()
    offenders = [
        (prop, rng)
        for prop in _sub_properties_of(graph, ABI.hasMemberPart)
        for rng in graph.objects(prop, RDFS.range)
        if isinstance(rng, URIRef)
        and _is_subclass_of(graph, rng, ABI.GenericallyDependentContinuant)
    ]
    assert offenders == []


IDENTITY_PROCESSES = [
    "ApplyPlatformConfiguration",
    "CreateUser",
    "UpdateUser",
    "DeleteUser",
    "CreateOrganization",
    "UpdateOrganization",
    "DeleteOrganization",
    "AddUserToOrganization",
    "ChangeOrganizationMemberRole",
    "RemoveUserFromOrganization",
    "CreateWorkspace",
    "UpdateWorkspace",
    "DeleteWorkspace",
    "AddUserToWorkspace",
    "ChangeWorkspaceMemberRole",
    "RemoveUserFromWorkspace",
    "ConfigureWorkspaceApp",
    "ConfigureWorkspaceAgent",
    "ConfigureOrganizationRoleFeatures",
]


def _all_values_from(graph: Graph, cls: URIRef, prop: URIRef) -> set[URIRef]:
    fillers = set()
    for ancestor in graph.transitive_objects(cls, RDFS.subClassOf):
        for restriction in graph.objects(ancestor, RDFS.subClassOf):
            if graph.value(restriction, OWL.onProperty) == prop:
                filler = graph.value(restriction, OWL.allValuesFrom)
                if isinstance(filler, URIRef):
                    fillers.add(filler)
    return fillers


def test_identity_processes_are_placed_in_the_seven_buckets() -> None:
    graph = _graph()
    buckets = {
        "WHEN": (NEXUS.createdAt, ABI.TemporalInstant),
        "WHO acted": (NEXUS.createdBy, ABI.Person),
        "WHO for": (NEXUS.createdFor, ABI.Person),
        "WHERE": (ABI.occursIn, NEXUS.DeploymentSite),
        "HOW WE KNOW (writes)": (NEXUS.creates, ABI.GenericallyDependentContinuant),
        "HOW WE KNOW (changes)": (NEXUS.updates, ABI.GenericallyDependentContinuant),
        "HOW WE KNOW (removes)": (NEXUS.deletes, ABI.GenericallyDependentContinuant),
        "WHY": (ABI.realizes, ABI.Role),
    }
    for name in IDENTITY_PROCESSES:
        cls = NEXUS[name]
        assert _is_subclass_of(graph, cls, ABI.Process), name
        for bucket, (prop, target) in buckets.items():
            assert target in _all_values_from(graph, cls, prop), (
                f"{name} misses {bucket}"
            )


def test_access_roles_are_borne_by_persons_and_concretize_their_grant() -> None:
    graph = _graph()
    grants = {
        NEXUS.PlatformSuperadminRole: NEXUS.PlatformConfiguration,
        NEXUS.WorkspaceAccessRole: NEXUS.WorkspaceMembership,
        NEXUS.OrganizationAccessRole: NEXUS.OrganizationMembership,
    }
    for role, grant in grants.items():
        assert _is_subclass_of(graph, role, ABI.Role)
        assert _all_values_from(graph, role, ABI.inheresIn) == {ABI.Person}
        some = {
            graph.value(r, OWL.someValuesFrom)
            for r in graph.objects(role, RDFS.subClassOf)
            if graph.value(r, OWL.onProperty) == ABI.concretizes
        }
        assert grant in some
    for level in ("Owner", "Admin", "Member", "Viewer"):
        assert _is_subclass_of(
            graph, NEXUS[f"Workspace{level}Role"], NEXUS.WorkspaceAccessRole
        )
    for level in ("Owner", "Admin", "Member"):
        assert _is_subclass_of(
            graph, NEXUS[f"Organization{level}Role"], NEXUS.OrganizationAccessRole
        )


def test_new_information_entities_are_gdcs() -> None:
    graph = _graph()
    for name in (
        "OrganizationProfile",
        "WorkspaceMembership",
        "OrganizationMembership",
        "PlatformConfiguration",
        "ConfigurationSetting",
        "TenantBranding",
        "Feature",
        "FeatureAccessPolicy",
        "WorkspaceFeatureOverride",
        "WorkspaceAppConfiguration",
        "WorkspaceAgentConfiguration",
    ):
        assert _is_subclass_of(
            graph, NEXUS[name], ABI.GenericallyDependentContinuant
        ), name
