"""Graph filter previews (ViewService) count on the store instead of holding
every triple. Kept beside access_test: importing the view package needs the
graph service, which access_test imports with ABIModule patched."""

from __future__ import annotations

import re
import threading
import unittest

from naas_abi.apps.nexus.apps.api.app.services.graph import access_test as access
from naas_abi.apps.nexus.apps.api.app.services.graph.access_test import ALPHA, REF, scope
from naas_abi.apps.nexus.apps.api.app.services.graph.adapters.secondary.scoped_store import (
    WorkspaceGraphStore,
)
from rdflib import OWL, RDF, RDFS, Graph, Literal, URIRef

EX = "http://example.org/"
A, B, C = URIRef(EX + "a"), URIRef(EX + "b"), URIRef(EX + "c")
KNOWS, AGE, PERSON = URIRef(EX + "knows"), URIRef(EX + "age"), URIRef(EX + "Person")


def preview_fixture() -> access.MemoryStore:
    raw = access.fixtures()  # Alice in alpha, Code in reference: urn: subjects
    alpha, reference = Graph(), Graph()
    alpha.add((A, KNOWS, B))
    alpha.add((A, RDFS.label, Literal("A")))
    alpha.add((B, RDF.type, PERSON))
    alpha.add((A, RDF.type, OWL.NamedIndividual))  # never previewed
    reference.add((A, KNOWS, B))  # the same triple in two graphs counts once
    reference.add((C, AGE, Literal(3)))
    raw.insert(alpha, URIRef(ALPHA))
    raw.insert(reference, URIRef(REF))
    return raw


class PreviewTest(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        access.ServiceIsolationTest.setUpClass()  # imports the graph service
        from naas_abi.apps.nexus.apps.api.app.services.view.service import ViewService

        cls.view_service = ViewService

    def setUp(self):
        self.raw = preview_fixture()
        self.threads: set[int] = set()
        query = self.raw.query

        def recording(sparql):
            self.threads.add(threading.get_ident())
            return query(sparql)

        self.raw.query = recording
        self.service = self.view_service(
            triple_store_getter=lambda: WorkspaceGraphStore(self.raw, scope()),
            access_scope=scope(),
        )

    async def test_counts_and_rows_without_filters(self):
        result = await self.service.preview_graph_filters(graph_names=[], filters=[], limit=3)

        self.assertEqual(
            (
                result["count"],
                result["object_properties_count"],
                result["data_properties_count"],
                result["individual_count"],
            ),
            # 8 triples: Alice and Code (type, label), a knows b, a label,
            # b type, c age. One object property (knows), four literals, and
            # three http(s) nodes: a, b, c.
            (8, 1, 4, 3),
        )
        self.assertEqual(len(result["rows"]), 3)
        for row in result["rows"]:
            self.assertEqual(set(row), {"subject", "predicate", "object"})
            self.assertNotEqual(row["object"], "NamedIndividual")

    async def test_filters_are_combined_and_deduplicated(self):
        result = await self.service.preview_graph_filters(
            graph_names=[ALPHA, REF],
            filters=[{"predicate_uri": str(KNOWS)}, {"subject_uri": str(A)}],
            limit=10,
        )

        # a knows b (matched by both filters, in both graphs) and a label "A".
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["object_properties_count"], 1)
        self.assertEqual(result["data_properties_count"], 1)
        self.assertEqual(result["individual_count"], 2)
        self.assertEqual(
            sorted((r["subject"], r["predicate"], r["object"]) for r in result["rows"]),
            [("a", "knows", "b"), ("a", "label", "A")],
        )

    async def test_the_store_counts_and_only_the_shown_rows_are_read(self):
        await self.service.preview_graph_filters(graph_names=[], filters=[], limit=5)

        # Every query is an aggregate or bounded by the preview's LIMIT.
        for sparql in self.raw.queries:
            self.assertTrue(
                "COUNT(" in sparql or re.search(r"LIMIT\s+5\s*$", sparql.strip()),
                sparql,
            )
        # The synchronous store never runs on the event loop's thread.
        self.assertNotIn(threading.get_ident(), self.threads)
