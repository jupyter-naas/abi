"""Composer HTTP regressions with synthetic RDF; no live engine/database needed."""

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response
from naas_abi.apps.nexus.apps.api.app.services.graph.access_test import (
    ALICE,
    BETA,
    PERSON,
    ALPHA,
    ServiceIsolationTest,
    fixtures,
    scope,
)
from rdflib import RDF, RDFS, Graph, Literal, URIRef


class ComposerEndpointTest(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        ServiceIsolationTest.setUpClass()
        from naas_abi.apps.nexus.apps.api.app.services.graph.adapters.primary import (
            graph__primary_adapter__FastAPI,
        )

        cls.api = graph__primary_adapter__FastAPI

    async def asyncSetUp(self):
        self.store = fixtures()
        self.service = ServiceIsolationTest.service_class(
            lambda: self.store, access_scope=scope()
        )
        app = FastAPI()
        app.include_router(self.api.router, prefix="/api/graph")
        app.dependency_overrides[self.api.get_current_user_required] = lambda: (
            SimpleNamespace(id="user")
        )
        app.dependency_overrides[self.api.get_graph_service] = lambda: self.service
        self.guard = patch.object(
            self.api, "workspace_graph_service", AsyncMock(return_value=self.service)
        )
        self.cache = patch.object(self.api, "_resolve_query_cache", return_value=None)
        self.guard.start()
        self.cache.start()
        self.addCleanup(self.guard.stop)
        self.addCleanup(self.cache.stop)
        self.client = AsyncClient(
            transport=ASGITransport(app=app), base_url="http://synthetic"
        )

    async def asyncTearDown(self):
        await self.client.aclose()

    async def columns(self, graph: str = ALPHA, refresh: bool = False) -> Response:
        return await self.client.get(
            "/api/graph/columns",
            params={
                "workspace_id": "alpha",
                "graph_uri": graph,
                "class_uri": str(PERSON),
                "force_refresh": str(refresh).lower(),
            },
        )

    async def test_columns_timeout_returns_retryable_error(self) -> None:
        from requests.exceptions import ReadTimeout

        with patch.object(self.store, "query", side_effect=ReadTimeout("fixture timeout")):
            response = await self.columns()
        self.assertEqual(response.status_code, 503, response.text)
        self.assertIn("Retry", response.json()["detail"])

    async def test_selected_class_discovers_columns_and_loads_its_instances(self):
        response = await self.columns()
        self.assertEqual(response.status_code, 200, response.text)
        label = next(
            c
            for c in response.json()["columns"]
            if c["predicate_uri"] == str(RDFS.label)
        )
        response = await self.client.post(
            "/api/graph/query",
            json={
                "workspace_id": "alpha",
                "spec": {
                    "mode": "list",
                    "graph_uris": [ALPHA],
                    "root": {"kind": "class", "class_uris": [str(PERSON)]},
                    "columns": [
                        {
                            "id": label["id"],
                            "datatype": label["datatype"],
                            "source": {
                                "kind": "property",
                                "predicate": label["predicate_uri"],
                            },
                        }
                    ],
                },
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["rows"][0][label["id"]]["value"], "Alice")
        self.assertNotIn("Secret person", response.text)

    async def test_property_free_instances_are_still_rows(self):
        self.store.insert(
            Graph().add((URIRef("urn:Unlabelled"), RDF.type, PERSON)), URIRef(ALPHA)
        )
        response = await self.client.post(
            "/api/graph/query",
            json={
                "workspace_id": "alpha",
                "spec": {
                    "mode": "list",
                    "graph_uris": [ALPHA],
                    "root": {"kind": "class", "class_uris": [str(PERSON)]},
                    "columns": [
                        {
                            "id": "label",
                            "datatype": "string",
                            "source": {
                                "kind": "property",
                                "predicate": str(RDFS.label),
                            },
                        }
                    ],
                },
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(response.json()["rows"]), 2)

    async def test_search_http_parameter_and_class_filter(self):
        for class_uri, expected in [(str(PERSON), True), ("urn:AbsentClass", False)]:
            response = await self.client.get(
                "/api/graph/search",
                params={
                    "workspace_id": "alpha",
                    "q": "Alice",
                    "class_uri": class_uri,
                },
            )
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(
                any(h["uri"] == str(ALICE) for h in response.json()["results"]),
                expected,
            )

    async def test_columns_retry_rechecks_scope(self):
        response = await self.columns(BETA, refresh=True)
        self.assertEqual(response.status_code, 403)
        self.assertFalse(self.store.queries)

    async def test_columns_refresh_recovers_a_stale_empty_cache(self):
        class Cache:
            data = {}

            def fetch(self, key):
                return self.data.get(key)

            def store(self, key, value):
                self.data[key] = value

        cache = Cache()
        with patch.object(self.api, "_resolve_query_cache", return_value=cache):
            response = await self.columns()
            self.assertTrue(response.json()["columns"])
            for key in cache.data:
                cache.data[key] = {"columns": []}
            response = await self.columns()
            self.assertEqual(response.json()["columns"], [])
            response = await self.columns(refresh=True)
            self.assertTrue(response.json()["columns"])

    async def test_cross_graph_relation_discovery_and_follow(self):
        from naas_abi.apps.nexus.apps.api.app.services.graph.access_test import REF

        car, car_class, owns = map(URIRef, ["urn:CarOne", "urn:Car", "urn:owns"])
        triples = Graph()
        triples.add((ALICE, owns, car))
        triples.add((car, RDF.type, car_class))
        triples.add((car, RDFS.label, Literal("Car one")))
        self.store.insert(triples, URIRef(REF))
        columns = (await self.columns()).json()["columns"]
        relation = next(c for c in columns if c["predicate_uri"] == str(owns))
        self.assertEqual(relation["target_classes"][0]["graph"], REF)
        response = await self.client.post(
            "/api/graph/query",
            json={
                "workspace_id": "alpha",
                "spec": {
                    "mode": "list",
                    "graph_uris": [ALPHA, REF],
                    "root": {"kind": "class", "class_uris": [str(car_class)]},
                    "columns": [
                        {
                            "id": "owner",
                            "datatype": "iri",
                            "source": {
                                "kind": "node",
                                "show": "label",
                                "path": [
                                    {
                                        "predicate": str(owns),
                                        "direction": "in",
                                        "quantifier": "one",
                                    }
                                ],
                            },
                        }
                    ],
                },
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["rows"][0]["owner"]["value"], "Alice")
