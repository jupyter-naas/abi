"""Who may read or write which graph is IAM's, proven on a real kernel.

A real IAM, the real triple store (embedded Oxigraph) wired to it and the real
graph service: graphs a workspace creates are placed in it, the workspace's
roles reach exactly them, and the kernel refuses the rest whichever route asks.
What one workspace is given of another's graphs is its offer's
(``graph_offer_test``).
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from naas_abi import ABIModule
from naas_abi.apps.nexus.apps.api.app.services.graph.access import GraphAccessError
from naas_abi.apps.nexus.apps.api.app.services.graph.adapters.secondary import graph_iam
from naas_abi.apps.nexus.apps.api.app.services.graph.adapters.secondary.workspace_policy import (
    load_workspace_scope,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.testing import knowledge_team
from naas_abi.apps.nexus.apps.api.app.services.iam.names import workspace_container
from naas_abi.apps.nexus.apps.api.app.services.workspaces.adapters.secondary import (
    resource_access_postgres as saved_policies,
)
from naas_abi.apps.nexus.graph_policy_config import (
    NEXUS_GRAPH,
    SCHEMA_GRAPH,
    WorkspaceGraphPolicyConfig,
)
from naas_abi_core.engine.call_context import as_service_account, use_call_context
from naas_abi_core.engine.IEngine import IEngine
from naas_abi_core.services.iam.IAMPorts import PermissionDeniedError
from naas_abi_core.services.triple_store.adaptors.secondary.TripleStoreService__SecondaryAdaptor__OxigraphEmbedded import (  # noqa: E501
    TripleStoreService__SecondaryAdaptor__OxigraphEmbedded as OxigraphEmbedded,
)
from naas_abi_core.services.triple_store.TripleStorePorts import Exceptions
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from rdflib import Graph, Literal, URIRef

_CONFIG = SimpleNamespace(
    configuration=SimpleNamespace(
        nexus_config=SimpleNamespace(ontology_base_uri="http://ontology.naas.ai/nexus/")
    )
)
with patch.object(ABIModule, "get_instance", return_value=_CONFIG):
    from naas_abi.apps.nexus.apps.api.app.services.graph.service import GraphService

PLATFORM = "urn:graph:platform"
P = URIRef("urn:p")


class _Bus:
    def publish_many(self, *_args, **_kwargs) -> None:
        return None


@pytest.fixture
def team():
    with knowledge_team() as nexus:
        yield nexus


class World:
    """The kernel store, and each workspace's saved assignments (its access policy is no
    allow-list here: the view reads the saved ones)."""

    def __init__(self, nexus, store) -> None:
        self.nexus = nexus
        self.store = store
        self.policies: dict[str, WorkspaceGraphPolicyConfig] = {}

    def acting(self, user: str):
        return use_call_context(self.nexus.context(user))

    async def view(self, user: str, workspace: str):
        """The workspace's view for ``user``, resolved as a request does."""
        with self.acting(user):
            return await load_workspace_scope(None, self.store, workspace, user)

    async def service(self, user: str, workspace: str) -> GraphService:
        scope = await self.view(user, workspace)
        return GraphService(lambda: self.store, access_scope=scope)

    async def create(self, user: str, workspace: str, label: str = "Sales"):
        service = await self.service(user, workspace)
        with self.acting(user):
            return await service.create_graph(workspace, label, None, user)

    def select(self, user: str, iri: str):
        with self.acting(user):
            return list(self.store.query(f"SELECT ?o WHERE {{ GRAPH <{iri}> {{ ?s ?p ?o }} }}"))

    def put(self, iri: str) -> None:
        graph = Graph()
        graph.add((URIRef(f"{iri}/s"), P, Literal("x")))
        with as_service_account("api"):
            self.store.insert(graph, URIRef(iri))


@pytest.fixture
def world(team, tmp_path, monkeypatch):
    store = TripleStoreService(OxigraphEmbedded(str(tmp_path / "oxigraph")))
    store.set_services(IEngine.Services(iam=team.iam, bus=_Bus()))
    found = World(team, store)

    async def saved(_db, workspace_id, _kind):
        config = found.policies.get(workspace_id, WorkspaceGraphPolicyConfig())
        return SimpleNamespace(data=config.model_dump(), revision=1)

    monkeypatch.setattr(saved_policies, "load_resource_policy", saved)
    yield found
    OxigraphEmbedded._stores.pop(str(tmp_path / "oxigraph"), None)


# -- a workspace's own graphs: placements ---------------------------------------


@pytest.mark.asyncio
async def test_a_graph_a_workspace_creates_is_placed_in_it(world) -> None:
    created = await world.create("member", "ws-1")
    assert graph_iam.owned_by("ws-1") == {created.uri}
    assert graph_iam.owned_by("ws-2") == set()
    placement = world.nexus.iam.placement_of("triple_store", graph_iam.graph_id(created.uri))
    assert placement.container == workspace_container("org-1", "ws-1")
    # Nexus's own record of it is the application graph, not an ownership triple.
    with as_service_account("api"):
        triples = world.store.query(
            f"SELECT ?o WHERE {{ GRAPH <{NEXUS_GRAPH}> {{ <{created.uri}> "
            "<http://ontology.naas.ai/nexus/graphWorkspaceId> ?o }}"
        )
    assert list(triples) == []


@pytest.mark.asyncio
async def test_the_members_roles_reach_exactly_their_workspaces_graphs(world) -> None:
    created = await world.create("member", "ws-1")
    service = await world.service("member", "ws-1")
    with world.acting("member"):
        await service.create_individual("ws-1", created.uri, "Alice", None)
    for user, expected in {
        "viewer": {created.uri},
        "member": {created.uri},
        "admin": {created.uri},
        "owner": {created.uri},
        # Nobody of ws-2, nor a stranger, sees ws-1's graph through ws-1.
        "stranger": set(),
        "viewer2": set(),
        "member2": set(),
        "admin2": set(),
    }.items():
        assert (await world.view(user, "ws-1")).readable == expected, user
    for user in ("stranger", "member2", "admin2", "viewer2"):
        with pytest.raises(Exceptions.GraphNotFoundError):
            world.select(user, created.uri)


@pytest.mark.asyncio
async def test_viewers_query_but_neither_insert_create_nor_drop(world) -> None:
    created = await world.create("admin", "ws-1")
    viewer = await world.view("viewer", "ws-1")
    assert viewer.readable == {created.uri}
    assert viewer.writable == frozenset()
    assert viewer.can_create is False
    service = await world.service("viewer", "ws-1")
    with world.acting("viewer"):
        for operation in (
            service.create_graph("ws-1", "Mine", None, "viewer"),
            service.create_individual("ws-1", created.uri, "Bob", None),
            service.clear_graph("ws-1", created.uri),
            service.delete_graph("ws-1", created.uri),
        ):
            with pytest.raises(GraphAccessError):
                await operation
        # The kernel itself refuses what the view would not have offered.
        with pytest.raises(PermissionDeniedError):
            world.store.insert(Graph(), URIRef(created.uri))
        with pytest.raises(PermissionDeniedError):
            world.store.drop_graph(URIRef(created.uri))


@pytest.mark.asyncio
async def test_members_write_and_only_admins_clear_or_drop(world) -> None:
    created = await world.create("member", "ws-1")
    member = await world.service("member", "ws-1")
    with world.acting("member"):
        await member.create_individual("ws-1", created.uri, "Alice", None)
        for operation in (
            member.clear_graph("ws-1", created.uri),
            member.delete_graph("ws-1", created.uri),
        ):
            with pytest.raises(GraphAccessError):
                await operation
    admin = await world.service("admin", "ws-1")
    with world.acting("admin"):
        await admin.clear_graph("ws-1", created.uri)
        await admin.delete_graph("ws-1", created.uri)
    assert graph_iam.owned_by("ws-1") == set()


@pytest.mark.asyncio
async def test_a_user_in_two_workspaces_sees_one_workspaces_graphs_at_a_time(world, team) -> None:
    team.grant("both", "member", workspace_container("org-1", "ws-1"))
    team.grant("both", "member", workspace_container("org-1", "ws-2"))
    first = await world.create("both", "ws-1", "One")
    second = await world.create("both", "ws-2", "Two")
    assert (await world.view("both", "ws-1")).readable == {first.uri}
    assert (await world.view("both", "ws-2")).readable == {second.uri}
    # The kernel lets them read both; the workspace's pages offer its own.
    assert world.select("both", second.uri) == []
    service = await world.service("both", "ws-1")
    with pytest.raises(GraphAccessError):
        with world.acting("both"):
            await service.get_graph("ws-1", second.uri)


@pytest.mark.asyncio
async def test_nexus_catalog_graph_is_reached_by_no_role_but_listing_works(world) -> None:
    created = await world.create("member", "ws-1")
    probe = f"SELECT ?s WHERE {{ GRAPH <{NEXUS_GRAPH}> {{ ?s ?p ?o }} }}"
    for user in ("viewer", "member", "admin", "owner"):
        with world.acting(user), pytest.raises(Exceptions.GraphNotFoundError):
            list(world.store.query(probe))
    # Nexus lists the workspace's graphs from its application graph, as itself.
    service = await world.service("viewer", "ws-1")
    with world.acting("viewer"):
        packs = await service.list_graphs("ws-1")
    assert [g.uri for pack in packs for g in pack.graphs] == [created.uri]


# -- the assignments editor -------------------------------------------------------


@pytest.mark.asyncio
async def test_the_editor_offers_only_graphs_the_administrator_administers(world) -> None:
    from naas_abi.apps.nexus.apps.api.app.services.workspaces.adapters.primary.resource_access import (  # noqa: E501
        _graph_catalog,
    )

    mine = await world.create("admin", "ws-1")
    theirs = await world.create("admin2", "ws-2")
    world.put(PLATFORM)
    service = SimpleNamespace(_get_catalog_store=lambda: world.store)

    def offered(user: str, workspace: str, held=()) -> set[str]:
        found = _graph_catalog(service, workspace, user, set(held))
        return {item["id"] for item in found}

    def run(user: str, workspace: str, held=()) -> set[str]:
        with world.acting(user):
            return offered(user, workspace, held)

    assert await asyncio.to_thread(run, "admin", "ws-1") == {mine.uri}
    assert await asyncio.to_thread(run, "admin2", "ws-2") == {theirs.uri}
    # What the workspace already holds stays on offer (a revocation needs it).
    assert await asyncio.to_thread(run, "admin2", "ws-2", {mine.uri}) == {mine.uri, theirs.uri}
    everything = {mine.uri, theirs.uri, PLATFORM, SCHEMA_GRAPH}
    assert await asyncio.to_thread(run, "root", "ws-1") == everything


# -- a label is data, never SPARQL --------------------------------------------------


@pytest.mark.asyncio
async def test_a_role_label_cannot_probe_other_tenants_graphs(world, team) -> None:
    """The role lookup runs as Nexus, which reads every graph: a label that closes
    its string must find nothing and change nothing outside it."""
    from naas_abi.apps.nexus.apps.api.app.services.graph.adapters.secondary.nexus_catalog import (
        NexusCatalogStore,
    )
    from naas_abi.apps.nexus.apps.api.app.services.graph.service import (
        _get_or_create_knowledge_graph_role,
    )

    secret = Graph()
    secret.add((URIRef("urn:victim/s"), P, Literal("topsecret-value")))
    with as_service_account("api"):
        world.store.insert(secret, URIRef("urn:graph:victim"))
    store = NexusCatalogStore(world.store)

    def probe(prefix: str) -> str:
        return 'x"||exists{graph ?g{?s ?p ?o filter(strstarts(lcase(str(?o)),"' + prefix + '"))}})#'

    with as_service_account("api"):
        seed = _get_or_create_knowledge_graph_role(store, "seed-role")
        present = _get_or_create_knowledge_graph_role(store, probe("topsecret"))
        absent = _get_or_create_knowledge_graph_role(store, probe("nothing-like-it"))
        # Both are new roles named by the text sent: the answer did not depend on
        # what other tenants keep (a hit would have linked to an existing role).
        assert present.label.startswith('x"||exists') and absent.label.startswith('x"||exists')
        assert present.label != absent.label
        assert seed._uri not in (present._uri, absent._uri)
        again = _get_or_create_knowledge_graph_role(store, probe("topsecret"))
        assert again._uri == present._uri
        # A line break in a label is part of it, not a syntax error.
        assert _get_or_create_knowledge_graph_role(store, "sales\nlead").label == "sales\nlead"
