"""Workspace catalog boundaries, exercised without a live server or database."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import get_current_user_required
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


class HttpScopeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.app = FastAPI()
        self.app.include_router(http.router, prefix="/api/ontology")
        self.service = SimpleNamespace(list_ontology_files=AsyncMock(return_value=[]))
        self.app.dependency_overrides[get_current_user_required] = lambda: SimpleNamespace(
            id="viewer"
        )
        self.app.dependency_overrides[get_ontology_service] = lambda: self.service
        self.client = AsyncClient(transport=ASGITransport(self.app), base_url="http://test")

    async def asyncTearDown(self) -> None:
        await self.client.aclose()

    async def test_every_catalog_read_requires_authorized_workspace(self) -> None:
        routes = [
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
            "/export?ontology_path=x",
        ]
        for route in routes + ["/cache/clear"]:
            with (
                self.subTest(route=route),
                patch.object(
                    http, "require_workspace_access", new=AsyncMock(side_effect=HTTPException(403))
                ) as access,
            ):
                method = "POST" if route == "/cache/clear" else "GET"
                url = "/api/ontology" + http.router.prefix + route
                response = await self.client.request(method, url)
                self.assertEqual(response.status_code, 422, response.text)
                access.assert_not_awaited()
                response = await self.client.request(
                    method, url + ("&" if "?" in url else "?") + "workspace_id=denied"
                )
                self.assertEqual(response.status_code, 403, response.text)
        self.service.list_ontology_files.assert_not_awaited()

    async def test_anonymous_cannot_read_catalog(self) -> None:
        def anonymous() -> None:
            raise HTTPException(401)

        self.app.dependency_overrides[get_current_user_required] = anonymous
        response = await self.client.get("/api/ontology/ontologies?workspace_id=allowed")
        self.assertEqual(response.status_code, 401)
        self.service.list_ontology_files.assert_not_awaited()

    async def test_viewer_reads_only_explicit_catalog(self) -> None:
        with (
            patch.object(http, "require_workspace_access", new=AsyncMock()) as access,
            patch.object(
                http,
                "_catalog_refs_for_workspace",
                new=AsyncMock(return_value=["fixture:Public.ttl"]),
            ),
        ):
            response = await self.client.get("/api/ontology/ontologies?workspace_id=allowed")
            self.assertEqual(response.status_code, 200, response.text)
            access.assert_awaited_once_with("viewer", "allowed")
            self.service.list_ontology_files.assert_awaited_once_with(
                catalog_refs=["fixture:Public.ttl"]
            )

    async def test_missing_null_and_empty_workspace_seeds_deny(self) -> None:
        for seed in [None, SimpleNamespace(ontologies=None), SimpleNamespace(ontologies=[])]:
            with (
                self.subTest(seed=seed),
                patch.object(http, "_workspace_slug", new=AsyncMock(return_value="fixture")),
                patch.object(http, "workspace_seed_for_slug", return_value=seed),
            ):
                self.assertEqual(await http._catalog_refs_for_workspace("allowed"), [])

    async def test_private_paths_are_rejected_before_reads_and_export(self) -> None:
        with (
            patch.object(http, "require_workspace_access", new=AsyncMock()),
            patch.object(
                http,
                "_catalog_refs_for_workspace",
                new=AsyncMock(return_value=["fixture:Public.ttl"]),
            ),
        ):
            for route in ["/overview/stats", "/export", "/overview/parents", "/overview/hierarchy"]:
                with self.subTest(route=route):
                    response = await self.client.get(
                        "/api/ontology" + route,
                        params={
                            "workspace_id": "allowed",
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
            with (
                patch.object(http, "require_workspace_access", new=AsyncMock()),
                patch.object(
                    http,
                    "_catalog_refs_for_workspace",
                    new=AsyncMock(return_value=["fixture:Public.ttl"]),
                ),
            ):
                response = await self.client.get(
                    "/api/ontology/overview/" + route,
                    params={
                        "workspace_id": "allowed",
                        "ontology_path": "/allowed.ttl",
                        "class_iris": "urn:child",
                    },
                )
                self.assertEqual(response.status_code, 200, response.text)
                handler.assert_awaited_once_with(
                    class_iris=["urn:child"],
                    ontology_path="/allowed.ttl",
                    catalog_refs=["fixture:Public.ttl"],
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
