"""Workspace catalog boundaries, exercised without a live server or database."""

import asyncio
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import get_current_user_required
from naas_abi.apps.nexus.apps.api.app.services.graph.testing import (
    acting_as_header,
    client,
    knowledge_team,
)
from naas_abi.apps.nexus.apps.api.app.services.ontology import service as ontology
from naas_abi.apps.nexus.apps.api.app.services.ontology.adapters.primary import (
    ontology__primary_adapter__FastAPI as http,
)
from naas_abi.apps.nexus.apps.api.app.services.ontology.adapters.primary.ontology__primary_adapter__dependencies import (
    get_ontology_service,
)
from naas_abi.apps.nexus.apps.api.app.services.ontology.ontology_imports import (
    clear_catalog_import_caches,
    load_catalog_import_graph,
)
from rdflib import Graph, URIRef
from rdflib.namespace import RDFS

PREFIXES = """@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix abi: <http://ontology.naas.ai/abi/> .
"""


@pytest.fixture
def team():
    with knowledge_team() as nexus:
        yield nexus


@pytest.fixture
def ontology_app():
    service = AsyncMock()
    service.list_ontology_files.return_value = []
    app = FastAPI()
    app.include_router(http.router, prefix="/api/ontology")
    app.dependency_overrides[get_ontology_service] = lambda: service
    icons = SimpleNamespace(
        list_icons=AsyncMock(return_value=[]), save_icon=AsyncMock(return_value=None)
    )
    app.dependency_overrides[http.get_ontology_icons_service] = lambda: icons
    acting_as_header(app)
    with patch.object(
        http, "_catalog_refs_for_workspace", new=AsyncMock(return_value=["fixture:Public.ttl"])
    ):
        yield app, service


READS = [
    "",
    "/dictionary",
    "/classes",
    "/relationships",
    "/ontologies",
    "/overview/stats?ontology_path=x",
    "/overview/stats/all",
    "/counts/types",
    "/overview/graph",
    "/overview/parents?ontology_path=x&class_iris=urn:c",
    "/overview/hierarchy?ontology_path=x&class_iris=urn:c",
    "/process-slices?path=x",
    "/export?ontology_path=x",
    "/icons",
]
# (method, route, body): state changes of the workspace's ontology.
WRITES = [
    ("POST", "/entity", {"name": "E"}),
    ("POST", "/relationship", {"name": "R"}),
    ("DELETE", "/entity-1", None),
    ("POST", "/import", {"content": "x", "filename": "x.ttl"}),
    (
        "PUT",
        "/icons",
        {"kind": "entity", "resource_id": "urn:term", "icon": "material-symbols-light:public"},
    ),
]
# Refreshing the caches of the ontology section is for administrators.
ADMIN = [("POST", "/cache/clear"), ("POST", "/bfo-bucket/refresh")]


def _url(route: str, workspace: str) -> str:
    return "/api/ontology" + route + ("&" if "?" in route else "?") + f"workspace_id={workspace}"


def _body(route: str) -> dict | None:
    return {"iri": "urn:c"} if route == "/bfo-bucket/refresh" else None


@pytest.mark.asyncio
@pytest.mark.parametrize("user", ["viewer", "member", "admin", "owner"])
async def test_every_role_reads_the_catalog_of_its_workspace(team, ontology_app, user) -> None:
    app, service = ontology_app
    async with client(app, user) as http_client:
        for route in READS:
            response = await http_client.get(_url(route, "ws-1"))
            assert response.status_code not in (401, 403), (user, route, response.text)
        # Which workspace is named matters: ws-2 is not theirs.
        for route in READS:
            response = await http_client.get(_url(route, "ws-2"))
            assert response.status_code == 403, (user, route)


@pytest.mark.asyncio
async def test_a_stranger_reads_nothing_and_no_workspace_means_no_answer(
    team, ontology_app
) -> None:
    app, service = ontology_app
    async with client(app, "stranger") as http_client:
        for route in READS:
            assert (await http_client.get(_url(route, "ws-1"))).status_code == 403, route
        assert (await http_client.get("/api/ontology/ontologies")).status_code == 422
    service.list_ontology_files.assert_not_awaited()


@pytest.mark.asyncio
async def test_only_members_change_the_ontology_and_only_admins_refresh_it(
    team, ontology_app
) -> None:
    app, _ = ontology_app
    async with client(app, "viewer") as viewer:
        for method, route, body in WRITES:
            response = await viewer.request(method, _url(route, "ws-1"), json=body)
            assert response.status_code == 403, route
        for method, route in ADMIN:
            response = await viewer.request(method, _url(route, "ws-1"), json=_body(route))
            assert response.status_code == 403, route
    async with client(app, "member") as member:
        for method, route, body in WRITES:
            response = await member.request(method, _url(route, "ws-1"), json=body)
            assert response.status_code not in (401, 403), (route, response.text)
        for method, route in ADMIN:
            response = await member.request(method, _url(route, "ws-1"), json=_body(route))
            assert response.status_code == 403, route
    async with client(app, "admin") as admin:
        for method, route in ADMIN:
            response = await admin.request(method, _url(route, "ws-1"), json=_body(route))
            assert response.status_code not in (401, 403), (route, response.text)


@pytest.mark.asyncio
async def test_icons_say_whether_the_caller_may_edit_them(team, ontology_app) -> None:
    app, _ = ontology_app
    for user, can_edit in {"viewer": False, "member": True, "admin": True}.items():
        async with client(app, user) as http_client:
            response = await http_client.get(_url("/icons", "ws-1"))
            assert response.json()["can_edit"] is can_edit, user


@pytest.mark.asyncio
async def test_a_workspace_without_the_ontology_feature_is_closed(ontology_app) -> None:
    # The deployment's default: members and viewers do not use the ontology section.
    from naas_abi.apps.nexus.apps.api.app.services.iam.testing import NexusIam

    app, _ = ontology_app
    nexus = NexusIam()
    scope = nexus.workspace("org-1", "ws-1")
    nexus.grant("member", "member", scope)
    nexus.grant("admin", "admin", scope)
    with nexus.installed():
        async with client(app, "member") as member:
            response = await member.get(_url("/ontologies", "ws-1"))
            assert response.status_code == 403
            assert "feature" in response.json()["detail"]
        async with client(app, "admin") as admin:
            assert (await admin.get(_url("/ontologies", "ws-1"))).status_code == 200


@pytest.mark.asyncio
async def test_a_deny_on_one_ontology_takes_it_out_of_every_read(team) -> None:
    """Bob may not get the Agent ontology (a Deny at his workspace): it is not
    listed, its path is not found, and the routes that read every enabled
    ontology read the others only. The simulator's answer is what every route
    applies."""
    from naas_abi_core.engine.call_context import as_service_account
    from naas_abi_core.services.iam.policy import POLICY_VERSION

    bfo, agent = "/o/ontologies/modules/BFO.ttl", "/o/ontologies/modules/AgentOntology.ttl"

    def file(path: str, name: str) -> SimpleNamespace:
        return SimpleNamespace(
            path=path,
            name=name,
            module_name="core",
            submodule_name=None,
            description=None,
            license=None,
            contributors=[],
            date=None,
            imports=[],
        )

    files = {bfo: file(bfo, "BFO core"), agent: file(agent, "Agent")}

    async def list_ontology_files(catalog_refs=None):
        refs = catalog_refs if catalog_refs is not None else list(files)
        # A ref is a path, or ``<module>:<file>`` (``ontology_matches_seed``).
        named = {r.rsplit(":", 1)[-1].lower() for r in refs}
        return [
            item for path, item in files.items() if path in refs or Path(path).name.lower() in named
        ]

    async def list_classes(ontology_path, catalog_refs=None):
        known = [f.path for f in await list_ontology_files(catalog_refs)]
        if ontology_path is not None and ontology_path not in known:
            raise ontology.OntologyPathNotFoundError(ontology_path)
        return []

    service = SimpleNamespace(
        list_ontology_files=AsyncMock(side_effect=list_ontology_files),
        list_classes=AsyncMock(side_effect=list_classes),
        workspace_dictionary=AsyncMock(return_value={}),
        list_items=AsyncMock(return_value=[]),
    )
    app = FastAPI()
    app.include_router(http.router, prefix="/api/ontology")
    app.dependency_overrides[get_ontology_service] = lambda: service
    acting_as_header(app)
    with as_service_account("engine"):
        deny = team.iam.create_policy(
            "Bob: BFO only",
            {
                "version": POLICY_VERSION,
                "statements": [
                    {
                        "effect": "Deny",
                        "actions": ["nexus:GetOntology", "nexus:ExportOntology"],
                        "resources": ["${scope}/nexus:ontology/*AgentOntology.ttl"],
                    }
                ],
            },
        )
        team.iam.attach_policy(deny.id, team.principal("member"), team.workspace("org-1", "ws-1"))
    enabled = ["core:bfo.ttl", "core:agentontology.ttl"]
    with patch.object(http, "_catalog_refs_for_workspace", new=AsyncMock(return_value=enabled)):
        async with client(app, "member") as bob:
            listed = await bob.get(_url("/ontologies", "ws-1"))
            assert [i["path"] for i in listed.json()["items"]] == [bfo]
            denied = await bob.get(_url(f"/classes?ontology_path={agent}", "ws-1"))
            assert denied.status_code == 404, denied.text
            assert (
                await bob.get(_url(f"/overview/stats?ontology_path={agent}", "ws-1"))
            ).status_code == 403
            assert (await bob.get(_url(f"/classes?ontology_path={bfo}", "ws-1"))).status_code == 200
            for route in ("", "/dictionary", "/classes"):
                assert (await bob.get(_url(route, "ws-1"))).status_code == 200, route
        # Every read went through the readable files only.
        for method in (service.list_classes, service.workspace_dictionary, service.list_items):
            assert all(call.kwargs["catalog_refs"] == [bfo] for call in method.await_args_list), (
                method
            )
        # Another member, not denied, reads both.
        async with client(app, "member2") as other:
            listed = await other.get(_url("/ontologies", "ws-2"))
            assert [i["path"] for i in listed.json()["items"]] == [bfo, agent]


class HttpScopeTests(unittest.IsolatedAsyncioTestCase):
    async def test_saved_empty_assignments_deny(self) -> None:
        from unittest.mock import MagicMock

        from naas_abi.apps.nexus.apps.api.app.core import database
        from naas_abi.apps.nexus.apps.api.app.services.workspaces.adapters.secondary import (
            resource_access_postgres as policies,
        )

        session = MagicMock()
        session.return_value.__aenter__ = AsyncMock(return_value=SimpleNamespace())
        session.return_value.__aexit__ = AsyncMock(return_value=False)
        with (
            patch.object(database, "AsyncSessionLocal", session),
            patch.object(
                policies,
                "load_resource_policy",
                AsyncMock(return_value=SimpleNamespace(data={"enabled": []})),
            ) as load,
        ):
            self.assertEqual(await http._catalog_refs_for_workspace("allowed"), [])
            self.assertEqual(load.call_args.args[1:], ("allowed", "ontologies"))

    async def asyncSetUp(self) -> None:
        self.nexus = knowledge_team()
        self.nexus.__enter__()
        self.addCleanup(self.nexus.__exit__, None, None, None)
        self.app = FastAPI()
        self.app.include_router(http.router, prefix="/api/ontology")
        self.service = SimpleNamespace(list_ontology_files=AsyncMock(return_value=[]))
        self.app.dependency_overrides[get_ontology_service] = lambda: self.service
        acting_as_header(self.app)
        self.client = client(self.app, "viewer")

    async def asyncTearDown(self) -> None:
        await self.client.aclose()

    async def test_anonymous_cannot_read_catalog(self) -> None:
        def anonymous() -> None:
            raise HTTPException(401)

        self.app.dependency_overrides[get_current_user_required] = anonymous
        response = await self.client.get("/api/ontology/ontologies?workspace_id=ws-1")
        self.assertEqual(response.status_code, 401)
        self.service.list_ontology_files.assert_not_awaited()

    async def test_private_paths_are_rejected_before_reads_and_export(self) -> None:
        with patch.object(
            http,
            "_catalog_refs_for_workspace",
            new=AsyncMock(return_value=["fixture:Public.ttl"]),
        ):
            for route in ["/overview/stats", "/export", "/overview/parents", "/overview/hierarchy"]:
                with self.subTest(route=route):
                    response = await self.client.get(
                        "/api/ontology" + route,
                        params={
                            "workspace_id": "ws-1",
                            "ontology_path": "/private.ttl",
                            "class_iris": "urn:class",
                        },
                    )
                    self.assertEqual(response.status_code, 404, response.text)

    async def test_expansion_forwards_workspace_catalog_to_service(self) -> None:
        self.service.list_ontology_files.return_value = [SimpleNamespace(path="/allowed.ttl")]
        for route, method in [
            ("parents", "get_class_parents"),
            ("hierarchy", "get_subclassof_hierarchy"),
        ]:
            handler = AsyncMock(return_value=SimpleNamespace(nodes=[], edges=[]))
            setattr(self.service, method, handler)
            with patch.object(
                http,
                "_catalog_refs_for_workspace",
                new=AsyncMock(return_value=["fixture:Public.ttl"]),
            ):
                response = await self.client.get(
                    "/api/ontology/overview/" + route,
                    params={
                        "workspace_id": "ws-1",
                        "ontology_path": "/allowed.ttl",
                        "class_iris": "urn:child",
                    },
                )
                self.assertEqual(response.status_code, 200, response.text)
                # The workspace's enabled files the caller may get, by path.
                handler.assert_awaited_once_with(
                    class_iris=["urn:child"],
                    ontology_path="/allowed.ttl",
                    catalog_refs=["/allowed.ttl"],
                )


class ImportBoundaryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.root = Path(self.temp.name) / "fixture" / "ontologies" / "modules"
        self.root.mkdir(parents=True)
        self.public = self.write(
            "Public",
            '<urn:public> a owl:Ontology; rdfs:label "Public"; owl:imports <urn:private>, <urn:shared>, <https://not-fetched.invalid/ontology> . <urn:child> a owl:Class; rdfs:subClassOf <urn:private-type>, <urn:shared-type> .',
        )
        self.private = self.write(
            "Private",
            '<urn:private> a owl:Ontology; rdfs:label "Private" . <urn:private-type> a owl:Class; rdfs:label "Private label"; skos:definition "Private definition" .',
        )
        self.shared = self.write(
            "Shared",
            '<urn:shared> a owl:Ontology; rdfs:label "Shared"; owl:imports <urn:public> . <urn:shared-type> a owl:Class; rdfs:label "Shared label" .',
        )
        module = SimpleNamespace(
            ontologies=list(map(str, [self.public, self.private, self.shared])),
            engine=SimpleNamespace(modules={}),
        )
        self.service = ontology.OntologyService(abi_module_getter=lambda: module)

    def tearDown(self) -> None:
        clear_catalog_import_caches()
        self.temp.cleanup()

    async def test_a_path_names_exactly_its_file_as_a_catalog_ref(self) -> None:
        """``ontology_catalog_scope`` narrows a workspace's refs to the paths the
        caller may read: a path selects its file alone."""
        every = await self.service.list_ontology_files(
            catalog_refs=["fixture:Public.ttl", "fixture:Private.ttl", "fixture:Shared.ttl"]
        )
        self.assertEqual(len(every), 3)
        only = await self.service.list_ontology_files(catalog_refs=[str(self.public)])
        self.assertEqual([item.path for item in only], [str(self.public)])
        self.assertEqual(await self.service.list_ontology_files(catalog_refs=[]), [])

    def write(self, name: str, content: str) -> Path:
        path = self.root / f"{name}.ttl"
        path.write_text(PREFIXES + content)
        return path

    def test_imports_cycles_and_cache_follow_permission_snapshot(self) -> None:
        original_parse = Graph.parse
        reads = []

        def local_parse(graph: Graph, source: str, *args: Any, **kwargs: Any) -> Graph:
            reads.append(str(source))
            self.assertIn(str(source), list(map(str, [self.public, self.private, self.shared])))
            return original_parse(graph, source, *args, **kwargs)

        with patch.object(Graph, "parse", local_parse):
            wide = load_catalog_import_graph(
                str(self.public), list(map(str, [self.public, self.private, self.shared])), {}
            )
            self.assertEqual(
                str(wide.value(URIRef("urn:private-type"), RDFS.label)), "Private label"
            )
            narrow = load_catalog_import_graph(
                str(self.public), list(map(str, [self.public, self.shared])), {}
            )
            self.assertIsNone(narrow.value(URIRef("urn:private-type"), RDFS.label))
            self.assertEqual(
                str(narrow.value(URIRef("urn:shared-type"), RDFS.label)), "Shared label"
            )
            self.shared.write_text(
                self.shared.read_text().replace("Shared label", "Updated shared label")
            )
            updated = load_catalog_import_graph(
                str(self.public), list(map(str, [self.public, self.shared])), {}
            )
            self.assertEqual(
                str(updated.value(URIRef("urn:shared-type"), RDFS.label)), "Updated shared label"
            )
        self.assertTrue(reads)
        with self.assertRaises(ValueError):
            load_catalog_import_graph(str(self.private), [str(self.public)], {})

    async def test_graph_parents_and_hierarchy_do_not_use_prior_global_imports(self) -> None:
        ontology._populate_dynamic_uri_map([str(self.private)])
        for method in [self.service.get_class_parents, self.service.get_subclassof_hierarchy]:
            with self.subTest(method=method.__name__):
                result = await method(
                    ["urn:child"],
                    str(self.public),
                    catalog_refs=["fixture:Public.ttl", "fixture:Shared.ttl"],
                )
                labels = {node.label for node in result.nodes}
                self.assertIn("Shared label", labels)
                self.assertNotIn("Private label", labels)

    async def test_excluded_malformed_file_is_not_parsed(self) -> None:
        self.private.write_text("malformed Turtle")
        files = await self.service.list_ontology_files(["fixture:Public.ttl"])
        self.assertEqual([file.path for file in files], [str(self.public)])
        self.assertEqual(await self.service.list_ontology_files([]), [])

    async def test_overview_does_not_enrich_from_global_triple_store(self) -> None:
        with patch.object(
            self.service,
            "_get_triple_store",
            side_effect=AssertionError("Global store must not be consulted"),
        ):
            result = await self.service.get_overview_graph(
                ontology_path=None, catalog_refs=["fixture:Public.ttl"]
            )
            self.assertTrue(result.nodes)
            self.assertNotIn("Private label", {node.label for node in result.nodes})

    def test_explicit_shared_aliases_and_relocated_package_imports(self) -> None:
        self.public.write_text(
            PREFIXES
            + "<urn:public> a owl:Ontology; owl:imports <https://example.org/shared>, <file:///old/host/pkg/ontologies/Dependency.ttl> ."
        )
        dependency = self.write(
            "Dependency",
            '<urn:dependency> a owl:Ontology; abi:pythonPackage "pkg"; abi:ontologyResource "ontologies/Dependency.ttl" . <urn:dependency-type> a owl:Class; rdfs:label "Dependency label" .',
        )
        graph = load_catalog_import_graph(
            str(self.public),
            list(map(str, [self.public, self.shared, dependency])),
            {"https://example.org/shared": "mid-level/Shared.ttl"},
        )
        self.assertEqual(str(graph.value(URIRef("urn:shared-type"), RDFS.label)), "Shared label")
        self.assertEqual(
            str(graph.value(URIRef("urn:dependency-type"), RDFS.label)), "Dependency label"
        )

    def test_aliased_imports_resolve_from_bundled_dir_only(self) -> None:
        # Standard upper ontologies (BFO, CCO) ship with the package, outside any
        # workspace catalog. An aliased import reaches them, transitively; an
        # IRI that is not aliased never does.
        bundled = Path(self.temp.name) / "bundled"
        (bundled / "mid-level").mkdir(parents=True)
        (bundled / "top-level").mkdir(parents=True)
        (bundled / "mid-level" / "Upper.ttl").write_text(
            PREFIXES
            + "<https://example.org/upper> a owl:Ontology; owl:imports <https://example.org/root> . "
            + '<urn:upper-type> a owl:Class; rdfs:label "Upper label"; rdfs:subClassOf <urn:root-type> .'
        )
        (bundled / "top-level" / "Root.ttl").write_text(
            PREFIXES
            + "<https://example.org/root> a owl:Ontology . "
            + '<urn:root-type> a owl:Class; rdfs:label "Root label" .'
        )
        (bundled / "mid-level" / "Unaliased.ttl").write_text(
            PREFIXES + '<urn:unaliased-type> a owl:Class; rdfs:label "Unaliased label" .'
        )
        self.public.write_text(
            PREFIXES
            + "<urn:public> a owl:Ontology; owl:imports <https://example.org/upper>, <https://example.org/unaliased> ."
        )
        graph = load_catalog_import_graph(
            str(self.public),
            [str(self.public)],
            {
                "https://example.org/upper": "mid-level/Upper.ttl",
                "https://example.org/root": "top-level/Root.ttl",
            },
            bundled_dir=str(bundled),
        )
        self.assertEqual(str(graph.value(URIRef("urn:upper-type"), RDFS.label)), "Upper label")
        self.assertEqual(str(graph.value(URIRef("urn:root-type"), RDFS.label)), "Root label")
        self.assertIsNone(graph.value(URIRef("urn:unaliased-type"), RDFS.label))
        # Without a bundled dir, the alias stays an unresolved reference.
        clear_catalog_import_caches()
        bare = load_catalog_import_graph(
            str(self.public),
            [str(self.public)],
            {"https://example.org/upper": "mid-level/Upper.ttl"},
        )
        self.assertIsNone(bare.value(URIRef("urn:upper-type"), RDFS.label))


@pytest.mark.asyncio
async def test_a_request_lists_each_catalog_once() -> None:
    """``remember_listings``: within one request (its context) a listing of the same
    refs is parsed once; another request lists again."""
    import contextvars

    service = ontology.OntologyService(abi_module_getter=lambda: None)
    parsed: list[object] = []

    async def listing(catalog_refs):
        parsed.append(catalog_refs)
        return [SimpleNamespace(path="/a.ttl")]

    service._list_ontology_files = listing  # type: ignore[method-assign]

    async def one_request() -> None:
        ontology.remember_listings()
        await service.list_ontology_files(catalog_refs=["x"])
        await service.list_ontology_files(catalog_refs=["x"])
        ontology.remember_listing(["/a.ttl"], [SimpleNamespace(path="/a.ttl")])
        await service.list_ontology_files(catalog_refs=["/a.ttl"])

    await contextvars.copy_context().run(lambda: asyncio.ensure_future(one_request()))
    assert parsed == [["x"]]
    await service.list_ontology_files(catalog_refs=["x"])
    assert parsed == [["x"], ["x"]]


@pytest.mark.asyncio
async def test_an_icon_is_set_only_on_what_the_caller_reads(team) -> None:
    """Bob may not get the Agent ontology: its file is not among what he may set an
    icon on (the icons service then answers 404, as for any file outside the
    workspace), BFO's is."""
    from naas_abi_core.engine.call_context import as_service_account
    from naas_abi_core.services.iam.policy import POLICY_VERSION

    bfo, agent = "/o/ontologies/modules/BFO.ttl", "/o/ontologies/modules/AgentOntology.ttl"
    files = [SimpleNamespace(path=bfo), SimpleNamespace(path=agent)]

    async def list_ontology_files(catalog_refs=None):
        return [
            f
            for f in files
            if catalog_refs is None or f.path in catalog_refs or catalog_refs == ["*"]
        ]

    service = SimpleNamespace(
        list_ontology_files=AsyncMock(side_effect=list_ontology_files),
        workspace_dictionary=AsyncMock(return_value={"items": []}),
    )
    saved: list[tuple] = []
    icons = SimpleNamespace(
        list_icons=AsyncMock(return_value=[]),
        save_icon=AsyncMock(side_effect=lambda *args: saved.append(args)),
    )
    app = FastAPI()
    app.include_router(http.router, prefix="/api/ontology")
    app.dependency_overrides[get_ontology_service] = lambda: service
    app.dependency_overrides[http.get_ontology_icons_service] = lambda: icons
    acting_as_header(app)
    with as_service_account("engine"):
        deny = team.iam.create_policy(
            "Bob: BFO only",
            {
                "version": POLICY_VERSION,
                "statements": [
                    {
                        "effect": "Deny",
                        "actions": ["nexus:GetOntology"],
                        "resources": ["${scope}/nexus:ontology/*AgentOntology.ttl"],
                    }
                ],
            },
        )
        team.iam.attach_policy(deny.id, team.principal("member"), team.workspace("org-1", "ws-1"))
    with patch.object(http, "_catalog_refs_for_workspace", new=AsyncMock(return_value=["*"])):
        async with client(app, "member") as bob:
            for path in (bfo, agent):
                await bob.put(
                    _url("/icons", "ws-1"),
                    json={
                        "kind": "file",
                        "resource_id": path,
                        "icon": "material-symbols-light:public",
                    },
                )
    allowed_sets = [call.args[2] for call in icons.save_icon.await_args_list]
    assert allowed_sets and all(("file", agent) not in allowed for allowed in allowed_sets)
    assert all(("file", bfo) in allowed for allowed in allowed_sets)
