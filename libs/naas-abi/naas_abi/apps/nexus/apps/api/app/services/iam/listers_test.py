"""naas_abi's listers: candidates for IAM's listing, read from Nexus's database
on the API's loop, and the modules' items named in the container asked."""

from __future__ import annotations

import asyncio
import threading
import uuid

import pytest
from naas_abi.apps.nexus.apps.api.app.models import (  # the tables nexus_db creates
    OrganizationMemberModel,
    OrganizationModel,
    UserModel,
    WorkspaceMemberModel,
    WorkspaceModel,
)
from naas_abi.apps.nexus.apps.api.app.services.iam import listers
from naas_abi.apps.nexus.apps.api.app.services.iam.names import (
    org_container,
    workspace_container,
)
from naas_abi_core.services.iam.listing import ListedResource, ListingQuery

ORG = org_container("org-1")
WS1 = workspace_container("org-1", "ws-1")


@pytest.fixture
def loop():
    running = asyncio.new_event_loop()
    thread = threading.Thread(target=running.run_forever, daemon=True)
    thread.start()
    yield running
    running.call_soon_threadsafe(running.stop)
    thread.join(5)
    running.close()


def test_a_lister_runs_its_query_on_the_loop_and_pages_it(loop):
    seen: list[asyncio.AbstractEventLoop] = []

    async def source(query: ListingQuery) -> list[ListedResource]:
        seen.append(asyncio.get_running_loop())
        return [ListedResource(f"{WS1}/nexus:member/{u}", u) for u in ("b", "a", "c")]

    lister = listers.OnLoop(loop, source)
    page = lister.list_resources(ListingQuery("nexus", "member", WS1, limit=2))
    assert [i.id for i in page.items] == ["a", "b"] and page.more
    assert seen == [loop]

    async def on_the_loop():
        with pytest.raises(RuntimeError, match="cannot wait"):
            lister.list_resources(ListingQuery("nexus", "member", WS1))

    asyncio.run_coroutine_threadsafe(on_the_loop(), loop).result(5)


def test_the_modules_items_are_named_in_the_container_asked(loop):
    calls = 0

    async def gather():
        nonlocal calls
        calls += 1
        return [
            {
                "module": "p",
                "agents": [{"name": "a", "display_name": "Agent A"}, {"name": "b"}],
                "apps": [],
            },
            {"module": "m", "agents": [], "apps": [{"name": "x", "description": "An app"}]},
        ]

    items = listers.ModuleItems(gather)
    agents = listers.OnLoop(loop, items.source("agent"))
    page = agents.list_resources(ListingQuery("module", "agent", WS1))
    assert [(i.name, i.id, i.label) for i in page.items] == [
        (f"{WS1}/module:agent/p/a", "p/a", "Agent A"),
        (f"{WS1}/module:agent/p/b", "p/b", "b"),
    ]
    apps = listers.OnLoop(loop, items.source("app"))
    only_m = apps.list_resources(ListingQuery("module", "app", WS1, module="m"))
    assert [(i.id, i.description) for i in only_m.items] == [("m/x", "An app")]
    assert apps.list_resources(ListingQuery("module", "app", WS1, module="p")).items == ()
    # Gathered once, reused for a while.
    assert calls == 1


def test_every_type_naas_abi_lists_has_a_lister(loop):
    assert set(listers.listers(loop)) == {
        ("nexus", "organization"),
        ("nexus", "workspace"),
        ("nexus", "member"),
        ("nexus", "feature"),
        ("nexus", "ontology"),
        ("module", "agent"),
        ("module", "app"),
        ("module", "workflow"),
        ("module", "pipeline"),
    }


@pytest.mark.asyncio
async def test_organizations_workspaces_and_members_come_from_the_database(nexus_db, monkeypatch):
    from naas_abi.apps.nexus.apps.api.app.core import database

    monkeypatch.setattr(database, "AsyncSessionLocal", nexus_db)
    async with nexus_db() as db:
        db.add_all(
            [
                UserModel(id="u-1", email="ann@example.com", name="Ann"),
                UserModel(id="u-2", email="bob@example.com", name=""),
            ]
        )
        await db.flush()
        db.add(OrganizationModel(id="org-1", name="Acme", slug="acme", owner_id="u-1"))
        await db.flush()
        db.add_all(
            [
                WorkspaceModel(
                    id="ws-1", name="Sales", slug="sales", owner_id="u-1", organization_id="org-1"
                ),
                WorkspaceModel(id="ws-p", name="Mine", slug="mine", owner_id="u-2"),
            ]
        )
        await db.flush()
        db.add_all(
            [
                OrganizationMemberModel(
                    id=str(uuid.uuid4()), organization_id="org-1", user_id="u-1", role="owner"
                ),
                WorkspaceMemberModel(
                    id=str(uuid.uuid4()), workspace_id="ws-1", user_id="u-2", role="member"
                ),
            ]
        )
        await db.commit()

    orgs = await listers.organizations(ListingQuery("nexus", "organization"))
    assert [(i.name, i.label) for i in orgs] == [(ORG, "Acme")]
    in_org = await listers.workspaces(ListingQuery("nexus", "workspace", ORG))
    assert [(i.name, i.label) for i in in_org] == [(WS1, "Sales")]
    every = await listers.workspaces(ListingQuery("nexus", "workspace"))
    assert {i.name for i in every} == {WS1, workspace_container(None, "ws-p")}
    at_org = await listers.members(ListingQuery("nexus", "member", ORG))
    assert sorted((i.name, i.label) for i in at_org) == [
        (f"{ORG}/nexus:member/u-1", "Ann"),
        (f"{WS1}/nexus:member/u-2", "bob@example.com"),
    ]
    at_ws = await listers.members(ListingQuery("nexus", "member", WS1))
    assert [(i.id, i.description) for i in at_ws] == [("u-2", "bob@example.com")]


def test_ontologies_are_listed_every_one_above_a_workspace_and_its_enabled_ones_in_it(
    loop, monkeypatch
):
    from contextlib import asynccontextmanager
    from types import SimpleNamespace

    from naas_abi.apps.nexus.apps.api.app.core import database
    from naas_abi.apps.nexus.apps.api.app.services import registry
    from naas_abi.apps.nexus.apps.api.app.services.workspaces.adapters.secondary import (
        resource_access_postgres,
    )
    from naas_abi_core.services.iam.names import PLATFORM

    files = [
        SimpleNamespace(path="/o/ontologies/BFO.ttl", name="BFO core", module_name="core"),
        SimpleNamespace(path="/o/ontologies/Agent.ttl", name="Agent", module_name="core"),
    ]
    asked: list[object] = []

    async def list_ontology_files(catalog_refs=None):
        asked.append(catalog_refs)
        return files if catalog_refs is None else [f for f in files if f.path in catalog_refs]

    service = SimpleNamespace(ontology=SimpleNamespace(list_ontology_files=list_ontology_files))
    monkeypatch.setattr(registry.ServiceRegistry, "instance", classmethod(lambda cls: service))

    @asynccontextmanager
    async def session():
        yield None

    async def load(db, workspace, kind):
        assert (workspace, kind) == ("ws-1", "ontologies")
        return SimpleNamespace(data={"enabled": ["/o/ontologies/BFO.ttl"]})

    monkeypatch.setattr(database, "AsyncSessionLocal", session)
    monkeypatch.setattr(resource_access_postgres, "load_resource_policy", load)
    lister = listers.OnLoop(loop, listers.ontologies)
    at_org = lister.list_resources(ListingQuery("nexus", "ontology", ORG))
    assert [(i.name, i.label) for i in at_org.items] == [
        (f"{ORG}/nexus:ontology/%2Fo%2Fontologies%2FAgent.ttl", "Agent"),
        (f"{ORG}/nexus:ontology/%2Fo%2Fontologies%2FBFO.ttl", "BFO core"),
    ]
    assert [
        i.id for i in lister.list_resources(ListingQuery("nexus", "ontology", PLATFORM)).items
    ] == [
        "/o/ontologies/Agent.ttl",
        "/o/ontologies/BFO.ttl",
    ]
    in_ws = lister.list_resources(ListingQuery("nexus", "ontology", WS1))
    assert [i.id for i in in_ws.items] == ["/o/ontologies/BFO.ttl"]
    assert asked == [None, None, ["/o/ontologies/BFO.ttl"]]
    # Another module's container holds no ontology.
    project = f"{WS1}/crm:project/p1"
    assert lister.list_resources(ListingQuery("nexus", "ontology", project)).items == ()
