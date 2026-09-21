from __future__ import annotations

import datetime

from naas_abi.apps.nexus.apps.api.app.services.identity_graph.port import (
    IdentityMembership,
    IdentityOrganization,
    IdentitySnapshot,
    IdentityUser,
    IdentityWorkspace,
    PlatformSnapshot,
)
from naas_abi.apps.nexus.apps.api.app.services.identity_graph.resolver import (
    CachedEventEnricher,
    IdentityResolver,
    enrich_events,
)
from naas_abi.apps.nexus.apps.api.app.services.identity_graph.service import (
    IDENTITY_GRAPH_URI,
    build_identity_graph,
)
from rdflib import Dataset

T0 = datetime.datetime(2026, 5, 1, 9, 30)


def _resolver() -> IdentityResolver:
    snapshot = IdentitySnapshot(
        users=[
            IdentityUser(
                id="usr-1",
                name="Alice Martin",
                email="alice@example.com",
                created_at=T0,
                is_superadmin=True,
            ),
            IdentityUser(
                id="usr-2",
                name="Bob Stone",
                email="bob@example.com",
                created_at=T0,
                avatar="https://a/b.png",
            ),
        ],
        organizations=[
            IdentityOrganization(
                id="org-1", name="Acme Group", slug="acme-group", owner_id="usr-1", created_at=T0
            )
        ],
        workspaces=[
            IdentityWorkspace(
                id="ws-1",
                name="Acme",
                slug="acme",
                owner_id="usr-1",
                organization_id="org-1",
                created_at=T0,
                settings={"primary_color": "#0057B8"},
            )
        ],
        memberships=[
            IdentityMembership(
                id="m", workspace_id="ws-1", user_id="usr-2", role="admin", created_at=T0
            )
        ],
        platform=PlatformSnapshot(host="bob.example.com", applied_at=T0),
    )
    dataset = Dataset()
    dataset.graph(IDENTITY_GRAPH_URI).__iadd__(build_identity_graph(snapshot))
    return IdentityResolver(query=dataset.query)


def test_resolves_users_to_their_person() -> None:
    identities = _resolver().resolve(user_ids={"usr-1", "usr-2", "usr-unknown"})

    alice, bob = identities.users["usr-1"], identities.users["usr-2"]
    assert (alice.name, alice.email, alice.is_superadmin) == (
        "Alice Martin",
        "alice@example.com",
        True,
    )
    assert (bob.name, bob.avatar_url, bob.is_superadmin) == ("Bob Stone", "https://a/b.png", False)
    assert bob.person_iri == "http://ontology.naas.ai/nexus/person/usr-2"
    assert "usr-unknown" not in identities.users


def test_resolves_workspaces_organizations_and_roles() -> None:
    identities = _resolver().resolve(
        workspace_ids={"ws-1"},
        organization_ids={"org-1"},
        memberships={("ws-1", "usr-2"), ("ws-1", "usr-1")},
    )

    ws = identities.workspaces["ws-1"]
    assert (ws.name, ws.slug, ws.primary_color, ws.organization_name) == (
        "Acme",
        "acme",
        "#0057B8",
        "Acme Group",
    )
    assert identities.organizations["org-1"].name == "Acme Group"
    assert identities.workspace_roles == {("ws-1", "usr-2"): "admin"}


def test_hostile_ids_are_never_put_in_a_query() -> None:
    queries: list[str] = []
    resolver = IdentityResolver(query=lambda q: queries.append(q) or [])

    resolver.resolve(user_ids={'x" } } DROP ALL #', "usr-1"})

    assert queries and all("DROP" not in q for q in queries)


def test_enrich_events_attaches_names_without_touching_the_payload() -> None:
    events = [
        {
            "_class_uri": "http://ontology.naas.ai/nexus/ChangeWorkspaceMemberRole",
            "actor_user_id": "usr-1",
            "target_user_id": "usr-2",
            "target_workspace_id": "ws-1",
        },
        # Agent events carry user_id / workspace_id instead.
        {
            "_class_uri": "http://ontology.naas.ai/abi/agent/AgentModelCalled",
            "user_id": "usr-2",
            "workspace_id": "ws-1",
        },
        {"_class_uri": "http://ontology.naas.ai/abi/bus/BusMessagePublished"},
    ]

    enrich_events(events, _resolver())

    first = events[0]["_identity"]
    assert first["actor"]["name"] == "Alice Martin"
    assert first["actor"]["is_superadmin"] is True
    assert first["subject"]["name"] == "Bob Stone"
    assert first["subject"]["workspace_role"] == "admin"
    assert first["workspace"]["name"] == "Acme"
    assert events[1]["_identity"]["actor"]["name"] == "Bob Stone"
    assert events[1]["_identity"]["actor"]["workspace_role"] == "admin"
    assert "_identity" not in events[2]
    assert events[0]["actor_user_id"] == "usr-1"


def test_enrich_events_survives_a_failing_triple_store() -> None:
    def boom(_query: str):
        raise RuntimeError("fuseki down")

    events = [{"actor_user_id": "usr-1"}]
    enrich_events(events, IdentityResolver(query=boom))

    assert events == [{"actor_user_id": "usr-1"}]


def test_cached_enricher_skips_anonymous_events_and_reuses_resolutions() -> None:
    calls: list[str] = []
    inner = _resolver()
    counting = IdentityResolver(query=lambda q: calls.append(q) or inner._query(q))
    now = [0.0]
    enricher = CachedEventEnricher(counting, ttl_seconds=60, clock=lambda: now[0])

    anonymous = {"_class_uri": "http://ontology.naas.ai/abi/bus/BusMessagePublished"}
    enricher.enrich(anonymous)
    assert calls == [] and "_identity" not in anonymous

    first, second = {"actor_user_id": "usr-1"}, {"actor_user_id": "usr-1"}
    enricher.enrich(first)
    made = len(calls)
    enricher.enrich(second)
    assert len(calls) == made
    assert second["_identity"]["actor"]["name"] == "Alice Martin"

    now[0] = 61.0
    enricher.enrich({"actor_user_id": "usr-1"})
    assert len(calls) > made


def test_terminal_actors_resolve_through_their_git_email_hash() -> None:
    from naas_abi_core.services.event.local_identity import email_actor_id

    actor = email_actor_id("Bob@Example.com")
    events = [{"agent_name": "Git_Agent", "actor_user_id": actor, "workspace_id": "ws-1"}]

    enrich_events(events, _resolver())

    resolved = events[0]["_identity"]["actor"]
    assert (resolved["name"], resolved["user_id"]) == ("Bob Stone", "usr-2")
    assert resolved["workspace_role"] == "admin"


def test_unknown_terminal_actor_stays_unresolved() -> None:
    from naas_abi_core.services.event.local_identity import email_actor_id

    events = [{"actor_user_id": email_actor_id("stranger@example.com")}]
    enrich_events(events, _resolver())

    assert "_identity" not in events[0]
