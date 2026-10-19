"""Every /api/graph route, driven as each role against a real IAM and kernel.

A request acts as the user it names (``X-User``), so the kernel's triple store
decides as the real stack does. A route is let in (anything but 401/403: a
handler that then fails on a thin fixture is not what is tested) or refused 403.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from naas_abi import ABIModule
from naas_abi.apps.nexus.apps.api.app.services.graph.testing import (
    acting_as_header,
    client,
    knowledge_team,
)
from naas_abi.apps.nexus.apps.api.app.services.workspaces.adapters.secondary import (
    resource_access_postgres as saved_policies,
)
from naas_abi.apps.nexus.graph_policy_config import WorkspaceGraphPolicyConfig
from naas_abi_core.engine.IEngine import IEngine
from naas_abi_core.services.triple_store.adaptors.secondary.TripleStoreService__SecondaryAdaptor__OxigraphEmbedded import (  # noqa: E501
    TripleStoreService__SecondaryAdaptor__OxigraphEmbedded as OxigraphEmbedded,
)
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService

_CONFIG = SimpleNamespace(
    configuration=SimpleNamespace(
        nexus_config=SimpleNamespace(ontology_base_uri="http://ontology.naas.ai/nexus/")
    )
)
with patch.object(ABIModule, "get_instance", return_value=_CONFIG):
    from naas_abi.apps.nexus.apps.api.app.services.graph.adapters.primary import (
        graph__primary_adapter__FastAPI as api,
    )
    from naas_abi.apps.nexus.apps.api.app.services.graph.service import GraphService

WS = "ws-1"
CLASS = "urn:Person"
THING = "urn:thing"
RDF_FILE = (
    "graph.ttl",
    b"@prefix owl: <http://www.w3.org/2002/07/owl#> . <urn:a> a owl:NamedIndividual .",
)


class _Bus:
    def publish_many(self, *_args, **_kwargs) -> None:
        return None


class FakeSession:
    def __call__(self):
        return self

    async def __aenter__(self):
        return None

    async def __aexit__(self, *_args):
        return False


def routes(g: str) -> dict[str, tuple]:
    """``(method, path, params, json, files)`` of each route, keyed by its
    permission class: ``read``, ``write`` (members), ``admin`` (clear, drop)."""
    ws = {"workspace_id": WS}
    graph = {**ws, "graph_uri": g}
    body = {**ws, "graph_uri": g}
    ind = {**body, "individual_uri": THING, "predicate_uri": "urn:p"}
    spec = {
        "mode": "list",
        "graph_uris": [g],
        "root": {"kind": "class", "class_uris": [CLASS]},
        "columns": [
            {"id": "c", "datatype": "string", "source": {"kind": "property", "predicate": "urn:p"}}
        ],
    }
    r = {
        "list": ("GET", "/list", ws, None, None),
        "roles": ("GET", "/roles", ws, None, None),
        "detail": ("GET", "/detail", {**ws, "uri": g}, None, None),
        "overview": ("GET", "/overview", graph, None, None),
        "kpis": ("GET", "/kpis", graph, None, None),
        "network-schema": ("GET", "/network/schema", graph, None, None),
        "network": ("GET", "/network", graph, None, None),
        "network-search": ("GET", "/network/search", {**graph, "query": "a"}, None, None),
        "network-parents": (
            "GET",
            "/network/parents",
            {**ws, "graph_names": g, "node_iris": THING},
            None,
            None,
        ),
        "export": ("GET", "/export", graph, None, None),
        "classes": ("GET", "/discovery/classes", graph, None, None),
        "classes-all": ("GET", "/discovery/classes/all", ws, None, None),
        "class-meta": ("GET", "/discovery/class-meta", {**graph, "class_uri": CLASS}, None, None),
        "class-dt": (
            "GET",
            "/discovery/class-datatype-properties",
            {**ws, "class_uri": CLASS},
            None,
            None,
        ),
        "class-obj": (
            "GET",
            "/discovery/class-object-properties",
            {**ws, "class_uri": CLASS},
            None,
            None,
        ),
        "columns": ("GET", "/columns", {**graph, "class_uri": CLASS}, None, None),
        "search": ("GET", "/search", {**ws, "q": "a"}, None, None),
        "explorer-catalog": ("POST", "/explorer/catalog", None, {**ws, "graph_uris": [g]}, None),
        "explorer-overview": ("POST", "/explorer/overview", None, {**ws, "graph_uris": [g]}, None),
        "explorer-instances": (
            "POST",
            "/explorer/instances",
            None,
            {**ws, "graph_uris": [g]},
            None,
        ),
        "explorer-network": ("POST", "/explorer/network", None, {**ws, "graph_uris": [g]}, None),
        "relation-targets": ("POST", "/discovery/relation-targets", None, body, None),
        "properties": ("POST", "/discovery/properties", None, body, None),
        "instances": ("POST", "/discovery/instances", None, body, None),
        "instance-detail": (
            "POST",
            "/discovery/instance-detail",
            None,
            {**ws, "graph_uri": g, "instance_uri": THING},
            None,
        ),
        "relation-types": ("POST", "/discovery/relation-types", None, body, None),
        "relations": ("POST", "/discovery/relations", None, body, None),
        "triples-export": ("POST", "/discovery/triples-export", None, {**ws, "triples": []}, None),
        "node-properties": (
            "POST",
            "/network/node-properties",
            None,
            {**body, "class_uri": CLASS},
            None,
        ),
        "node-instances": (
            "POST",
            "/network/node-instances",
            None,
            {**body, "class_uri": CLASS},
            None,
        ),
        "query": ("POST", "/query", None, {**ws, "spec": spec}, None),
        "facets": (
            "POST",
            "/query/facets",
            None,
            {**ws, "spec": spec, "target_column_id": "c"},
            None,
        ),
        "analyze": ("POST", "/analyze", None, ws, {"file": RDF_FILE}),
    }
    w = {
        "create": ("POST", "/create", None, {**ws, "label": "New"}, None),
        "update": ("POST", "/update", None, {**ws, "uri": g, "label": "Renamed"}, None),
        "cache": ("POST", "/cache/clear", ws, None, None),
        "node": ("POST", "/nodes", None, {**body, "label": "Ada"}, None),
        "node-delete": ("POST", "/nodes/delete", None, {**body, "individual_uri": THING}, None),
        "dp-add": ("POST", "/nodes/data-property/add", None, {**ind, "value": "v"}, None),
        "dp-delete": ("POST", "/nodes/data-property/delete", None, {**ind, "value": "v"}, None),
        "dp-update": (
            "POST",
            "/nodes/data-property/update",
            None,
            {**ind, "old_value": "v", "new_value": "w"},
            None,
        ),
        "op-add": ("POST", "/nodes/object-property/add", None, {**ind, "other_uri": "urn:o"}, None),
        "op-delete": (
            "POST",
            "/nodes/object-property/delete",
            None,
            {**ind, "other_uri": "urn:o"},
            None,
        ),
        "op-update": (
            "POST",
            "/nodes/object-property/update",
            None,
            {
                **body,
                "individual_uri": THING,
                "old_predicate_uri": "urn:p",
                "old_other_uri": "urn:o",
                "new_predicate_uri": "urn:p",
                "new_other_uri": "urn:n",
            },
            None,
        ),
        "import": ("POST", "/import", None, None, {"file": RDF_FILE}),
    }
    admin = {
        "clear": ("POST", "/clear", None, {**ws, "uri": g}, None),
        "delete": ("POST", "/delete", None, {**ws, "uri": g}, None),
    }
    return {"read": r, "write": w, "admin": admin}  # type: ignore[return-value]


@pytest.fixture
def team():
    with knowledge_team() as nexus:
        yield nexus


@pytest.fixture
def stack(team, tmp_path, monkeypatch):
    store = TripleStoreService(OxigraphEmbedded(str(tmp_path / "ox")))
    store.set_services(IEngine.Services(iam=team.iam, bus=_Bus()))
    policies: dict[str, WorkspaceGraphPolicyConfig] = {}

    async def saved(_db, workspace_id, _kind):
        config = policies.get(workspace_id, WorkspaceGraphPolicyConfig())
        return SimpleNamespace(data=config.model_dump(), revision=1)

    monkeypatch.setattr(saved_policies, "load_resource_policy", saved)
    from naas_abi.apps.nexus.apps.api.app.core import database

    monkeypatch.setattr(database, "AsyncSessionLocal", FakeSession())
    app = FastAPI()
    app.include_router(api.router, prefix="/api/graph")
    app.dependency_overrides[api.get_graph_service] = lambda: GraphService(lambda: store)
    acting_as_header(app)
    yield app, store, team
    OxigraphEmbedded._stores.pop(str(tmp_path / "ox"), None)


async def send(http, spec, g=None):
    method, path, params, body, files = spec
    kwargs: dict = {"params": params}
    if files is not None:
        kwargs["files"] = files
        kwargs["data"] = {**(body or {}), "workspace_id": WS, "graph_uri": g or "urn:g"}
    elif body is not None:
        kwargs["json"] = body
    return await http.request(method, "/api/graph" + path, **kwargs)


async def make_graph(app, user="admin") -> str:
    async with client(app, user) as http:
        created = await http.post("/api/graph/create", json={"workspace_id": WS, "label": "Sales"})
        assert created.status_code == 200, created.text
        return created.json()["uri"]


def allowed(response) -> bool:
    return response.status_code not in (401, 403)


@pytest.mark.asyncio
async def test_every_route_is_covered_by_the_tables(stack) -> None:
    app, _, _ = stack
    covered = {
        (spec[0], "/api/graph" + spec[1])
        for group in routes("urn:g").values()
        for spec in group.values()
    }
    declared = {
        (method, "/api/graph" + route.path)
        for route in api.router.routes
        for method in route.methods
        if route.path != "/admin/catalog"
    }
    assert declared == covered


@pytest.mark.asyncio
async def test_viewers_read_everything_that_reads_and_change_nothing(stack) -> None:
    app, _, _ = stack
    g = await make_graph(app)
    tables = routes(g)
    async with client(app, "viewer") as viewer:
        for name, spec in tables["read"].items():
            assert allowed(await send(viewer, spec, g)), name
        for group in ("write", "admin"):
            for name, spec in tables[group].items():
                response = await send(viewer, spec, g)
                assert response.status_code == 403, (name, response.text)


@pytest.mark.asyncio
async def test_members_write_and_only_admins_clear_or_drop(stack) -> None:
    app, _, _ = stack
    g = await make_graph(app)
    tables = routes(g)
    async with client(app, "member") as member:
        for group in ("read", "write"):
            for name, spec in tables[group].items():
                assert allowed(await send(member, spec, g)), name
        for name, spec in tables["admin"].items():
            assert (await send(member, spec, g)).status_code == 403, name
    async with client(app, "admin") as admin:
        for name, spec in tables["admin"].items():
            assert allowed(await send(admin, spec, g)), name


@pytest.mark.asyncio
async def test_strangers_and_other_workspaces_are_refused_everywhere(stack) -> None:
    app, _, _ = stack
    g = await make_graph(app)
    tables = routes(g)
    for user in ("stranger", "owner2", "viewer2"):
        async with client(app, user) as other:
            for group in tables.values():
                for name, spec in group.items():
                    response = await send(other, spec, g)
                    assert response.status_code == 403, (user, name, response.text)


@pytest.mark.asyncio
async def test_a_member_of_another_workspace_cannot_name_the_graph_through_their_own(stack) -> None:
    app, _, _ = stack
    g = await make_graph(app)
    async with client(app, "member2") as other:
        detail = await other.get("/api/graph/detail", params={"workspace_id": "ws-2", "uri": g})
        assert detail.status_code == 403
        kpis = await other.get("/api/graph/kpis", params={"workspace_id": "ws-2", "graph_uri": g})
        assert kpis.status_code == 403
        response = await other.post(
            "/api/graph/nodes", json={"workspace_id": "ws-2", "graph_uri": g, "label": "x"}
        )
        assert response.status_code == 403


@pytest.mark.asyncio
async def test_a_workspace_without_the_graph_feature_is_closed_to_its_members(
    tmp_path, monkeypatch
) -> None:
    # The deployment's default: only admins and owners use the graph section.
    from naas_abi.apps.nexus.apps.api.app.core import database
    from naas_abi.apps.nexus.apps.api.app.services.iam.testing import NexusIam

    monkeypatch.setattr(database, "AsyncSessionLocal", FakeSession())

    async def saved(_db, _workspace_id, _kind):
        return SimpleNamespace(data=WorkspaceGraphPolicyConfig().model_dump(), revision=1)

    monkeypatch.setattr(saved_policies, "load_resource_policy", saved)
    nexus = NexusIam()
    scope = nexus.workspace("org-1", WS)
    nexus.grant("member", "member", scope)
    nexus.grant("admin", "admin", scope)
    store = TripleStoreService(OxigraphEmbedded(str(tmp_path / "ox2")))
    store.set_services(IEngine.Services(iam=nexus.iam, bus=_Bus()))
    app = FastAPI()
    app.include_router(api.router, prefix="/api/graph")
    app.dependency_overrides[api.get_graph_service] = lambda: GraphService(lambda: store)
    acting_as_header(app)
    with nexus.installed():
        async with client(app, "member") as member:
            response = await member.get("/api/graph/list", params={"workspace_id": WS})
            assert response.status_code == 403
        async with client(app, "admin") as admin:
            assert (
                await admin.get("/api/graph/list", params={"workspace_id": WS})
            ).status_code == 200
    OxigraphEmbedded._stores.pop(str(tmp_path / "ox2"), None)
