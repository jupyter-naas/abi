"""What a workspace is given of the graphs outside it is its offer's (ADR
``20261125_offer_gives_outside_resources``): the Graphs part of "<W> access"
(``iam/given_graphs``), which IAM gives W's people while they belong to W, within their
level; what W closes of its own is a Deny of its bound.

A real IAM (``NexusIam``) with an organization and two workspaces made as Nexus makes
them, memberships given through ``MEMBERSHIPS``, the real triple store (embedded
Oxigraph) wired to it, the real graph service, and the offer written as the caller,
through the offer service and Settings › Graphs. Nothing is mocked."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import pytest_asyncio
from naas_abi import ABIModule
from naas_abi.apps.nexus.apps.api.app.services.feature_access import runtime as offers_runtime
from naas_abi.apps.nexus.apps.api.app.services.feature_access.service import (
    FeatureAccessService,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.access import GraphAccessError
from naas_abi.apps.nexus.apps.api.app.services.graph.adapters.secondary import graph_iam
from naas_abi.apps.nexus.apps.api.app.services.graph.adapters.secondary.workspace_policy import (
    load_workspace_scope,
)
from naas_abi.apps.nexus.apps.api.app.services.iam import given_graphs
from naas_abi.apps.nexus.apps.api.app.services.iam.authz import AUTHZ
from naas_abi.apps.nexus.apps.api.app.services.iam.container_defaults import CONTAINER_DEFAULTS
from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import MEMBERSHIPS
from naas_abi.apps.nexus.apps.api.app.services.iam.names import org_container
from naas_abi.apps.nexus.apps.api.app.services.iam.testing import NexusIam
from naas_abi.apps.nexus.apps.api.app.services.iam.workspace_offer import Offer, offer_of
from naas_abi.apps.nexus.apps.api.app.services.iam_admin.adapters.secondary.engine import (
    EngineIamGateway,
)
from naas_abi.apps.nexus.apps.api.app.services.iam_admin.testing import MemoryAudit
from naas_abi.apps.nexus.apps.api.app.services.workspaces.adapters.primary import (
    resource_access,
)
from naas_abi.apps.nexus.graph_policy_config import (
    NEXUS_IDENTITY_GRAPH,
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

OFFER = Offer.of(features=["graph"])
PLATFORM = "urn:graph:platform"
P = URIRef("urn:p")
CLOSED = (PermissionDeniedError, Exceptions.GraphNotFoundError)


class _Bus:
    def publish_many(self, *_args, **_kwargs) -> None:
        return None


class _NoStore:
    async def managed_among(self, policy_ids):  # noqa: ANN001 - unused here
        return {}


def _user(user: str) -> SimpleNamespace:
    return SimpleNamespace(id=user, is_superadmin=False)


class World:
    def __init__(self, nexus: NexusIam, store: TripleStoreService, offers) -> None:
        self.nexus = nexus
        self.store = store
        self.offers = offers

    def acting(self, user: str):
        return use_call_context(self.nexus.context(user))

    async def view(self, user: str, workspace: str):
        with self.acting(user):
            return await load_workspace_scope(None, self.store, workspace, user)

    async def service(self, user: str, workspace: str) -> GraphService:
        scope = await self.view(user, workspace)
        return GraphService(lambda: self.store, access_scope=scope)

    async def create(self, user: str, workspace: str, label: str = "Sales"):
        service = await self.service(user, workspace)
        with self.acting(user):
            return await service.create_graph(workspace, label, None, user)

    async def share(self, user: str, workspace: str, **config) -> WorkspaceGraphPolicyConfig:
        """Settings › Graphs saves ``config`` as ``user``: the offer, written as them."""
        saved = await resource_access._save_graphs(
            _user(user), workspace, WorkspaceGraphPolicyConfig(**config).model_dump()
        )
        return WorkspaceGraphPolicyConfig.model_validate(saved.data)

    def offer(self, workspace: str) -> Offer:
        record = CONTAINER_DEFAULTS._known[self.nexus.containers[workspace]]
        with as_service_account("api"):
            return offer_of(self.nexus.iam.get_policy(record.access_policy_id).document)

    def sids(self, workspace: str) -> list[str]:
        record = CONTAINER_DEFAULTS._known[self.nexus.containers[workspace]]
        with as_service_account("api"):
            document = self.nexus.iam.get_policy(record.access_policy_id).document
        return [s.sid for s in document.statements]

    def select(self, user: str, iri: str):
        with self.acting(user):
            return list(self.store.query(f"SELECT ?o WHERE {{ GRAPH <{iri}> {{ ?s ?p ?o }} }}"))

    def insert(self, user: str, iri: str) -> None:
        graph = Graph()
        graph.add((URIRef(f"{iri}/{user}"), P, Literal("x")))
        with self.acting(user):
            self.store.insert(graph, URIRef(iri))

    def put(self, iri: str) -> None:
        graph = Graph()
        graph.add((URIRef(f"{iri}/s"), P, Literal("x")))
        with as_service_account("api"):
            self.store.insert(graph, URIRef(iri))


@pytest.fixture
def team():
    nexus = NexusIam(features_with_roles=False)
    with nexus.installed():
        nexus.grouped_org("org-1", "Acme")
        nexus.grouped_org("org-2", "Other")
        nexus.containers = {  # type: ignore[attr-defined]
            ws: nexus.grouped_workspace(org, ws, ws.title(), offer=OFFER).container
            for org, ws in (
                ("org-1", "ws-1"),
                ("org-1", "ws-2"),
                ("org-2", "ws-9"),
                (None, "solo-1"),
                (None, "solo-2"),
            )
        }
        for person in ("viewer", "member", "admin", "viewer2", "member2", "admin2"):
            nexus.user(person)
        for person in ("other", "late", "stranger", "oadmin", "solo1", "solo2"):
            nexus.user(person)
        nexus.platform_admin("root")
        yield nexus
    CONTAINER_DEFAULTS.forget_grouped()


@pytest_asyncio.fixture
async def world(team, tmp_path):
    for suffix, workspace in (("", "ws-1"), ("2", "ws-2")):
        for level in ("viewer", "member", "admin"):
            await MEMBERSHIPS.grant(f"{level}{suffix}", level, team.containers[workspace])
    await MEMBERSHIPS.grant("other", "admin", team.containers["ws-9"])
    await MEMBERSHIPS.grant("oadmin", "admin", org_container("org-1"))
    await MEMBERSHIPS.grant("solo1", "admin", team.containers["solo-1"])
    await MEMBERSHIPS.grant("solo2", "admin", team.containers["solo-2"])
    store = TripleStoreService(OxigraphEmbedded(str(tmp_path / "oxigraph")))
    store.set_services(IEngine.Services(iam=team.iam, bus=_Bus()))
    offers = FeatureAccessService(
        EngineIamGateway(),
        _NoStore(),  # type: ignore[arg-type]
        MemoryAudit(),
        container_of=AUTHZ.container_of,
        defaults_of=CONTAINER_DEFAULTS.record_of,
        features=lambda: ["graph"],
    )
    previous = offers_runtime.configure(lambda: offers)
    yield World(team, store, offers)
    offers_runtime.configure(previous)
    OxigraphEmbedded._stores.pop(str(tmp_path / "oxigraph"), None)


# -- given to read and to write: within each person's level ------------------------------


@pytest.mark.asyncio
async def test_a_member_writes_a_graph_given_for_writing_and_a_viewer_only_reads_it(world):
    shared = await world.create("member", "ws-1")
    world.put(shared.uri)
    assert world.offer("ws-2").graphs_read == frozenset()
    await world.share("root", "ws-2", read=[shared.uri], write=[shared.uri])
    # Named as IAM placed it, in its own workspace.
    assert world.offer("ws-2").graphs_write == {
        given_graphs.name_in(world.nexus.containers["ws-1"], shared.uri)
    }
    for user in ("viewer2", "member2", "admin2"):
        assert (await world.view(user, "ws-2")).readable == {shared.uri}, user
        assert world.select(user, shared.uri), user
    for user in ("member2", "admin2"):
        assert (await world.view(user, "ws-2")).writable == {shared.uri}, user
        world.insert(user, shared.uri)
    # The level caps it: a Viewer of ws-2 reads, never writes.
    assert (await world.view("viewer2", "ws-2")).writable == frozenset()
    with pytest.raises(PermissionDeniedError):
        world.insert("viewer2", shared.uri)
    # Given data, never the graph's life.
    admin = await world.service("admin2", "ws-2")
    with world.acting("admin2"):
        for operation in (
            admin.clear_graph("ws-2", shared.uri),
            admin.delete_graph("ws-2", shared.uri),
        ):
            with pytest.raises(GraphAccessError):
                await operation
    assert graph_iam.owned_by("ws-1") == {shared.uri}
    # Nobody outside ws-2 is given it.
    for user in ("stranger", "other", "late"):
        assert (await world.view(user, "ws-2")).readable == frozenset(), user
        with pytest.raises(CLOSED):
            world.select(user, shared.uri)


@pytest.mark.asyncio
async def test_joining_gives_it_and_leaving_the_workspace_ends_it(world):
    shared = await world.create("member", "ws-1")
    world.put(shared.uri)
    await world.share("root", "ws-2", read=[shared.uri], write=[shared.uri])
    with pytest.raises(CLOSED):
        world.select("late", shared.uri)
    await MEMBERSHIPS.grant("late", "viewer", world.nexus.containers["ws-2"])
    assert world.select("late", shared.uri)
    with pytest.raises(PermissionDeniedError):
        world.insert("late", shared.uri)
    await MEMBERSHIPS.grant("late", "member", world.nexus.containers["ws-2"])
    world.insert("late", shared.uri)
    await MEMBERSHIPS.revoke("late", world.nexus.containers["ws-2"])
    with pytest.raises(CLOSED):
        world.select("late", shared.uri)
    # No policy per person: nothing is kept in step with the members.
    with as_service_account("api"):
        names = [p.name for p in world.nexus.iam.list_policies(limit=1000).items]
    assert not [n for n in names if n.startswith("workspace.")]


@pytest.mark.asyncio
async def test_a_workspace_given_more_graphs_than_a_statement_holds_reaches_each(world):
    many = [f"urn:graph:shared{i:03}" for i in range(130)]
    for iri in (many[0], many[-1]):
        world.put(iri)
    await world.share("root", "ws-2", read=many)
    sids = world.sids("ws-2")
    assert {"GivenGraphs", "GivenGraphs2"} <= set(sids)
    assert len(world.offer("ws-2").graphs_read) == len(many)
    assert world.select("viewer2", many[0]) and world.select("viewer2", many[-1])
    with world.acting("viewer2"):
        assert graph_iam.allowed("Query", many, user="viewer2") == set(many)


# -- grant only what you hold --------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_workspace_admin_shares_only_a_graph_they_hold_and_may_stop_sharing_any(world):
    theirs = await world.create("member", "ws-1")
    world.put(theirs.uri)
    before = world.offer("ws-2")
    with pytest.raises(PermissionDeniedError):
        await world.share("admin2", "ws-2", read=[theirs.uri])
    assert world.offer("ws-2") == before
    with pytest.raises(CLOSED):
        world.select("member2", theirs.uri)
    # What they were given is never theirs to give again, even for writing.
    await world.share("root", "ws-2", read=[theirs.uri])
    with pytest.raises(PermissionDeniedError):
        await world.share("admin2", "ws-2", read=[theirs.uri], write=[theirs.uri])
    assert world.offer("ws-2").graphs_write == frozenset()
    # A graph of their own workspace is theirs to share; taking one away needs no hold.
    mine = await world.create("admin2", "ws-2", "Mine")
    kept = await world.share("admin2", "ws-2", read=[theirs.uri, mine.uri], write=[mine.uri])
    assert kept.read == sorted([theirs.uri, mine.uri]) and kept.write == [mine.uri]
    await world.share("admin2", "ws-2", read=[mine.uri])
    with pytest.raises(CLOSED):
        world.select("member2", theirs.uri)
    # An admin of both workspaces holds it: they share it.
    await MEMBERSHIPS.grant("admin", "admin", world.nexus.containers["ws-2"])
    await world.share("admin", "ws-2", read=[theirs.uri], write=[theirs.uri])
    world.insert("member2", theirs.uri)


@pytest.mark.asyncio
async def test_nexus_graphs_are_never_given_even_by_name(world):
    world.put(NEXUS_IDENTITY_GRAPH)
    await world.share("root", "ws-2", read=[NEXUS_IDENTITY_GRAPH])
    assert world.offer("ws-2").graphs_read == frozenset()
    with pytest.raises(Exceptions.GraphNotFoundError):
        world.select("viewer2", NEXUS_IDENTITY_GRAPH)


# -- every graph of the organization --------------------------------------------------------


@pytest.mark.asyncio
async def test_reading_all_reads_the_organizations_graphs_made_later_too_and_no_other(world):
    own = await world.create("member", "ws-1")
    foreign = await world.create("other", "ws-9")
    for iri in (own.uri, foreign.uri, PLATFORM, NEXUS_IDENTITY_GRAPH, SCHEMA_GRAPH):
        world.put(iri)
    await world.share("root", "ws-2", read_all=True)
    assert world.offer("ws-2").graphs_all == set(
        given_graphs.read_all_names(world.nexus.containers["ws-2"])
    )
    view = await world.view("viewer2", "ws-2")
    assert {own.uri, SCHEMA_GRAPH} <= view.readable
    assert not {foreign.uri, PLATFORM, NEXUS_IDENTITY_GRAPH} & view.readable
    assert view.writable == frozenset()
    assert world.select("viewer2", own.uri)
    for closed in (foreign.uri, PLATFORM, NEXUS_IDENTITY_GRAPH):
        with pytest.raises(CLOSED):
            world.select("viewer2", closed)
    # A graph made later in the organization is read too: a pattern, not a list.
    later = await world.create("member", "ws-1", "Later")
    world.put(later.uri)
    assert world.select("viewer2", later.uri)
    with pytest.raises(PermissionDeniedError):
        world.insert("member2", later.uri)


@pytest.mark.asyncio
async def test_reading_all_never_reaches_another_tenants_or_a_graph_not_placed_in_it(world):
    """A personal workspace reads its own and the schema graph, nobody else's; a graph
    the application graph records for a workspace but IAM has not placed yet is at the
    platform, which no organization's pattern names."""
    private = await world.create("solo1", "solo-1")
    foreign = await world.create("other", "ws-9", "Foreign")
    for graph in (private, foreign):
        world.put(graph.uri)
    with as_service_account("api"):  # the placement a restart has not made yet
        world.nexus.iam.delete_placement("triple_store", graph_iam.graph_id(foreign.uri))
    await world.share("root", "solo-2", read_all=True)
    await world.share("root", "ws-2", read_all=True)
    for user, workspace in (("solo2", "solo-2"), ("viewer2", "ws-2")):
        readable = (await world.view(user, workspace)).readable
        assert not {private.uri, foreign.uri} & readable, user
        for closed in (private.uri, foreign.uri):
            with pytest.raises(CLOSED):
                world.select(user, closed)


# -- what a workspace closes of its own ----------------------------------------------------


@pytest.mark.asyncio
async def test_a_workspace_that_may_not_create_graphs_creates_none(world):
    await world.share("admin2", "ws-2", allow_create=False)
    assert "OfferGraphsDeny" in world.sids("ws-2")
    assert (await world.view("member2", "ws-2")).can_create is False
    assert (await world.view("member", "ws-1")).can_create is True
    service = await world.service("member2", "ws-2")
    with world.acting("member2"), pytest.raises(GraphAccessError):
        await service.create_graph("ws-2", "No", None, "member2")
    # Nor through the kernel: W's own names are closed to creation.
    from naas_abi_core.engine.call_context import current_call_context

    with world.acting("member2"):
        ctx = replace(current_call_context(), container=world.nexus.containers["ws-2"])
        with use_call_context(ctx), pytest.raises(PermissionDeniedError):
            world.store.create_graph(URIRef("urn:graph:sneaky"))
    # A Deny of W's bound restricts its own admins too: lifting it is for whoever it does
    # not restrict, an admin of the organization or the platform admin (core rule).
    with pytest.raises(PermissionDeniedError):
        await world.share("admin2", "ws-2")
    assert world.offer("ws-2").graphs_no_create is True
    await world.share("oadmin", "ws-2")
    assert (await world.view("member2", "ws-2")).can_create is True


@pytest.mark.asyncio
async def test_a_workspace_that_excludes_its_own_graphs_does_not_see_them(world):
    created = await world.create("member2", "ws-2")
    kept = await world.create("member2", "ws-2", "Kept")
    for graph in (created, kept):
        world.put(graph.uri)
    saved = await world.share("admin2", "ws-2", include_owned=False, read=[kept.uri])
    assert saved.include_owned is False and saved.allow_create is False
    assert (await world.view("member2", "ws-2")).readable == {kept.uri}
    for user in ("viewer2", "member2", "admin2"):
        with pytest.raises(CLOSED):
            world.select(user, created.uri)
    assert world.select("member2", kept.uri)
    assert (await world.view("member2", "ws-2")).can_create is False
    # Included again (by whom the Deny does not restrict): read and written as before.
    with pytest.raises(PermissionDeniedError):
        await world.share("admin2", "ws-2")
    await world.share("root", "ws-2")
    assert (await world.view("member2", "ws-2")).readable == {created.uri, kept.uri}
    world.insert("member2", created.uri)


# -- Settings › Graphs -------------------------------------------------------------------


def _editor(world):
    from fastapi import FastAPI
    from naas_abi.apps.nexus.apps.api.app.services.graph.testing import acting_as_header

    app = FastAPI()
    app.include_router(resource_access.router, prefix="/api/workspaces")
    app.dependency_overrides[resource_access.get_db] = lambda: None
    app.dependency_overrides[resource_access.get_graph_service] = lambda: SimpleNamespace(
        _get_catalog_store=lambda: world.store
    )
    app.dependency_overrides[resource_access.get_ontology_service] = lambda: SimpleNamespace()
    return acting_as_header(app)


@pytest.mark.asyncio
async def test_settings_graphs_reads_and_writes_the_offer_as_the_caller(world):
    from naas_abi.apps.nexus.apps.api.app.services.graph.testing import client

    mine = await world.create("admin2", "ws-2", "Mine")
    theirs = await world.create("admin", "ws-1", "Theirs")
    world.put(theirs.uri)
    app = _editor(world)
    uri = "/api/workspaces/ws-2/resource-access/graphs"
    async with client(app, "admin2") as http:
        found = (await http.get(uri)).json()
        assert set(found) == {"data", "revision", "updated_by", "catalog"}
        assert found["data"] == WorkspaceGraphPolicyConfig().model_dump()
        assert [item["id"] for item in found["catalog"]] == [mine.uri]
        assert found["catalog"][0]["owned"] is True
        # A graph they may not drop is not on offer to them.
        refused = await http.put(uri, json={"revision": 1, "policy": {"read": [theirs.uri]}})
        assert refused.status_code == 422
        # Sharing every graph stays the platform admins'.
        everything = await http.put(uri, json={"revision": 1, "policy": {"read_all": True}})
        assert everything.status_code == 403
        assert world.offer("ws-2").graphs_all == frozenset()
        saved = await http.put(
            uri, json={"revision": 1, "policy": {"write": [mine.uri], "allow_create": False}}
        )
        assert saved.status_code == 200, saved.text
        assert saved.json()["data"]["write"] == [mine.uri]
        assert saved.json()["data"]["allow_create"] is False
    assert world.offer("ws-2").graphs_no_create is True
    async with client(app, "root") as http:
        shared = await http.put(
            uri, json={"revision": 1, "policy": {"read": [theirs.uri], "read_all": True}}
        )
        assert shared.status_code == 200, shared.text
    assert world.select("viewer2", theirs.uri)
    async with client(app, "admin2") as http:
        # The workspace holds it: on offer to take away, never to give for writing.
        listed = {item["id"] for item in (await http.get(uri)).json()["catalog"]}
        assert theirs.uri in listed
        upgrade = {"revision": 1, "policy": {"read": [theirs.uri], "write": [theirs.uri]}}
        assert (await http.put(uri, json=upgrade)).status_code == 403
        assert world.offer("ws-2").graphs_write == frozenset()
        # Leaving ``read_all`` on while taking the rest away is theirs.
        dropped = await http.put(uri, json={"revision": 1, "policy": {"read_all": True}})
        assert dropped.status_code == 200, dropped.text
    assert world.offer("ws-2").graphs_read == frozenset()
    async with client(app, "viewer2") as http:
        assert (await http.get(uri)).status_code == 403
