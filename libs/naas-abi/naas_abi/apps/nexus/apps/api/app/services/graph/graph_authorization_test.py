"""Who may read or write which graph is IAM's, proven on a real kernel.

A real IAM, the real triple store (embedded Oxigraph) wired to it and the real
graph service: graphs a workspace creates are placed in it, the workspace's
roles reach exactly them, a graph one workspace shares with another is an
Allow statement for the receiving workspace's members, and the kernel refuses
the rest whichever route asks.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from naas_abi import ABIModule
from naas_abi.apps.nexus.apps.api.app.services.graph.access import GraphAccessError
from naas_abi.apps.nexus.apps.api.app.services.graph.adapters.secondary import graph_iam
from naas_abi.apps.nexus.apps.api.app.services.graph.adapters.secondary.graph_grants import (
    GRANTS,
    policy_name,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.adapters.secondary.graph_placements import (
    OWNER_PREDICATE,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.adapters.secondary.workspace_policy import (
    load_workspace_scope,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.testing import knowledge_team
from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import MEMBERSHIPS
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
    """The kernel store, and each workspace's saved assignments."""

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

    async def share(self, workspace: str, config: WorkspaceGraphPolicyConfig) -> None:
        self.policies[workspace] = config
        await GRANTS.apply(workspace, config, store=self.store)

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


# -- what a workspace shares or is given: Allow statements ----------------------


@pytest.mark.asyncio
async def test_a_shared_graph_is_read_by_the_receiving_workspace_not_written(world) -> None:
    shared = await world.create("member", "ws-1")
    world.put(shared.uri)
    await world.share("ws-2", WorkspaceGraphPolicyConfig(read=[shared.uri]))
    for user in ("viewer2", "member2", "admin2", "owner2"):
        view = await world.view(user, "ws-2")
        assert view.readable == {shared.uri}, user
        assert view.writable == frozenset(), user
        assert world.select(user, shared.uri)
    # Whoever holds nothing is offered nothing, however the workspace shares.
    assert (await world.view("stranger", "ws-2")).readable == frozenset()
    with pytest.raises(Exceptions.GraphNotFoundError):
        world.select("stranger", shared.uri)
    with world.acting("member2"), pytest.raises(PermissionDeniedError):
        world.store.insert(Graph(), URIRef(shared.uri))


@pytest.mark.asyncio
async def test_a_graph_shared_for_writing_is_written_by_members_never_viewers(world) -> None:
    shared = await world.create("member", "ws-1")
    await world.share("ws-2", WorkspaceGraphPolicyConfig(read=[shared.uri], write=[shared.uri]))
    assert (await world.view("viewer2", "ws-2")).writable == frozenset()
    for user in ("member2", "admin2", "owner2"):
        assert (await world.view(user, "ws-2")).writable == {shared.uri}, user
    service = await world.service("member2", "ws-2")
    with world.acting("member2"):
        await service.create_individual("ws-2", shared.uri, "Carol", None)
    with world.acting("viewer2"), pytest.raises(PermissionDeniedError):
        world.store.insert(Graph(), URIRef(shared.uri))
    # Sharing gives data, never control of the graph's life.
    admin = await world.service("admin2", "ws-2")
    with world.acting("admin2"):
        for operation in (
            admin.clear_graph("ws-2", shared.uri),
            admin.delete_graph("ws-2", shared.uri),
        ):
            with pytest.raises(GraphAccessError):
                await operation
    assert graph_iam.owned_by("ws-1") == {shared.uri}


@pytest.mark.asyncio
async def test_revoking_a_share_closes_it_and_leaves_no_policy(world, team) -> None:
    shared = await world.create("member", "ws-1")
    world.put(shared.uri)
    await world.share("ws-2", WorkspaceGraphPolicyConfig(read=[shared.uri], write=[shared.uri]))
    assert world.select("member2", shared.uri)
    await world.share("ws-2", WorkspaceGraphPolicyConfig())
    assert (await world.view("member2", "ws-2")).readable == frozenset()
    with pytest.raises(Exceptions.GraphNotFoundError):
        world.select("member2", shared.uri)
    names = {p.name for p in team.iam.list_policies(limit=1000).items}
    assert policy_name("ws-2", "read") not in names
    assert policy_name("ws-2", "write") not in names


@pytest.mark.asyncio
async def test_the_shared_grant_follows_the_workspaces_members(world, team) -> None:
    shared = await world.create("member", "ws-1")
    world.put(shared.uri)
    config = WorkspaceGraphPolicyConfig(read=[shared.uri], write=[shared.uri])
    await world.share("ws-2", config)
    # A new member holds it once the workspace's holders are synced.
    team.grant("newcomer", "viewer", workspace_container("org-1", "ws-2"))
    with pytest.raises(Exceptions.GraphNotFoundError):
        world.select("newcomer", shared.uri)
    await GRANTS.sync_members("ws-2")
    assert world.select("newcomer", shared.uri)
    # A promoted viewer may write what is shared for writing.
    team.grant("newcomer", "member", workspace_container("org-1", "ws-2"))
    await GRANTS.sync_members("ws-2")
    with world.acting("newcomer"):
        world.store.insert(Graph(), URIRef(shared.uri))
    # A removed member loses it.
    await MEMBERSHIPS.revoke("newcomer", workspace_container("org-1", "ws-2"))
    await GRANTS.sync_members("ws-2")
    with pytest.raises(Exceptions.GraphNotFoundError):
        world.select("newcomer", shared.uri)


@pytest.mark.asyncio
async def test_a_workspace_that_may_not_create_graphs_creates_none(world) -> None:
    await world.share("ws-1", WorkspaceGraphPolicyConfig(allow_create=False))
    assert (await world.view("member", "ws-1")).can_create is False
    assert (await world.view("member2", "ws-2")).can_create is True
    service = await world.service("member", "ws-1")
    with world.acting("member"), pytest.raises(GraphAccessError):
        await service.create_graph("ws-1", "No", None, "member")
    # Not through the kernel either: the workspace's own names are closed to creation.
    from dataclasses import replace

    from naas_abi_core.engine.call_context import current_call_context

    with world.acting("member"):
        ctx = replace(current_call_context(), container=workspace_container("org-1", "ws-1"))
        with use_call_context(ctx), pytest.raises(PermissionDeniedError):
            world.store.create_graph(URIRef("urn:graph:sneaky"))


@pytest.mark.asyncio
async def test_a_workspace_that_excludes_its_own_graphs_does_not_see_them(world) -> None:
    created = await world.create("member", "ws-1")
    world.put(created.uri)
    await world.share("ws-1", WorkspaceGraphPolicyConfig(include_owned=False))
    assert (await world.view("member", "ws-1")).readable == frozenset()
    with pytest.raises((PermissionDeniedError, Exceptions.GraphNotFoundError)):
        world.select("member", created.uri)


@pytest.mark.asyncio
async def test_reading_the_whole_catalog_reads_every_graph_but_the_application_graph(
    world,
) -> None:
    own = await world.create("member", "ws-1")
    world.put(own.uri)
    world.put(PLATFORM)
    await world.share("ws-2", WorkspaceGraphPolicyConfig(read_all=True))
    view = await world.view("viewer2", "ws-2")
    # The store's own schema graph is part of the catalog.
    assert view.readable == {own.uri, PLATFORM, SCHEMA_GRAPH}
    assert view.writable == frozenset()
    assert NEXUS_GRAPH not in view.readable
    assert world.select("viewer2", PLATFORM)
    with world.acting("viewer2"), pytest.raises(Exceptions.GraphNotFoundError):
        list(world.store.query(f"SELECT ?s WHERE {{ GRAPH <{NEXUS_GRAPH}> {{ ?s ?p ?o }} }}"))


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


# -- what a save of the assignments may widen -------------------------------------


@pytest.mark.asyncio
async def test_reading_the_whole_catalog_never_reaches_another_tenants_graphs(world, team) -> None:
    """``read_all`` shares what exists in the workspace's own organization (and the
    platform's), not what other organizations, or other people's personal
    workspaces, keep."""
    team.workspace("org-2", "ws-9")
    team.grant("other", "owner", workspace_container("org-2", "ws-9"))
    team.workspace(None, "solo-1")
    team.grant("solo1", "owner", workspace_container(None, "solo-1"))
    team.workspace(None, "solo-2")
    team.grant("solo2", "owner", workspace_container(None, "solo-2"))
    mine = await world.create("member", "ws-1")
    foreign = await world.create("other", "ws-9")
    private = await world.create("solo1", "solo-1")
    for graph in (mine, foreign, private):
        world.put(graph.uri)
    world.put(PLATFORM)

    await world.share("ws-2", WorkspaceGraphPolicyConfig(read_all=True))
    readable = (await world.view("viewer2", "ws-2")).readable
    assert {mine.uri, PLATFORM} <= readable
    assert foreign.uri not in readable and private.uri not in readable
    with pytest.raises((PermissionDeniedError, Exceptions.GraphNotFoundError)):
        world.select("viewer2", foreign.uri)

    # A personal workspace sweeps in nobody else's personal graph either.
    await world.share("solo-2", WorkspaceGraphPolicyConfig(read_all=True))
    readable = (await world.view("solo2", "solo-2")).readable
    assert private.uri not in readable and foreign.uri not in readable and mine.uri not in readable
    with pytest.raises((PermissionDeniedError, Exceptions.GraphNotFoundError)):
        world.select("solo2", private.uri)


@pytest.mark.asyncio
async def test_a_graph_recorded_for_another_workspace_is_not_swept_in_before_it_is_placed(
    world, team
) -> None:
    """At boot assignments are applied before IAM places the graphs the application
    graph records: those are their workspace's already."""
    team.workspace("org-2", "ws-9")
    team.grant("other", "owner", workspace_container("org-2", "ws-9"))
    foreign = await world.create("other", "ws-9")
    world.put(foreign.uri)
    with as_service_account("api"):  # the placement a restart has not made yet
        team.iam.delete_placement("triple_store", graph_iam.graph_id(foreign.uri))
    assert foreign.uri not in graph_iam.owned_by("ws-9")
    # An install from before placements: the application graph records the owner.
    record = Graph()
    record.add((URIRef(foreign.uri), URIRef(OWNER_PREDICATE), Literal("ws-9")))
    with as_service_account("api"):
        world.store.insert(record, URIRef(NEXUS_GRAPH))

    await world.share("ws-2", WorkspaceGraphPolicyConfig(read_all=True))

    assert foreign.uri not in (await world.view("viewer2", "ws-2")).readable
    with pytest.raises((PermissionDeniedError, Exceptions.GraphNotFoundError)):
        world.select("viewer2", foreign.uri)


@dataclass
class _Saved:
    data: dict
    revision: int


def _assignments_app(world, monkeypatch, current: WorkspaceGraphPolicyConfig, offered):
    from unittest.mock import AsyncMock

    from fastapi import FastAPI
    from naas_abi.apps.nexus.apps.api.app.services.graph.testing import acting_as_header
    from naas_abi.apps.nexus.apps.api.app.services.workspaces.adapters.primary import (
        resource_access as http,
    )

    saved: dict = {}

    async def load(_db, _workspace, _kind):
        return SimpleNamespace(data=current.model_dump(), revision=1)

    class Service:
        def __init__(self, _repository) -> None:
            pass

        async def save(self, _workspace, _kind, data, revision, _user):
            saved["data"] = data
            return _Saved(data=data, revision=revision + 1)

    monkeypatch.setattr(http, "load_resource_policy", load)
    monkeypatch.setattr(http, "ResourceAccessService", Service)
    monkeypatch.setattr(http, "sync_workspace", AsyncMock())
    monkeypatch.setattr(
        http, "assignment_catalog", AsyncMock(return_value=[{"id": iri} for iri in offered])
    )
    app = FastAPI()
    app.include_router(http.router, prefix="/api/workspaces")
    app.dependency_overrides[http.get_db] = lambda: None
    app.dependency_overrides[http.get_graph_service] = lambda: SimpleNamespace(
        _get_catalog_store=lambda: world.store
    )
    app.dependency_overrides[http.get_ontology_service] = lambda: SimpleNamespace()
    return acting_as_header(app), saved


@pytest.mark.asyncio
async def test_sharing_every_graph_is_for_platform_administrators(world, monkeypatch) -> None:
    from naas_abi.apps.nexus.apps.api.app.services.graph.testing import client

    app, saved = _assignments_app(world, monkeypatch, WorkspaceGraphPolicyConfig(), [])
    uri = "/api/workspaces/ws-1/resource-access/graphs"
    body = {"revision": 1, "policy": {"read_all": True}}
    for user in ("admin", "owner"):
        async with client(app, user) as http:
            assert (await http.put(uri, json=body)).status_code == 403, user
    assert saved == {}
    async with client(app, "root") as http:
        assert (await http.put(uri, json=body)).status_code == 200
    assert saved["data"]["read_all"] is True
    # Turning it off, or leaving it on while changing the rest, is the admin's.
    app, saved = _assignments_app(world, monkeypatch, WorkspaceGraphPolicyConfig(read_all=True), [])
    async with client(app, "admin") as http:
        keep = {"revision": 1, "policy": {"read_all": True, "include_owned": False}}
        assert (await http.put(uri, json=keep)).status_code == 200
        assert (await http.put(uri, json={"revision": 1, "policy": {}})).status_code == 200


@pytest.mark.asyncio
async def test_a_graph_read_may_become_a_write_only_by_those_who_may_drop_it(
    world, monkeypatch
) -> None:
    from naas_abi.apps.nexus.apps.api.app.services.graph.testing import client

    mine = await world.create("admin", "ws-1")
    theirs = await world.create("admin2", "ws-2")
    # ws-1 reads ``theirs`` (a platform administrator shared it read-only).
    current = WorkspaceGraphPolicyConfig(read=[theirs.uri])
    app, saved = _assignments_app(world, monkeypatch, current, [mine.uri, theirs.uri])
    uri = "/api/workspaces/ws-1/resource-access/graphs"
    upgrade = {"revision": 1, "policy": {"read": [theirs.uri], "write": [theirs.uri]}}
    async with client(app, "admin") as http:
        assert (await http.put(uri, json=upgrade)).status_code == 403
        assert saved == {}
        # Their own graph is theirs to share for writing; the read stays as it is.
        own = {"revision": 1, "policy": {"read": [theirs.uri], "write": [mine.uri]}}
        assert (await http.put(uri, json=own)).status_code == 200
    async with client(app, "root") as http:
        assert (await http.put(uri, json=upgrade)).status_code == 200


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
