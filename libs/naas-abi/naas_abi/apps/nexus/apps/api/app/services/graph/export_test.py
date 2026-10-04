"""Graph export streams one named graph instead of building it in memory."""

from __future__ import annotations

import threading
import unittest
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

from naas_abi.apps.nexus.apps.api.app.services.graph import access_test as access
from naas_abi.apps.nexus.apps.api.app.services.graph.access_test import (
    ALICE,
    ALPHA,
    BETA,
    REF,
    MemoryStore,
    fixtures,
    scope,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.adapters.secondary.scoped_store import (
    WorkspaceGraphStore,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.graph__schema import (
    GraphAccessError,
)
from naas_abi.apps.nexus.graph_policy_config import WorkspaceGraphPolicyConfig
from rdflib import OWL, RDF, BNode, Graph, Literal, URIRef
from rdflib.compare import isomorphic

LARGE = "urn:graph:large"


def alpha_graph(raw: MemoryStore) -> Graph:
    expected = Graph()
    for triple in raw.dataset.graph(URIRef(ALPHA)):
        expected.add(triple)
    return expected


def with_tricky_terms(raw: MemoryStore) -> MemoryStore:
    # Multi-line, quoted and tagged literals, a typed literal and a blank node.
    node = BNode()
    tricky = Graph()
    tricky.add((ALICE, URIRef("urn:note"), Literal('line one\nline "two"', lang="en")))
    tricky.add((ALICE, URIRef("urn:age"), Literal(42)))
    tricky.add((ALICE, URIRef("urn:knows"), node))
    tricky.add((node, RDF.type, OWL.NamedIndividual))
    raw.insert(tricky, URIRef(ALPHA))
    return raw


class ScopedExportTest(unittest.TestCase):
    def setUp(self):
        self.raw = fixtures()
        self.store = WorkspaceGraphStore(self.raw, scope())

    def test_export_reads_one_readable_graph(self):
        with self.store.export(URIRef(ALPHA)) as triples:
            exported = Graph()
            for triple in triples:
                exported.add(triple)
        self.assertTrue(isomorphic(exported, alpha_graph(self.raw)))

    def test_export_of_an_unreadable_graph_is_denied_before_io(self):
        with self.assertRaises(GraphAccessError):
            with self.store.export(URIRef(BETA)):
                pass
        self.assertFalse(self.raw.queries)

    def test_export_of_a_readable_but_absent_graph_is_empty(self):
        store = WorkspaceGraphStore(
            self.raw, scope(WorkspaceGraphPolicyConfig(read=["urn:graph:absent"]))
        )
        with store.export(URIRef("urn:graph:absent")) as triples:
            self.assertEqual(list(triples), [])
        self.assertFalse(self.raw.queries)

    def test_query_stream_is_scoped_like_query(self):
        with self.store.query_stream("SELECT ?s WHERE { GRAPH ?g { ?s ?p ?o } }") as result:
            subjects = {str(row["s"]) for row in result.rows}
        self.assertIn(str(ALICE), subjects)
        self.assertNotIn("urn:Secret", subjects)
        with self.assertRaises(GraphAccessError):
            with self.store.query_stream(f"SELECT ?s FROM <{BETA}> WHERE {{ ?s ?p ?o }}"):
                pass

    def test_query_stream_without_readable_graphs_never_queries(self):
        store = WorkspaceGraphStore(self.raw, scope(WorkspaceGraphPolicyConfig()))
        with store.query_stream("SELECT ?s WHERE { ?s ?p ?o }") as result:
            self.assertEqual(list(result.rows), [])
        self.assertFalse(self.raw.queries)


class OneThreadStore(MemoryStore):
    """Records the thread reading each triple, like pyoxigraph would require."""

    def __init__(self, triples: int = 0):
        super().__init__()
        self.reading_threads: set[int] = set()
        self.read = 0
        self.large = triples
        if triples:
            self.create_graph(LARGE)

    @contextmanager
    def export(self, graph_name=None):
        if str(graph_name) != LARGE:
            with super().export(graph_name) as triples:
                yield triples
            return

        def triples():
            for n in range(self.large):
                self.reading_threads.add(threading.get_ident())
                self.read += 1
                yield (URIRef(f"urn:s{n}"), RDF.type, OWL.NamedIndividual)

        yield triples()

    def query(self, query):
        if LARGE in query and "COUNT" in query:
            return [(Literal(self.large),)]  # every triple is a NamedIndividual
        return super().query(query)


class ServiceExportTest(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        access.ServiceIsolationTest.setUpClass()
        cls.service_class = access.ServiceIsolationTest.service_class

    def service(self, raw, config=None):
        return self.service_class(lambda: raw, access_scope=scope(config))

    async def collect(self, export) -> bytes:
        return b"".join([chunk async for chunk in export.chunks])

    async def test_nt_and_ttl_stream_the_same_triples_as_the_graph(self):
        raw = with_tricky_terms(fixtures())
        for fmt, parse_as in [("nt", "nt"), ("turtle", "turtle")]:
            with self.subTest(format=fmt):
                export = await self.service(raw).export_graph(
                    workspace_id="alpha", graph_uri=ALPHA, format=fmt
                )
                body = await self.collect(export)
                parsed = Graph().parse(data=body.decode(), format=parse_as)
                self.assertTrue(isomorphic(parsed, alpha_graph(raw)))
                self.assertEqual(export.triple_count, len(alpha_graph(raw)))
                # Alice and the blank node are both NamedIndividuals.
                self.assertEqual(export.named_individual_count, 2)
        self.assertIn(b"@prefix owl: <http://www.w3.org/2002/07/owl#> .", body)

    async def test_rdf_xml_keeps_the_whole_graph_path(self):
        raw = with_tricky_terms(fixtures())
        export = await self.service(raw).export_graph(
            workspace_id="alpha", graph_uri=ALPHA, format="xml"
        )
        parsed = Graph().parse(data=(await self.collect(export)).decode(), format="xml")
        self.assertTrue(isomorphic(parsed, alpha_graph(raw)))

    async def test_triples_are_read_lazily_on_one_thread(self):
        raw = OneThreadStore(triples=50_000)
        config = WorkspaceGraphPolicyConfig(write=[ALPHA], read=[REF, LARGE])
        export = await self.service(raw, config).export_graph(
            workspace_id="alpha", graph_uri=LARGE, format="nt"
        )
        self.assertEqual(export.triple_count, 50_000)
        self.assertEqual(raw.read, 0)  # nothing read before the body is
        first = await anext(export.chunks)
        self.assertTrue(first.startswith(b"<urn:s0> "))
        self.assertLess(raw.read, 50_000)  # one chunk, not the whole graph
        rest = b"".join([chunk async for chunk in export.chunks])
        self.assertEqual((first + rest).count(b"\n"), 50_000)
        self.assertEqual(len(raw.reading_threads), 1)

    async def test_unreadable_graph_is_denied_before_io(self):
        raw = fixtures()
        with self.assertRaises(GraphAccessError):
            await self.service(raw).export_graph(workspace_id="alpha", graph_uri=BETA)
        self.assertFalse(raw.queries)


class HTTPExportTest(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        access.ServiceIsolationTest.setUpClass()
        from naas_abi.apps.nexus.apps.api.app.services.graph.adapters.primary import (
            graph__primary_adapter__FastAPI as api,
        )

        cls.api = api

    async def asyncSetUp(self):
        import httpx
        from fastapi import FastAPI

        self.raw = with_tricky_terms(fixtures())
        base = access.ServiceIsolationTest.service_class(lambda: self.raw)
        app = FastAPI()
        app.include_router(self.api.router, prefix="/graph")
        app.dependency_overrides[self.api.get_graph_service] = lambda: base
        app.dependency_overrides[self.api.get_current_user_required] = lambda: SimpleNamespace(
            id="user", is_superadmin=False
        )

        async def bind(service, user, workspace):
            return service.for_scope(scope())

        self.patcher = patch.object(self.api, "workspace_graph_service", bind)
        self.patcher.start()
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        )

    async def asyncTearDown(self):
        await self.client.aclose()
        self.patcher.stop()

    async def test_export_streams_with_count_headers(self):
        for fmt, parse_as, media_type in [
            ("nt", "nt", "application/n-triples"),
            ("ttl", "turtle", "text/turtle"),
            ("owl", "xml", "application/rdf+xml"),
        ]:
            with self.subTest(format=fmt):
                response = await self.client.get(
                    "/graph/export",
                    params={"workspace_id": "alpha", "graph_uri": ALPHA, "format": fmt},
                )
                self.assertEqual(response.status_code, 200, response.text)
                self.assertTrue(response.headers["content-type"].startswith(media_type))
                self.assertEqual(
                    response.headers["x-triple-count"], str(len(alpha_graph(self.raw)))
                )
                self.assertEqual(response.headers["x-named-individual-count"], "2")
                self.assertIn("attachment", response.headers["content-disposition"])
                parsed = Graph().parse(data=response.text, format=parse_as)
                self.assertTrue(isomorphic(parsed, alpha_graph(self.raw)))

    async def test_export_of_an_unreadable_graph_is_forbidden(self):
        response = await self.client.get(
            "/graph/export", params={"workspace_id": "alpha", "graph_uri": BETA}
        )
        self.assertEqual(response.status_code, 403)
