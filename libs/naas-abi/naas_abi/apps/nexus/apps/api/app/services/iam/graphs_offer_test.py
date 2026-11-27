"""The workspaces' graph assignments move into their offers (``graphs_offer_v1``): each
workspace's effective assignment becomes the Graphs part of "<W> access"; the
``workspace.<ws>.graphs.read|write`` policies an earlier version attached to each person
go. A workspace whose policy passed the pattern limit (never written) is given its graphs
for the first time, and named.

A real IAM (``NexusIam``) with the workspaces made as Nexus makes them, the policies as
``graph_grants`` wrote them, the real triple store and graph service, and a SQLite
database for the recorded move. Nothing is mocked."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest
import pytest_asyncio
from naas_abi import ABIModule
from naas_abi.apps.nexus.apps.api.app import models  # noqa: F401 - its tables in nexus_db
from naas_abi.apps.nexus.apps.api.app.models import (
    OrganizationModel,
    UserModel,
    WorkspaceModel,
    WorkspaceResourcePolicyModel,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.adapters.secondary import graph_iam
from naas_abi.apps.nexus.apps.api.app.services.graph.adapters.secondary.workspace_policy import (
    load_workspace_scope,
)
from naas_abi.apps.nexus.apps.api.app.services.iam import given_graphs, graphs_offer
from naas_abi.apps.nexus.apps.api.app.services.iam.container_defaults import (
    CONTAINER_DEFAULTS,
    SqlDefaultsStore,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.graphs_offer import Move, policy_name
from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import MEMBERSHIPS
from naas_abi.apps.nexus.apps.api.app.services.iam.testing import NexusIam
from naas_abi.apps.nexus.apps.api.app.services.iam.workspace_offer import Offer, offer_of
from naas_abi.apps.nexus.graph_policy_config import WorkspaceGraphPolicyConfig
from naas_abi_core.engine.call_context import as_service_account, use_call_context
from naas_abi_core.engine.IEngine import IEngine
from naas_abi_core.services.iam.IAMPorts import PermissionDeniedError
from naas_abi_core.services.triple_store.adaptors.secondary.TripleStoreService__SecondaryAdaptor__OxigraphEmbedded import (  # noqa: E501
    TripleStoreService__SecondaryAdaptor__OxigraphEmbedded as OxigraphEmbedded,
)
from naas_abi_core.services.triple_store.TripleStorePorts import Exceptions
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from rdflib import Graph, Literal, URIRef
from sqlalchemy import text

_CONFIG = SimpleNamespace(
    configuration=SimpleNamespace(
        nexus_config=SimpleNamespace(ontology_base_uri="http://ontology.naas.ai/nexus/")
    )
)
with patch.object(ABIModule, "get_instance", return_value=_CONFIG):
    from naas_abi.apps.nexus.apps.api.app.services.graph.service import GraphService

OFFER = Offer.of(features=["graph"])
P = URIRef("urn:p")
CLOSED = (PermissionDeniedError, Exceptions.GraphNotFoundError)
DEFAULT = WorkspaceGraphPolicyConfig()


class _Bus:
    def publish_many(self, *_args, **_kwargs) -> None:
        return None


def _old_documents(
    config: WorkspaceGraphPolicyConfig, container: str, owned: set[str] = frozenset()
) -> tuple[dict | None, dict | None]:
    """The two documents ``graph_grants.assignment_of`` wrote (no ``read_all``)."""
    shared = set(config.read) | set(config.write)
    reading: list[dict[str, Any]] = []
    if shared:
        reading.append(
            {
                "sid": "SharedGraphsRead",
                "effect": "Allow",
                "actions": given_graphs.READ_ACTIONS,
                "resources": [p for i in sorted(shared) for p in given_graphs.anywhere_names(i)],
            }
        )
    if not (config.allow_create and config.include_owned):
        reading.append(
            {
                "sid": "NoNewGraphs",
                "effect": "Deny",
                "actions": given_graphs.CREATE_ACTIONS,
                "resources": [f"{container}/triple_store:graph/*"],
            }
        )
    if not config.include_owned and owned - shared:
        reading.append(
            {
                "sid": "OwnGraphsClosed",
                "effect": "Deny",
                "actions": given_graphs.ALL_ACTIONS,
                "resources": [given_graphs.name_in(container, i) for i in sorted(owned - shared)],
            }
        )
    writing = [
        {
            "sid": "SharedGraphsWrite",
            "effect": "Allow",
            "actions": given_graphs.WRITE_ACTIONS,
            "resources": [p for i in sorted(config.write) for p in given_graphs.anywhere_names(i)],
        }
    ]

    def document(statements: list[dict]) -> dict | None:
        return {"version": "2026-10-13", "statements": statements} if statements else None

    return document(reading), document(writing if config.write else [])


class World:
    def __init__(self, nexus: NexusIam, store: TripleStoreService) -> None:
        self.nexus = nexus
        self.store = store

    def acting(self, user: str):
        return use_call_context(self.nexus.context(user))

    def record(self, workspace: str):
        return CONTAINER_DEFAULTS._known[self.nexus.containers[workspace]]

    def move(self, workspace: str, config: WorkspaceGraphPolicyConfig = DEFAULT) -> Move:
        record = self.record(workspace)
        return Move(workspace, record.container, record.access_policy_id, config)

    def offer(self, workspace: str) -> Offer:
        with as_service_account("api"):
            return offer_of(
                self.nexus.iam.get_policy(self.record(workspace).access_policy_id).document
            )

    async def view(self, user: str, workspace: str):
        with self.acting(user):
            return await load_workspace_scope(None, self.store, workspace, user)

    async def create(self, user: str, workspace: str, label: str = "Sales"):
        scope = await self.view(user, workspace)
        service = GraphService(lambda: self.store, access_scope=scope)
        with self.acting(user):
            created = await service.create_graph(workspace, label, None, user)
        self.put(created.uri)
        return created.uri

    def put(self, iri: str) -> None:
        graph = Graph()
        graph.add((URIRef(f"{iri}/s"), P, Literal("x")))
        with as_service_account("api"):
            self.store.insert(graph, URIRef(iri))

    def select(self, user: str, iri: str):
        with self.acting(user):
            return list(self.store.query(f"SELECT ?o WHERE {{ GRAPH <{iri}> {{ ?s ?p ?o }} }}"))

    def insert(self, user: str, iri: str) -> None:
        graph = Graph()
        graph.add((URIRef(f"{iri}/{user}"), P, Literal("x")))
        with self.acting(user):
            self.store.insert(graph, URIRef(iri))

    def legacy(
        self,
        workspace: str,
        config: WorkspaceGraphPolicyConfig,
        readers: list[str],
        writers: list[str],
        *,
        owned: set[str] = frozenset(),
    ) -> None:
        """The policies ``graph_grants`` wrote for ``workspace``, attached to each person."""
        container = self.nexus.containers.get(workspace, f"abi:nexus:workspace/{workspace}")
        reading, writing = _old_documents(config, container, owned)
        with as_service_account("api"):
            for kind, document, holders in (
                ("read", reading, readers),
                ("write", writing, writers),
            ):
                if document is None:
                    continue
                policy = self.nexus.iam.create_policy(policy_name(workspace, kind), document)
                for person in holders:
                    self.nexus.iam.attach_policy(policy.id, self.nexus.principal(person))

    def left(self) -> list[str]:
        with as_service_account("api"):
            names = [p.name for p in self.nexus.iam.list_policies(limit=1000).items]
        return sorted(n for n in names if n.startswith("workspace."))


@pytest.fixture
def team():
    nexus = NexusIam(features_with_roles=False)
    with nexus.installed():
        nexus.grouped_org("org-1", "Acme")
        nexus.containers = {  # type: ignore[attr-defined]
            ws: nexus.grouped_workspace("org-1", ws, ws.title(), offer=OFFER).container
            for ws in ("ws-1", "ws-2", "ws-3")
        }
        for person in ("member", "viewer2", "member2", "admin2", "stranger"):
            nexus.user(person)
        yield nexus
    CONTAINER_DEFAULTS.forget_grouped()


@pytest_asyncio.fixture
async def world(team, tmp_path):
    await MEMBERSHIPS.grant("member", "member", team.containers["ws-1"])
    for level in ("viewer", "member", "admin"):
        await MEMBERSHIPS.grant(f"{level}2", level, team.containers["ws-2"])
    store = TripleStoreService(OxigraphEmbedded(str(tmp_path / "oxigraph")))
    store.set_services(IEngine.Services(iam=team.iam, bus=_Bus()))
    yield World(team, store)
    OxigraphEmbedded._stores.pop(str(tmp_path / "oxigraph"), None)


@pytest.mark.asyncio
async def test_each_assignment_becomes_its_workspaces_graph_sections_and_the_policies_go(world):
    shared = await world.create("member", "ws-1")
    config = WorkspaceGraphPolicyConfig(read=[shared], write=[shared])
    world.legacy("ws-2", config, ["viewer2", "member2", "admin2"], ["admin2"])
    world.legacy("ws-gone", WorkspaceGraphPolicyConfig(read=[shared]), ["stranger"], [])
    assert world.select("viewer2", shared) and world.select("stranger", shared)
    with pytest.raises(PermissionDeniedError):  # only its admins wrote it before
        world.insert("member2", shared)
    moves = [world.move("ws-1"), world.move("ws-2", config), world.move("ws-3")]

    report = graphs_offer.apply(world.nexus.iam, moves)

    assert report.to_dict() == {
        "written": ["ws-2"],
        "kept": 0,
        "waiting": [],
        "policies_deleted": 3,
        "attachments_deleted": 5,
        "widened": [],
        "failed": {},
    }
    assert world.left() == []
    assert given_graphs.iris_of(world.offer("ws-2").graphs_write) == {shared}
    assert world.offer("ws-2").features == {"graph"}
    # The offer gives it now, within each person's level, to ws-2's people only.
    assert world.select("viewer2", shared)
    with pytest.raises(PermissionDeniedError):
        world.insert("viewer2", shared)
    world.insert("member2", shared)
    with pytest.raises(CLOSED):
        world.select("stranger", shared)
    assert (await world.view("member2", "ws-2")).writable == {shared}
    # Idempotent: nothing written nor deleted again.
    again = graphs_offer.apply(world.nexus.iam, moves)
    assert (again.written, again.kept, again.policies_deleted) == ([], ["ws-2"], 0)


@pytest.mark.asyncio
async def test_a_workspace_past_the_pattern_limit_gets_every_graph_and_is_named(world):
    many = [f"urn:graph:shared{i:03}" for i in range(60)]
    for iri in (many[0], many[-1]):
        world.put(iri)
    config = WorkspaceGraphPolicyConfig(read=many)
    # 120 names: the earlier version never wrote the policy (none to delete).
    report = graphs_offer.apply(world.nexus.iam, [world.move("ws-1", config)])
    assert report.widened == ["ws-1"] and report.written == ["ws-1"]
    assert world.select("member", many[0]) and world.select("member", many[-1])
    with world.acting("member"):
        assert graph_iam.allowed("Query", many, user="member") == set(many)


@pytest.mark.asyncio
async def test_what_a_workspace_closed_moves_into_its_bound(world):
    own = await world.create("member2", "ws-2")
    config = WorkspaceGraphPolicyConfig(include_owned=False, allow_create=False)
    world.legacy("ws-2", config, ["viewer2", "member2", "admin2"], [], owned={own})
    report = graphs_offer.apply(world.nexus.iam, [world.move("ws-2", config)])
    assert report.written == ["ws-2"] and world.left() == []
    offer = world.offer("ws-2")
    assert offer.graphs_no_create
    assert given_graphs.iris_of(offer.graphs_closed) == {own, given_graphs.NEW_GRAPH}
    for user in ("viewer2", "member2", "admin2"):
        with pytest.raises(CLOSED):
            world.select(user, own)
    assert (await world.view("member2", "ws-2")).can_create is False


@pytest.mark.asyncio
async def test_a_workspace_with_no_access_policy_yet_waits_and_keeps_its_policies(world):
    shared = await world.create("member", "ws-1")
    config = WorkspaceGraphPolicyConfig(read=[shared])
    world.legacy("ws-2", config, ["viewer2"], [])
    world.legacy("ws-new", config, ["stranger"], [])
    waiting = Move("ws-new", None, None, config)
    report = graphs_offer.apply(world.nexus.iam, [world.move("ws-2", config), waiting])
    assert report.waiting == ["ws-new"] and report.written == ["ws-2"]
    assert world.left() == [policy_name("ws-new", "read")]
    assert world.select("stranger", shared)


async def _rows(db, workspaces: list[str]) -> None:
    db.add(UserModel(id="admin", name="Admin", email="a@example.org"))
    db.add(OrganizationModel(id="org-1", name="Acme", slug="acme", owner_id="admin"))
    for workspace in workspaces:
        db.add(
            WorkspaceModel(
                id=workspace,
                name=workspace,
                slug=workspace,
                owner_id="admin",
                organization_id="org-1",
            )
        )
    await db.commit()


@pytest.mark.asyncio
async def test_the_move_reads_the_saved_assignments_runs_once_and_is_recorded(world, nexus_db):
    shared = await world.create("member", "ws-1")
    config = WorkspaceGraphPolicyConfig(read=[shared])
    world.legacy("ws-2", config, ["viewer2"], [])
    async with nexus_db() as db:
        await _rows(db, ["ws-1", "ws-2", "ws-3"])
        db.add(
            WorkspaceResourcePolicyModel(
                workspace_id="ws-2",
                resource_kind="graphs",
                policy=config.model_dump_json(),
                revision=3,
            )
        )
        store = SqlDefaultsStore(db)
        for workspace in ("ws-1", "ws-2", "ws-3"):
            await store.put(world.record(workspace))
        await db.commit()
        report = await graphs_offer.migrate(db, world.nexus.iam, store=world.store)
        assert report is not None and report.written == ["ws-2"] and not report.failed
        found = await db.execute(
            text("SELECT report FROM iam_migrations WHERE name = :n"),
            {"n": graphs_offer.MIGRATION_NAME},
        )
        assert json.loads(found.scalar_one())["policies_deleted"] == 1
        assert await graphs_offer.migrate(db, world.nexus.iam, store=world.store) is None
        # What a seeded workspace made later is made with.
        made = await graphs_offer.configured_graphs(db, {"ws-2": "org-1", "ws-3": "org-1"})
        assert set(made) == {"ws-2"}
        assert given_graphs.iris_of(made["ws-2"].graphs_read) == {shared}
    assert world.left() == []
    assert world.select("viewer2", shared)
