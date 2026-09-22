"""Explorer projections use RDFLib, with optional Fuseki compatibility checks."""

import os
import unittest
from types import SimpleNamespace
from typing import Any, Never, cast
from unittest.mock import AsyncMock, patch

import requests
from naas_abi.apps.nexus.apps.api.app.services.graph.explorer import (
    catalog,
    graph_snapshot,
    instances,
    network,
    overview,
    resolve_graphs,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.graph__schema import (
    GraphAccessError,
    GraphInfoData,
    GraphPackData,
    GraphQuerySpecError,
)
from rdflib import OWL, RDF, RDFS, BNode, Dataset, Literal, URIRef

G1, G2, EMPTY, SCHEMA = "urn:g1", "urn:g2", "urn:empty", "urn:schema"
PERSON, EMPLOYEE, ALICE, CAROL = map(
    URIRef, ["urn:Person", "urn:Employee", "urn:Alice", "urn:Carol"]
)


class ExplorerProjectionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.store = Dataset()
        self.packs = [
            GraphPackData(
                role_label="data",
                graphs=[
                    GraphInfoData(id=u, uri=u, label="Same label", role_label="data")
                    for u in [G1, G2, EMPTY]
                ],
            )
        ]
        self.g1 = self.store.graph(URIRef(G1))
        self.g2 = self.store.graph(URIRef(G2))
        for g in (self.g1, self.g2):
            g.add((ALICE, RDF.type, PERSON))
            g.add((ALICE, RDF.type, OWL.NamedIndividual))
            g.add((ALICE, RDFS.label, Literal("Alice")))
        self.g1.add((ALICE, RDF.type, EMPLOYEE))
        self.g1.add((CAROL, RDF.type, PERSON))
        self.g1.add((CAROL, RDFS.label, Literal("")))
        self.g1.add((ALICE, URIRef("urn:knows"), CAROL))
        self.g1.add((PERSON, RDF.type, OWL.Class))
        self.g1.add((BNode(), RDF.type, PERSON))
        schema = self.store.graph(URIRef(SCHEMA))
        schema.add((EMPLOYEE, RDFS.subClassOf, PERSON))
        schema.add((PERSON, RDFS.label, Literal("Person")))

    def summary(self, graphs: list[str] | None = None) -> dict[str, Any]:
        return overview(self.store, self.packs, graphs or [G1, G2, EMPTY], SCHEMA)

    def page(
        self,
        graphs: list[str] | None = None,
        classes: list[str] | None = None,
        search: str = "",
        offset: int = 0,
        limit: int = 50,
    ) -> dict[str, Any]:
        return instances(
            self.store, graphs or [G1, G2], classes or [], search, offset, limit, SCHEMA
        )

    def test_overview_lists_graph_tiles_when_no_graphs_selected(self) -> None:
        data = overview(self.store, self.packs, [], SCHEMA)
        self.assertEqual({g["uri"] for g in data["graph_metrics"]}, {G1, G2, EMPTY})
        self.assertTrue(all(g["triples"] == 0 for g in data["graph_metrics"]))

    def test_catalog_matches_overview_without_dashboard_scans(self) -> None:
        queries: list[str] = []
        dataset = self.store

        class RecordingStore:
            def query(self, query: str) -> Any:
                queries.append(query)
                return dataset.query(query)

        data = catalog(RecordingStore(), self.packs, [G1, G2, EMPTY], SCHEMA)
        self.assertGreaterEqual(len(queries), 3)
        self.assertNotIn("kpis", data)
        self.assertEqual(
            sorted(c["uri"] for c in data["classes"] if c["count"]),
            sorted(c["uri"] for c in self.summary()["classes"]),
        )
        self.assertEqual(len(data["graphs"]), 3)

    def test_independent_counts_handle_multiple_types_labels_and_graphs(self) -> None:
        self.g1.add((ALICE, RDFS.label, Literal("Another label")))
        self.g1.add((ALICE, RDF.type, URIRef("urn:ExtraType")))
        kpis = self.summary()["kpis"]
        # Per-graph distinct, summed: Alice is in G1 and G2.
        self.assertEqual(kpis["instances"], 3)
        self.assertEqual(kpis["named_individuals"], 2)
        self.assertEqual(kpis["labeled_instances"], 2)
        self.assertEqual(self.summary([G1])["kpis"]["instances"], 2)
        item = next(i for i in self.page([G1])["items"] if i["uri"] == str(ALICE))
        self.assertEqual(item["label"], "Alice")
        self.assertEqual(item["class_uri"], str(EMPLOYEE))

    def test_network_skips_table_only_counts(self) -> None:
        queries: list[str] = []
        dataset = self.store

        class RecordingStore:
            def query(self, query: str) -> Any:
                queries.append(query)
                return dataset.query(query)

        data = network(RecordingStore(), [G1], [str(EMPLOYEE)], "", 0, 50, SCHEMA)
        self.assertEqual(len(data["items"]), 1)
        self.assertEqual(len(queries), 6)
        self.assertFalse(
            any(
                " AS ?outgoing" in q or " AS ?incoming" in q or " AS ?properties" in q
                for q in queries
            )
        )

    def test_instances_unique_per_graph_and_summed_across_graphs(self) -> None:
        k = self.summary()["kpis"]
        self.assertEqual(k["instances"], 3)
        self.assertEqual(k["named_individuals"], 2)
        # Classes and predicates are unions, not sums.
        self.assertEqual(k["classes"], 2)
        self.assertEqual(k["predicates"], 3)
        single = self.summary([G1])["kpis"]
        self.assertEqual((single["instances"], single["named_individuals"]), (2, 1))

    def test_schema_subject_with_a_custom_metatype_is_not_an_instance(self) -> None:
        self.g1.add((PERSON, RDF.type, URIRef("urn:MetaClass")))
        self.assertEqual(self.summary([G1])["kpis"]["instances"], 2)
        self.assertNotIn(str(PERSON), [i["uri"] for i in self.page()["items"]])

    def test_exact_triples_include_blank_nodes_and_schema(self) -> None:
        self.assertEqual(self.summary()["kpis"]["triples"], len(self.g1) + len(self.g2))

    def test_nonempty_label_coverage(self) -> None:
        self.assertEqual(self.summary([G1])["kpis"]["labeled_instances"], 1)

    def test_empty_graph_is_kept_and_duplicate_labels_are_distinct(self) -> None:
        metrics = self.summary()["graph_metrics"]
        self.assertEqual(len(metrics), 3)
        self.assertEqual(next(g for g in metrics if g["uri"] == EMPTY)["triples"], 0)

    def test_filter_changes_exact_scope(self) -> None:
        self.assertEqual(self.summary([G2])["kpis"]["instances"], 1)
        self.assertEqual({g["uri"] for g in self.summary([G2])["graph_metrics"]}, {G2})

    def test_real_hierarchy_and_class_counts(self) -> None:
        classes = {
            c["uri"]: c for c in catalog(self.store, self.packs, [G1, G2], SCHEMA)["classes"]
        }
        self.assertEqual(classes[str(EMPLOYEE)]["parents"], [str(PERSON)])
        self.assertEqual(classes[str(PERSON)]["count"], 2)
        self.assertEqual(classes[str(PERSON)]["label"], "Person")

    def test_pagination_has_one_row_per_membership_not_per_type(self) -> None:
        first = self.page(limit=1)
        second = self.page(offset=1, limit=1)
        last = self.page(offset=2, limit=1)
        self.assertTrue(first["has_more"])
        self.assertTrue(second["has_more"])
        self.assertFalse(last["has_more"])
        keys = [
            (p["items"][0]["graph_uri"], p["items"][0]["uri"])
            for p in (first, second, last)
        ]
        self.assertEqual(len(set(keys)), 3)

    def test_instance_counts_and_source_graph(self) -> None:
        alice = next(
            i
            for i in self.page()["items"]
            if i["uri"] == str(ALICE) and i["graph_uri"] == G1
        )
        self.assertEqual(alice["properties_count"], 1)
        self.assertEqual(alice["domain_relations_count"], 1)
        self.assertEqual(alice["range_relations_count"], 0)

    def test_class_multiselect_is_union(self) -> None:
        self.assertEqual(
            len(self.page(classes=[str(PERSON), str(EMPLOYEE)])["items"]), 3
        )
        self.assertEqual(len(self.page(classes=[str(EMPLOYEE)])["items"]), 1)

    def test_unavailable_class_does_not_widen(self) -> None:
        self.assertEqual(self.page(classes=["urn:missing"])["items"], [])

    def test_search_labels_iris_and_injection(self) -> None:
        self.assertEqual(len(self.page(search="alice")["items"]), 2)
        self.assertEqual(len(self.page(search="urn:Carol")["items"]), 1)
        self.assertEqual(self.page(search='" } UNION { ?s ?p ?o } #')["items"], [])

    def test_graph_access_is_resolved_before_queries(self) -> None:
        self.assertEqual(resolve_graphs(self.packs, []), sorted([G1, G2, EMPTY]))
        self.assertEqual(resolve_graphs(self.packs, [G1, G1]), [G1])
        with self.assertRaises(GraphAccessError):
            resolve_graphs(self.packs, [G1, "urn:private"])
        with self.assertRaises(GraphAccessError):
            resolve_graphs([], [G1])
        with self.assertRaises(GraphQuerySpecError):
            resolve_graphs(self.packs, ["urn:g> } UNION {"])

    def test_empty_catalog_does_not_query_default_or_all_graphs(self) -> None:
        class FailStore:
            def query(self, query: str) -> Never:
                raise AssertionError("must not query")

        self.assertEqual(overview(FailStore(), [], [], SCHEMA)["kpis"]["instances"], 0)
        self.assertEqual(instances(FailStore(), [], [], "", 0, 50, SCHEMA)["items"], [])

    def test_network_keeps_scope_and_immediate_neighbors(self) -> None:
        car = URIRef("urn:Car1")
        self.g1.add((ALICE, URIRef("urn:drives"), car))
        self.g1.add((car, RDFS.label, Literal("Car one")))
        self.g2.add((ALICE, URIRef("urn:secret"), URIRef("urn:Hidden")))
        data = network(self.store, [G1], [str(EMPLOYEE)], "", 0, 50, SCHEMA)
        self.assertEqual([item["uri"] for item in data["items"]], [str(ALICE)])
        self.assertEqual(
            {item["uri"] for item in data["neighbors"]}, {str(CAROL), str(car)}
        )
        self.assertEqual({row["graph_uri"] for row in data["relations"]}, {G1})
        self.assertNotIn("urn:secret", [row["predicate"] for row in data["relations"]])
        self.assertEqual(
            next(
                item["label"] for item in data["neighbors"] if item["uri"] == str(car)
            ),
            "Car one",
        )

    def test_network_paging_incoming_edges_and_duplicate_memberships(self) -> None:
        data = network(self.store, [G1], [str(PERSON)], "", 1, 1, SCHEMA)
        self.assertEqual([item["uri"] for item in data["items"]], [str(CAROL)])
        self.assertEqual(data["relations"][0]["source"], str(ALICE))
        self.g2.add((ALICE, URIRef("urn:knows"), CAROL))
        data = network(self.store, [G1, G2], [], "Alice", 0, 50, SCHEMA)
        self.assertEqual(len(data["items"]), 2)
        self.assertEqual(len(data["relations"]), 2)
        self.assertEqual({item["graph_uri"] for item in data["neighbors"]}, {G1, G2})

    def test_network_bound_and_no_results(self) -> None:
        self.g1.add((ALICE, URIRef("urn:knows"), URIRef("urn:Third")))
        data = network(self.store, [G1], [], "", 0, 50, SCHEMA, relation_limit=1)
        self.assertEqual(len(data["relations"]), 1)
        self.assertTrue(data["relations_truncated"])
        empty = network(self.store, [G1], [], "No match", 0, 50, SCHEMA)
        self.assertEqual(empty["relations"], [])
        self.assertEqual(empty["neighbors"], [])
        self.assertFalse(empty["relations_truncated"])

    @unittest.skipUnless(
        os.environ.get("FUSEKI_TEST_QUERY_URL"),
        "Set FUSEKI_TEST_QUERY_URL to an isolated Fuseki query endpoint",
    )
    def test_generated_queries_execute_on_fuseki(self) -> None:
        """Exercise every projection query on Jena as well as RDFLib.

        The fixture supplies rows to generate dependent queries. Fuseki only
        receives SELECT queries, so this test does not change its dataset.
        """
        queries: list[str] = []
        dataset = self.store

        class RecordingStore:
            def query(self, query: str) -> Any:
                queries.append(query)
                return dataset.query(query)

        store = RecordingStore()
        catalog(store, self.packs, [G1, G2], SCHEMA)
        overview(store, self.packs, [G1, G2], SCHEMA)
        instances(store, [G1, G2], [str(PERSON)], "Alice", 0, 50, SCHEMA)
        network(store, [G1], [str(EMPLOYEE)], "", 0, 50, SCHEMA)
        for query in dict.fromkeys(queries):
            with self.subTest(query=query):
                response = requests.post(
                    os.environ["FUSEKI_TEST_QUERY_URL"],
                    data=query.encode(),
                    headers={
                        "Content-Type": "application/sparql-query",
                        "Accept": "application/sparql-results+json",
                    },
                    timeout=10,
                )
                self.assertEqual(response.status_code, 200, response.text)

    def test_metric_read_failure_degrades_to_unavailable(self) -> None:
        dataset = self.store

        class DamagedStore:
            # Mimics a TDB2 node-table read error on literal objects only.
            def query(self, query: str) -> Any:
                if "isLiteral(?o)" in query or "STRLEN" in query:
                    raise RuntimeError("NodeTableTRDF/Read")
                return dataset.query(query)

        data = overview(DamagedStore(), self.packs, [G1, G2], SCHEMA)
        k = data["kpis"]
        self.assertIsNone(k["relations"])
        self.assertIsNone(k["literal_values"])
        self.assertIsNone(k["labeled_instances"])
        self.assertEqual(k["instances"], 3)
        self.assertEqual(k["triples"], len(self.g1) + len(self.g2))
        self.assertEqual(
            data["unavailable"], ["labeled_instances", "literal_values", "relations"]
        )
        self.assertIsNone(data["graph_metrics"][0]["relations"])

    def test_consolidation_uses_supplied_snapshots_concurrently(self) -> None:
        calls: list[str] = []

        def snapshot(store: Any, uri: str) -> dict[str, Any]:
            calls.append(uri)
            return graph_snapshot(store, uri)

        data = overview(
            self.store, self.packs, [G1, G2, EMPTY], SCHEMA,
            snapshot=snapshot, max_workers=3,
        )
        self.assertEqual(sorted(calls), [EMPTY, G1, G2])
        self.assertEqual([g["uri"] for g in data["graph_metrics"]], [G1, G2, EMPTY])
        self.assertEqual(data["kpis"], self.summary()["kpis"])

    def test_pending_snapshot_blanks_totals_and_keeps_tile_order(self) -> None:
        def snapshot(store: Any, uri: str) -> dict[str, Any] | None:
            return None if uri == G2 else graph_snapshot(store, uri)

        data = overview(self.store, self.packs, [G1, G2, EMPTY], SCHEMA, snapshot=snapshot)
        self.assertEqual(data["pending"], [G2])
        self.assertTrue(all(v is None for v in data["kpis"].values()))
        self.assertEqual([g["uri"] for g in data["graph_metrics"]], [G1, G2, EMPTY])
        self.assertTrue(data["graph_metrics"][1]["pending"])
        self.assertEqual(data["graph_metrics"][0]["instances"], 2)

    def test_skipped_metrics_are_not_queried(self) -> None:
        queries: list[str] = []
        dataset = self.store

        class RecordingStore:
            def query(self, query: str) -> Any:
                queries.append(query)
                return dataset.query(query)

        snap = graph_snapshot(RecordingStore(), G1, skip=["relations"])
        self.assertEqual(snap["unavailable"], ["relations", "literal_values"])
        self.assertFalse(any("isLiteral(?o)" in q for q in queries))
        self.assertEqual(snap["instances"], 2)

    def test_consolidation_excludes_graphs_missing_a_metric(self) -> None:
        dataset = self.store

        class G2Damaged:
            def query(self, query: str) -> Any:
                if "<urn:g2>" in query and "isLiteral(?o)" in query:
                    raise RuntimeError("NodeTableTRDF/Read")
                return dataset.query(query)

        data = overview(G2Damaged(), self.packs, [G1, G2], SCHEMA)
        g1 = graph_snapshot(self.store, G1)
        self.assertEqual(data["kpis"]["relations"], g1["relations"])
        self.assertEqual(data["kpis"]["literal_values"], g1["literal_values"])
        self.assertEqual(data["excluded"], {"relations": [G2], "literal_values": [G2]})
        self.assertEqual(data["kpis"]["instances"], 3)

    def test_unbound_sum_is_a_failure_not_zero(self) -> None:
        class Row(dict[str, Any]):
            def asdict(self) -> dict[str, Any]:
                return dict(self)

        dataset = self.store

        class UnboundSums:
            # Jena returns an unbound aggregate when a value cannot be read.
            def query(self, query: str) -> Any:
                if "isLiteral(?o)" in query:
                    return [Row()]
                return dataset.query(query)

        snap = graph_snapshot(UnboundSums(), G1)
        self.assertIsNone(snap["relations"])
        self.assertEqual(snap["unavailable"], ["relations", "literal_values"])
        self.assertEqual(snap["transient"], [])

    def test_outage_is_marked_transient(self) -> None:
        dataset = self.store

        class Flaky:
            def query(self, query: str) -> Any:
                if "COUNT(DISTINCT ?s) AS ?instances" in query:
                    raise ConnectionResetError(104, "Connection reset by peer")
                return dataset.query(query)

        snap = graph_snapshot(Flaky(), G1)
        self.assertEqual(snap["transient"], ["instances", "named_individuals"])

    def test_query_failure_is_not_zero(self) -> None:
        class FailStore:
            def query(self, query: str) -> Never:
                raise RuntimeError("offline")

        with self.assertRaises(RuntimeError):
            overview(FailStore(), self.packs, [G1], SCHEMA)


class ExplorerEndpointTest(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # Supply only the configuration read at service import. No engine is started.
        from naas_abi import ABIModule

        config = SimpleNamespace(
            configuration=SimpleNamespace(
                nexus_config=SimpleNamespace(
                    ontology_base_uri="http://ontology.naas.ai/nexus/"
                )
            )
        )
        with patch.object(ABIModule, "get_instance", return_value=config):
            from naas_abi.apps.nexus.apps.api.app.services.graph.adapters.primary import (
                graph__primary_adapter__FastAPI,
            )

            assert graph__primary_adapter__FastAPI.router

    async def test_catalog_workspace_guard_and_forbidden_graph(self) -> None:
        from fastapi import HTTPException
        from naas_abi.apps.nexus.apps.api.app.services.graph.adapters.primary import (
            graph__primary_adapter__FastAPI as api,
        )

        service: Any = SimpleNamespace(
            explorer_catalog=AsyncMock(side_effect=GraphAccessError("denied"))
        )
        with patch.object(
            api, "workspace_graph_service", AsyncMock(side_effect=HTTPException(403))
        ):
            with self.assertRaises(HTTPException):
                await api.explorer_catalog(
                    api.ExplorerRequest(workspace_id="ws"),
                    cast(Any, SimpleNamespace(id="user")),
                    service,
                )
        service.explorer_catalog.assert_not_called()
        with patch.object(
            api, "workspace_graph_service", AsyncMock(return_value=service)
        ):
            with self.assertRaises(HTTPException) as caught:
                await api.explorer_catalog(
                    api.ExplorerRequest(workspace_id="ws", graph_uris=["urn:hidden"]),
                    cast(Any, SimpleNamespace(id="user")),
                    service,
                )
            self.assertEqual(caught.exception.status_code, 403)

    async def test_workspace_membership_guard_precedes_overview(self) -> None:
        from fastapi import HTTPException
        from naas_abi.apps.nexus.apps.api.app.services.graph.adapters.primary import (
            graph__primary_adapter__FastAPI as api,
        )

        service: Any = SimpleNamespace(explorer_overview=AsyncMock())
        with patch.object(
            api, "workspace_graph_service", AsyncMock(side_effect=HTTPException(403))
        ):
            with self.assertRaises(HTTPException):
                await api.explorer_overview(
                    api.ExplorerRequest(workspace_id="ws"),
                    cast(Any, SimpleNamespace(id="user")),
                    service,
                )
        service.explorer_overview.assert_not_called()

    async def test_workspace_membership_guard_precedes_instances(self) -> None:
        from fastapi import HTTPException
        from naas_abi.apps.nexus.apps.api.app.services.graph.adapters.primary import (
            graph__primary_adapter__FastAPI as api,
        )

        service: Any = SimpleNamespace(explorer_instances=AsyncMock())
        with patch.object(
            api, "workspace_graph_service", AsyncMock(side_effect=HTTPException(403))
        ):
            with self.assertRaises(HTTPException):
                await api.explorer_instances(
                    api.ExplorerInstancesRequest(workspace_id="ws"),
                    cast(Any, SimpleNamespace(id="user")),
                    service,
                )
        service.explorer_instances.assert_not_called()

    async def test_network_workspace_guard_and_forbidden_graph(self) -> None:
        from fastapi import HTTPException
        from naas_abi.apps.nexus.apps.api.app.services.graph.adapters.primary import (
            graph__primary_adapter__FastAPI as api,
        )

        service: Any = SimpleNamespace(
            explorer_network=AsyncMock(side_effect=GraphAccessError("denied"))
        )
        with patch.object(
            api, "workspace_graph_service", AsyncMock(side_effect=HTTPException(403))
        ):
            with self.assertRaises(HTTPException):
                await api.explorer_network(
                    api.ExplorerInstancesRequest(workspace_id="ws"),
                    cast(Any, SimpleNamespace(id="user")),
                    service,
                )
        service.explorer_network.assert_not_called()
        with patch.object(
            api, "workspace_graph_service", AsyncMock(return_value=service)
        ):
            with self.assertRaises(HTTPException) as caught:
                await api.explorer_network(
                    api.ExplorerInstancesRequest(
                        workspace_id="ws", graph_uris=["urn:hidden"]
                    ),
                    cast(Any, SimpleNamespace(id="user")),
                    service,
                )
            self.assertEqual(caught.exception.status_code, 403)

    async def test_pagination_validation_and_graph_error(self) -> None:
        from fastapi import HTTPException
        from naas_abi.apps.nexus.apps.api.app.services.graph.adapters.primary import (
            graph__primary_adapter__FastAPI as api,
        )
        from pydantic import ValidationError

        for kwargs in ({"limit": 0}, {"limit": 101}, {"offset": -1}):
            with self.assertRaises(ValidationError):
                api.ExplorerInstancesRequest(workspace_id="ws", **kwargs)
        service: Any = SimpleNamespace(
            explorer_overview=AsyncMock(side_effect=GraphAccessError("unavailable"))
        )
        with patch.object(
            api, "workspace_graph_service", AsyncMock(return_value=service)
        ):
            with self.assertRaises(HTTPException) as caught:
                await api.explorer_overview(
                    api.ExplorerRequest(workspace_id="ws"),
                    cast(Any, SimpleNamespace(id="user")),
                    service,
                )
        self.assertEqual(caught.exception.status_code, 403)
