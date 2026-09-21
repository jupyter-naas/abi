"""Workspace isolation using synthetic RDF only; never starts an engine or database."""

from __future__ import annotations

import inspect
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from naas_abi.apps.nexus.apps.api.app.services.graph.access import GraphAccessScope
from naas_abi.apps.nexus.apps.api.app.services.graph.adapters.secondary.scoped_store import (
    WorkspaceGraphStore,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.adapters.secondary.workspace_policy import (
    config_for_workspace,
    owned_graphs,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.graph__schema import (
    GraphAccessError,
)
from naas_abi.apps.nexus.graph_policy_config import (
    NEXUS_GRAPH,
    SCHEMA_GRAPH,
    WorkspaceGraphPolicyConfig,
)
from rdflib import OWL, RDF, RDFS, Dataset, Graph, Literal, URIRef

ALPHA, BETA, REF = "urn:graph:alpha", "urn:graph:beta", "urn:graph:reference"
PERSON, ALICE, SECRET = map(URIRef, ["urn:Person", "urn:Alice", "urn:Secret"])


class MemoryStore:
    def __init__(self):
        self.dataset = Dataset()
        self.names: set[URIRef] = set()
        self.queries: list[str] = []
        self.lock = threading.RLock()

    def query(self, query):
        with self.lock:
            self.queries.append(query)
            result = self.dataset.query(query)
            if result.type == "SELECT":
                result.bindings = list(result.bindings)
            return result

    def list_graphs(self):
        return list(self.names)

    def create_graph(self, graph_name):
        self.names.add(URIRef(graph_name))
        self.dataset.graph(URIRef(graph_name))

    def insert(self, triples, graph_name):
        self.create_graph(graph_name)
        for triple in triples:
            self.dataset.graph(URIRef(graph_name)).add(triple)

    def remove(self, triples, graph_name):
        for triple in triples:
            self.dataset.graph(URIRef(graph_name)).remove(triple)

    def clear_graph(self, graph_name):
        self.dataset.graph(URIRef(graph_name)).remove((None, None, None))

    def drop_graph(self, graph_name):
        self.dataset.remove_graph(URIRef(graph_name))
        self.names.discard(URIRef(graph_name))


def fixtures():
    store = MemoryStore()
    for uri, subject, label in [
        (ALPHA, ALICE, "Alice"),
        (BETA, SECRET, "Secret person in beta graph"),
        (REF, URIRef("urn:Code"), "Code"),
    ]:
        g = Graph()
        g.add((subject, RDF.type, OWL.NamedIndividual))
        g.add((subject, RDF.type, PERSON))
        g.add((subject, RDFS.label, Literal(label)))
        store.insert(g, URIRef(uri))
    g = Graph()
    g.add((PERSON, RDFS.label, Literal("Private schema label")))
    store.insert(g, URIRef(SCHEMA_GRAPH))
    g = Graph()
    g.add((SECRET, RDFS.label, Literal("Private application metadata")))
    store.insert(g, URIRef(NEXUS_GRAPH))
    return store


def scope(config=None, role="member", ws="alpha", owned=()):
    return GraphAccessScope.resolve(
        ws,
        config or WorkspaceGraphPolicyConfig(write=[ALPHA], read=[REF]),
        set(owned),
        role,
    )


class PolicyTest(unittest.TestCase):
    def test_missing_grants_expose_only_owned(self):
        s = scope(WorkspaceGraphPolicyConfig(), owned=[ALPHA])
        self.assertEqual(s.readable, {ALPHA})
        self.assertEqual(scope(WorkspaceGraphPolicyConfig()).readable, set())

    def test_explicit_disable_and_viewer(self):
        s = scope(
            WorkspaceGraphPolicyConfig(include_owned=False, allow_create=False),
            owned=[ALPHA],
        )
        self.assertFalse(s.readable)
        self.assertFalse(s.allow_create)
        self.assertFalse(scope(WorkspaceGraphPolicyConfig(include_owned=False)).allow_create)
        s = scope(role="viewer")
        self.assertEqual(s.readable, {ALPHA, REF})
        self.assertFalse(s.writable)
        self.assertFalse(s.allow_create)

    def test_shared_read_only_and_wrong_workspace(self):
        s = scope()
        s.require("alpha", [REF])
        for ws, graphs, write in [
            ("alpha", [REF], True),
            ("beta", [ALPHA], False),
            ("alpha", [BETA], False),
            ("alpha", [NEXUS_GRAPH], False),
        ]:
            with (
                self.subTest(ws=ws, graphs=graphs, write=write),
                self.assertRaises(GraphAccessError),
            ):
                s.require(ws, graphs, write=write)

    def test_invalid_configuration_is_rejected(self):
        from pydantic import ValidationError

        for cfg in [
            {"read": ["*"]},
            {"read": ["urn:graph:*"]},
            {"read": [NEXUS_GRAPH]},
            {"write": [SCHEMA_GRAPH]},
            {"read": ["urn:g> ?s ?p ?o"]},
            {"unknown": True},
        ]:
            with self.subTest(cfg=cfg), self.assertRaises(ValidationError):
                WorkspaceGraphPolicyConfig(**cfg)

    def test_config_uses_organization_and_workspace_identity(self):
        def org(slug, graph):
            return SimpleNamespace(
                slug=slug,
                workspaces=[
                    SimpleNamespace(slug="team", graphs=WorkspaceGraphPolicyConfig(read=[graph]))
                ],
            )

        settings = SimpleNamespace(organizations=[org("one", ALPHA), org("two", BETA)])
        self.assertEqual(config_for_workspace(settings, "two", "team").read, [BETA])
        self.assertEqual(config_for_workspace(settings, "unknown", "team").read, [])
        settings.organizations.append(org("two", ALPHA))
        with self.assertRaises(GraphAccessError):
            config_for_workspace(settings, "two", "team")

    def test_policy_fingerprint_changes_on_revocation(self):
        self.assertNotEqual(
            scope().cache_key, scope(WorkspaceGraphPolicyConfig(write=[ALPHA])).cache_key
        )
        self.assertNotEqual(scope().cache_key, scope(ws="other").cache_key)


class ScopedStoreTest(unittest.TestCase):
    def setUp(self):
        self.raw = fixtures()
        self.store = WorkspaceGraphStore(self.raw, scope())

    def test_variable_graph_and_default_union_are_scoped(self):
        for query in [
            "SELECT ?s WHERE { GRAPH ?g { ?s ?p ?o } }",
            "SELECT ?s WHERE { ?s ?p ?o }",
        ]:
            subjects = {str(row.s) for row in self.store.query(query)}
            self.assertIn(str(ALICE), subjects)
            self.assertNotIn(str(SECRET), subjects)

    def test_explicit_graph_subquery_construct_and_ask(self):
        self.assertFalse(
            list(self.store.query(f"SELECT ?s WHERE {{ GRAPH <{BETA}> {{ ?s ?p ?o }} }}"))
        )
        self.assertFalse(
            self.store.query(f"ASK WHERE {{ GRAPH <{BETA}> {{ ?s ?p ?o }} }}").askAnswer
        )
        self.assertEqual(
            len(
                self.store.query(
                    f"CONSTRUCT {{ ?s ?p ?o }} WHERE {{ GRAPH <{BETA}> {{ ?s ?p ?o }} }}"
                ).graph
            ),
            0,
        )
        self.assertFalse(
            list(
                self.store.query(
                    f"SELECT ?s WHERE {{ {{ SELECT ?s WHERE {{ GRAPH <{BETA}> {{ ?s ?p ?o }} }} }} }}"
                )
            )
        )

    def test_schema_and_nexus_are_not_implicit(self):
        for uri in [SCHEMA_GRAPH, NEXUS_GRAPH]:
            self.assertFalse(
                list(self.store.query(f"SELECT ?s WHERE {{ GRAPH <{uri}> {{ ?s ?p ?o }} }}"))
            )
        s = WorkspaceGraphStore(self.raw, scope(WorkspaceGraphPolicyConfig(read=[SCHEMA_GRAPH])))
        self.assertTrue(
            list(s.query(f"SELECT ?s WHERE {{ GRAPH <{SCHEMA_GRAPH}> {{ ?s ?p ?o }} }}"))
        )

    def test_federation_or_dataset_override_denied(self):
        for query in [
            f"SELECT ?s FROM <{BETA}> WHERE {{ ?s ?p ?o }}",
            f"SELECT ?s WHERE {{ SERVICE <{BETA}> {{ ?s ?p ?o }} }}",
            f"SELECT ?s WHERE {{ {{ SELECT ?s WHERE {{ SERVICE <{BETA}> {{ ?s ?p ?o }} }} }} }}",
        ]:
            with self.subTest(query=query), self.assertRaises(GraphAccessError):
                self.store.query(query)
        self.assertFalse(self.raw.queries)

    def test_keywords_in_literals_and_iris_are_not_structure(self):
        query = 'SELECT ("WHERE FROM SERVICE" AS ?label) ?s WHERE { GRAPH ?g { ?s ?p ?o FILTER(?o != "WHERE") } }'
        self.assertTrue(list(self.store.query(query)))
        self.assertTrue(
            list(
                self.store.query(
                    "PREFIX where: <urn:where:> SELECT ?where WHERE { GRAPH ?g { ?where ?p ?o } }"
                )
            )
        )

    def test_empty_or_absent_grant_never_queries_or_fetches(self):
        for config in [
            WorkspaceGraphPolicyConfig(),
            WorkspaceGraphPolicyConfig(read=["http://invalid.example/absent"]),
        ]:
            s = WorkspaceGraphStore(self.raw, scope(config))
            self.assertFalse(list(s.query("SELECT ?s WHERE { GRAPH ?g { ?s ?p ?o } }")))
        self.assertFalse(self.raw.queries)

    def test_mutations_require_write(self):
        for name in ["insert", "remove", "clear_graph", "drop_graph"]:
            args = (Graph(),) if name in ["insert", "remove"] else ()
            with self.subTest(name=name), self.assertRaises(GraphAccessError):
                getattr(self.store, name)(*args, graph_name=URIRef(REF))


class ServiceIsolationTest(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        from naas_abi import ABIModule

        config = SimpleNamespace(
            configuration=SimpleNamespace(
                nexus_config=SimpleNamespace(ontology_base_uri="http://ontology.naas.ai/nexus/")
            )
        )
        with patch.object(ABIModule, "get_instance", return_value=config):
            from naas_abi.apps.nexus.apps.api.app.services.graph.service import (
                GraphService,
            )
        cls.service_class = GraphService

    def setUp(self):
        self.raw = fixtures()
        self.service = self.service_class(lambda: self.raw, access_scope=scope())

    async def test_list_uses_policy_not_store_scan(self):
        missing = "urn:graph:policy-only"
        access = scope(
            WorkspaceGraphPolicyConfig(write=[missing], include_owned=False)
        )
        svc = self.service_class(lambda: self.raw, access_scope=access)
        self.raw.list_graphs = lambda: (_ for _ in ()).throw(
            AssertionError("list_graphs must not scan the store")
        )
        packs = await svc.list_graphs("alpha")
        self.assertEqual({g.uri for p in packs for g in p.graphs}, {missing})

    async def test_catalog_overview_and_detail_isolate(self):
        packs = await self.service.list_graphs("alpha")
        self.assertEqual({g.uri for p in packs for g in p.graphs}, {ALPHA, REF})
        summary_empty = await self.service.explorer_overview("alpha", [])
        self.assertEqual(summary_empty["kpis"]["instances"], 0)
        summary = await self.service.explorer_overview("alpha", [ALPHA, REF])
        self.assertEqual(summary["kpis"]["instances"], 2)
        rows = await self.service.explorer_instances("alpha", [ALPHA], [], "", 0, 50)
        self.assertEqual([r["uri"] for r in rows["items"]], [str(ALICE)])
        detail = await self.service.discover_instance_detail("alpha", [ALPHA], str(SECRET))
        self.assertFalse(detail.data_properties)

    async def test_unbound_service_denies_and_cross_workspace_denies(self):
        for svc, ws in [
            (self.service_class(lambda: self.raw), "alpha"),
            (self.service, "beta"),
        ]:
            with self.assertRaises(GraphAccessError):
                await svc.list_graphs(ws)
        self.assertFalse(self.raw.queries)

    async def test_all_graph_entrypoints_deny_before_io_or_cache(self):
        for name, method in inspect.getmembers(self.service, inspect.ismethod):
            if name.startswith("_") or not inspect.iscoroutinefunction(method):
                continue
            signature = inspect.signature(method)
            if "workspace_id" not in signature.parameters:
                continue
            if not any(
                k in signature.parameters for k in ["graph_uri", "graph_names", "graph_uris"]
            ):
                continue
            args = {}
            for key, param in signature.parameters.items():
                if key == "workspace_id":
                    args[key] = "alpha"
                elif key == "graph_uri":
                    args[key] = BETA
                elif key in ["graph_names", "graph_uris"]:
                    args[key] = [BETA]
                elif param.default is inspect.Parameter.empty:
                    args[key] = [] if key.endswith(("s", "iris")) else "urn:value"
            with self.subTest(method=name), self.assertRaises(GraphAccessError):
                await method(**args)
        self.assertFalse(self.raw.queries)

    async def test_created_graphs_have_persistent_workspace_ownership_and_unique_ids(
        self,
    ):
        other = self.service_class(lambda: self.raw, access_scope=scope(ws="beta"))
        a = await self.service.create_graph("alpha", "Same name", None, "user")
        b = await other.create_graph("beta", "Same name", None, "user")
        self.assertNotEqual(a.uri, b.uri)
        self.assertEqual(owned_graphs(self.raw, "alpha"), {a.uri})
        self.assertEqual(owned_graphs(self.raw, "beta"), {b.uri})
        # Fresh request / process reads ownership from persistent metadata.
        access = scope(WorkspaceGraphPolicyConfig(), owned=owned_graphs(self.raw, "alpha"))
        fresh = self.service_class(lambda: self.raw, access_scope=access)
        self.assertEqual({g.uri for p in await fresh.list_graphs("alpha") for g in p.graphs}, {a.uri})
        await fresh.update_graph("alpha", a.uri, "Renamed", None)
        self.assertEqual(owned_graphs(self.raw, "alpha"), {a.uri})

    async def test_viewer_and_read_only_mutations_denied(self):
        viewer = self.service_class(lambda: self.raw, access_scope=scope(role="viewer"))
        for operation in [
            viewer.create_graph("alpha", "X", None, "user"),
            viewer.clear_graph("alpha", ALPHA),
            self.service.clear_graph("alpha", REF),
        ]:
            with self.assertRaises(GraphAccessError):
                await operation
        self.assertFalse(self.raw.queries)

    async def test_old_schema_cache_cannot_leak_after_revocation(self):
        from naas_abi.apps.nexus.apps.api.app.services.graph.service import (
            _get_ontology_label,
        )

        granted = self.service_class(
            lambda: self.raw,
            access_scope=scope(WorkspaceGraphPolicyConfig(read=[SCHEMA_GRAPH])),
        )
        self.assertEqual(
            _get_ontology_label(granted._get_triple_store(), str(PERSON)),
            "Private schema label",
        )
        self.assertNotEqual(
            _get_ontology_label(self.service._get_triple_store(), str(PERSON)),
            "Private schema label",
        )

    async def test_composer_checks_policy_before_cached_results(self):
        from naas_abi.apps.nexus.apps.api.app.services.graph.query.adapters.secondary.graph_query__secondary_adapter__triplestore import (
            GraphQueryTripleStoreAdapter,
        )
        from naas_abi.apps.nexus.apps.api.app.services.graph.query.query__schema import (
            ClassAnchor,
            ListSpec,
        )
        from naas_abi.apps.nexus.apps.api.app.services.graph.query.service import (
            CountCache,
            GraphQueryService,
        )

        class ExplodingCache(CountCache):
            def fetch(self, key):
                raise AssertionError("authorization must happen first")

        service = GraphQueryService(
            GraphQueryTripleStoreAdapter(self.service._get_triple_store()),
            owned_graphs=lambda _: set(scope().readable),
            system_graphs=set(),
            page_cache=ExplodingCache(),
        )
        spec = ListSpec(graph_uris=(BETA,), root=ClassAnchor(class_uris=(str(PERSON),)), columns=())
        with self.assertRaises(GraphAccessError):
            await service.run_query(spec=spec, workspace_id="alpha")


class HTTPPolicyTest(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        ServiceIsolationTest.setUpClass()
        from naas_abi.apps.nexus.apps.api.app.services.graph.adapters.primary import (
            graph__primary_adapter__FastAPI as api,
        )

        cls.api = api

    async def asyncSetUp(self):
        import httpx
        from fastapi import FastAPI, HTTPException

        self.raw = fixtures()
        base = ServiceIsolationTest.service_class(lambda: self.raw)
        app = FastAPI()
        app.include_router(self.api.router, prefix="/graph")
        app.dependency_overrides[self.api.get_graph_service] = lambda: base
        app.dependency_overrides[self.api.get_current_user_required] = lambda: SimpleNamespace(
            id="user", is_superadmin=False
        )

        async def bind(service, user, workspace):
            if workspace != "alpha":
                raise HTTPException(403, "Workspace unavailable")
            return service.for_scope(scope())

        self.patcher = patch.object(self.api, "workspace_graph_service", bind)
        self.patcher.start()
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        )

    async def asyncTearDown(self):
        await self.client.aclose()
        self.patcher.stop()

    async def test_direct_urls_and_mutations_cannot_escape(self):
        cases = [
            ("GET", "/detail", {"uri": BETA}),
            ("GET", "/kpis", {"graph_uri": BETA}),
            ("GET", "/network", {"graph_uri": BETA}),
            ("GET", "/export", {"graph_uri": BETA}),
            ("GET", "/discovery/classes", {"graph_uri": BETA}),
            ("POST", "/clear", {"uri": BETA}),
            ("POST", "/delete", {"uri": BETA}),
            (
                "POST",
                "/nodes",
                {"graph_uri": BETA, "label": "X", "class_uri": str(PERSON)},
            ),
            ("POST", "/explorer/overview", {"graph_uris": [ALPHA, BETA]}),
            ("POST", "/explorer/instances", {"graph_uris": [BETA]}),
            (
                "POST",
                "/discovery/instance-detail",
                {"graph_uris": [BETA], "instance_uri": str(SECRET)},
            ),
        ]
        for method, url, data in cases:
            data = {"workspace_id": "alpha", **data}
            kwargs = {"params": data} if method == "GET" else {"json": data}
            with self.subTest(url=url):
                result = await self.client.request(method, "/graph" + url, **kwargs)
                self.assertEqual(result.status_code, 403, result.text)
        self.assertFalse(self.raw.queries)

    async def test_import_denies_before_parsing(self):
        result = await self.client.post(
            "/graph/import",
            data={"workspace_id": "alpha", "graph_uri": BETA},
            files={"file": ("invalid.ttl", b"not RDF")},
        )
        self.assertEqual(result.status_code, 403, result.text)
        self.assertFalse(self.raw.queries)

    async def test_admin_inventory_denies_regular_members(self):
        result = await self.client.get("/graph/admin/catalog")
        self.assertEqual(result.status_code, 403, result.text)
        self.assertFalse(self.raw.queries)

    async def test_catalog_permissions_and_create_result(self):
        result = await self.client.get("/graph/list", params={"workspace_id": "alpha"})
        self.assertEqual(result.status_code, 200, result.text)
        graphs = {g["uri"]: g for pack in result.json() for g in pack["graphs"]}
        self.assertEqual(set(graphs), {ALPHA, REF})
        self.assertTrue(graphs[ALPHA]["can_write"])
        self.assertFalse(graphs[REF]["can_write"])
        result = await self.client.post(
            "/graph/create", json={"workspace_id": "alpha", "label": "New"}
        )
        self.assertEqual(result.status_code, 200, result.text)
        self.assertTrue(result.json()["can_write"])
        self.assertIn(result.json()["uri"], owned_graphs(self.raw, "alpha"))

    async def test_workspace_cache_clear_requires_context(self):
        result = await self.client.post("/graph/cache/clear")
        self.assertEqual(result.status_code, 422)
        result = await self.client.post("/graph/cache/clear", params={"workspace_id": "beta"})
        self.assertEqual(result.status_code, 403)


class LegacyPolicyTest(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        ServiceIsolationTest.setUpClass()

    async def test_view_previews_and_options_use_same_grants(self):
        from naas_abi.apps.nexus.apps.api.app.services.view.service import ViewService

        raw = fixtures()
        service = ViewService(
            triple_store_getter=lambda: WorkspaceGraphStore(raw, scope()),
            access_scope=scope(),
        )
        for request in [
            service.list_graph_filter_options(graph_names=[BETA]),
            service.preview_graph_filters(graph_names=[BETA], filters=[], limit=10),
        ]:
            with self.assertRaises(GraphAccessError):
                await request
        self.assertFalse(raw.queries)

    async def test_saved_view_checks_graph_before_network(self):
        from unittest.mock import AsyncMock

        from naas_abi.apps.nexus.apps.api.app.services.view.service import ViewService

        raw = fixtures()
        service = ViewService(
            triple_store_getter=lambda: WorkspaceGraphStore(raw, scope()),
            catalog_store_getter=lambda: raw,
            access_scope=scope(),
        )
        service.get_view = AsyncMock(
            return_value={"kind": "filter", "graph_names": [BETA], "graph_filters": []}
        )
        with self.assertRaises(GraphAccessError):
            await service.get_view_network("alpha", "saved-before-revocation")
        self.assertFalse(raw.queries)

    async def test_saved_view_resolves_catalog_filters_after_graph_grant(self):
        from unittest.mock import AsyncMock, patch

        from naas_abi.apps.nexus.apps.api.app.services.view.service import ViewService
        from rdflib import Literal

        raw = fixtures()
        filter_uri = "http://ontology.naas.ai/nexus/filter/demo"
        meta = Graph()
        meta.add((URIRef(filter_uri), RDF.type, URIRef("http://ontology.naas.ai/nexus/GraphFilter")))
        meta.add((URIRef(filter_uri), URIRef("http://ontology.naas.ai/nexus/predicate_uri"), RDF.type))
        meta.add((URIRef(filter_uri), RDFS.label, Literal("Demo filter")))
        raw.insert(meta, URIRef(NEXUS_GRAPH))
        access = scope(owned=[ALPHA])
        service = ViewService(
            triple_store_getter=lambda: WorkspaceGraphStore(raw, access),
            catalog_store_getter=lambda: raw,
            access_scope=access,
        )
        service.get_view = AsyncMock(
            return_value={
                "kind": "filter",
                "graph_names": [ALPHA],
                "graph_filters": [filter_uri],
            }
        )
        with patch(
            "naas_abi.apps.nexus.apps.api.app.services.view.service._list_individuals",
            return_value=SimpleNamespace(nodes=[], edges=[]),
        ) as listed:
            await service.get_view_network("alpha", "saved-with-filters")
        self.assertEqual(listed.call_args.kwargs["graph_filters"][0]["uri"], filter_uri)
        self.assertEqual(
            listed.call_args.kwargs["graph_filters"][0]["predicate_uri"],
            str(RDF.type),
        )

    async def test_workspace_membership_denied_before_policy_or_catalog_access(self):
        from unittest.mock import AsyncMock, Mock

        from fastapi import HTTPException
        from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary import (
            auth__primary_adapter__dependencies as auth,
        )
        from naas_abi.apps.nexus.apps.api.app.services.graph.adapters.primary.graph__primary_adapter__dependencies import (
            workspace_graph_service,
        )

        graph = Mock()
        with patch.object(
            auth, "require_workspace_access", AsyncMock(side_effect=HTTPException(403))
        ):
            with self.assertRaises(HTTPException):
                await workspace_graph_service(graph, "outsider", "alpha")
        graph._get_catalog_store.assert_not_called()

    async def test_legacy_network_route_binds_scope_before_execution(self):
        from unittest.mock import AsyncMock

        from naas_abi.apps.nexus.apps.api.app.api.endpoints import view

        service = SimpleNamespace(
            get_view_network=AsyncMock(return_value=SimpleNamespace(nodes=[], edges=[]))
        )
        factory = AsyncMock(return_value=service)
        with patch.object(view, "_get_scoped_view_service", factory):
            await view.get_view_network(
                None, "saved", "alpha", 10, SimpleNamespace(id="member"), None
            )
        factory.assert_awaited_once_with(None, "member", "alpha")
        service.get_view_network.assert_awaited_once_with(
            workspace_id="alpha", view_id="saved", limit=10
        )


class EmbeddedAdapterPolicyTest(unittest.TestCase):
    def test_named_and_default_datasets_on_oxigraph(self):
        import tempfile

        from naas_abi_core.services.triple_store.adaptors.secondary.TripleStoreService__SecondaryAdaptor__OxigraphEmbedded import (
            TripleStoreService__SecondaryAdaptor__OxigraphEmbedded as Adapter,
        )

        try:
            import pyoxigraph  # noqa: F401
        except ImportError:
            self.skipTest("pyoxigraph is optional")
        with tempfile.TemporaryDirectory(prefix="graph-policy-") as directory:
            raw = Adapter(directory)
            try:
                fixture = fixtures()
                for name in fixture.names:
                    raw.insert(fixture.dataset.graph(name), name)
                store = WorkspaceGraphStore(raw, scope())
                for query in [
                    "SELECT ?s WHERE { ?s ?p ?o }",
                    "SELECT ?s WHERE { GRAPH ?g { ?s ?p ?o } }",
                ]:
                    subjects = {str(row.s) for row in store.query(query)}
                    self.assertIn(str(ALICE), subjects)
                    self.assertNotIn(str(SECRET), subjects)
                self.assertFalse(
                    list(store.query(f"SELECT ?s WHERE {{ GRAPH <{BETA}> {{ ?s ?p ?o }} }}"))
                )
                self.assertFalse(
                    store.query(f"ASK WHERE {{ GRAPH <{BETA}> {{ ?s ?p ?o }} }}").askAnswer
                )
                exported = store.query("CONSTRUCT { ?s ?p ?o } WHERE { GRAPH ?g { ?s ?p ?o } }")
                self.assertIsInstance(exported, Graph)
                self.assertIn((ALICE, RDF.type, PERSON), exported)
                self.assertNotIn((SECRET, RDF.type, PERSON), exported)
            finally:
                Adapter._stores.pop(directory, None)


class CatalogReadPolicyTest(unittest.IsolatedAsyncioTestCase):
    def test_catalog_read_is_explicit_and_does_not_grant_write(self):
        catalog = {ALPHA, BETA, REF, SCHEMA_GRAPH, NEXUS_GRAPH}
        enabled = WorkspaceGraphPolicyConfig(read_all=True)
        actual = GraphAccessScope.resolve("staff", enabled, {REF}, "member", catalog=catalog)
        self.assertEqual(actual.readable, catalog - {NEXUS_GRAPH})
        self.assertEqual(actual.writable, {REF})
        viewer = GraphAccessScope.resolve("staff", enabled, {REF}, "viewer", catalog=catalog)
        self.assertEqual(viewer.readable, actual.readable)
        self.assertFalse(viewer.writable)
        self.assertFalse(viewer.allow_create)
        restricted = GraphAccessScope.resolve(
            "alpha", WorkspaceGraphPolicyConfig(), {ALPHA}, "member", catalog=catalog
        )
        self.assertEqual(restricted.readable, {ALPHA})
        with self.assertRaises(GraphAccessError):
            restricted.require("alpha", [BETA])
        with self.assertRaises(GraphAccessError):
            actual.require("staff", [BETA], write=True)

    async def test_configured_staff_sees_legacy_and_new_graphs_on_next_request(self):
        from unittest.mock import AsyncMock

        from naas_abi.apps.nexus.apps.api.app.services.graph.adapters.secondary import (
            workspace_policy as policy,
        )

        raw = fixtures()
        registered = Graph()
        registered.add(
            (
                URIRef("urn:empty-legacy"),
                RDF.type,
                URIRef("http://ontology.naas.ai/nexus/KnowledgeGraph"),
            )
        )
        raw.insert(registered, URIRef(NEXUS_GRAPH))
        from naas_abi.apps.nexus.apps.api.app.services.workspaces.adapters.secondary import (
            resource_access_postgres as saved_policies,
        )

        async def saved_policy(db, workspace_id, kind):
            return SimpleNamespace(data=WorkspaceGraphPolicyConfig(read_all=workspace_id == "staff-id").model_dump())

        db = SimpleNamespace()
        with patch.object(saved_policies, "load_resource_policy", new=AsyncMock(side_effect=saved_policy)):
            first = await policy.load_workspace_scope(db, raw, "staff-id", "member")
            self.assertEqual(first.readable, {ALPHA, BETA, REF, SCHEMA_GRAPH, "urn:empty-legacy"})
            self.assertFalse(first.writable)
            raw.create_graph("urn:newly-added")
            second = await policy.load_workspace_scope(db, raw, "staff-id", "member")
            self.assertIn("urn:newly-added", second.readable)
            self.assertNotEqual(first.cache_key, second.cache_key)
            other = await policy.load_workspace_scope(db, raw, "alpha-id", "member")
            self.assertFalse(other.readable)
            different_org = await policy.load_workspace_scope(db, raw, "other-staff", "member")
            self.assertFalse(different_org.readable)

    def test_inventory_lists_catalog_read_grants(self):
        from naas_abi.apps.nexus.apps.api.app.services.graph.adapters.secondary.workspace_policy import (
            catalog_inventory,
        )

        raw = fixtures()
        settings = SimpleNamespace(
            organizations=[
                SimpleNamespace(
                    slug="org",
                    workspaces=[
                        SimpleNamespace(
                            slug="staff", graphs=WorkspaceGraphPolicyConfig(read_all=True)
                        ),
                    ],
                )
            ]
        )
        items = catalog_inventory(raw, settings)
        self.assertEqual({item["uri"] for item in items}, {ALPHA, BETA, REF, SCHEMA_GRAPH})
        for item in items:
            self.assertEqual(item["grants"], [{"workspace": "org/staff", "access": "read"}])
