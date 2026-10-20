"""Shared icons retain workspace isolation and never modify ontology declarations."""
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from naas_abi.apps.nexus.apps.api.app.models import OntologyIconModel
from naas_abi.apps.nexus.apps.api.app.services.ontology.adapters.primary import (
    ontology__primary_adapter__FastAPI as http,
)
from naas_abi.apps.nexus.apps.api.app.services.ontology.adapters.secondary.ontology_icons_postgres import (
    OntologyIconsPostgres,
)
from naas_abi.apps.nexus.apps.api.app.services.ontology.ontology_icons import OntologyIconsService
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

ICON = "material-symbols-light:public"
OTHER = "material-symbols-light:school-outline"
ALLOWED = {("entity", "urn:term"), ("file", "/ontology.ttl")}


class SharedIconsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with self.engine.begin() as db:
            await db.run_sync(lambda connection: OntologyIconModel.__table__.create(connection))
        self.repo = OntologyIconsPostgres(async_sessionmaker(self.engine, expire_on_commit=False))
        self.service = OntologyIconsService(self.repo)

    async def asyncTearDown(self):
        await self.engine.dispose()

    async def test_persistence_shared_between_readers_but_isolated_by_workspace_and_kind(self):
        await self.service.save_icon("a", "member", "user1", ALLOWED, "entity", "urn:term", ICON)
        second_reader = OntologyIconsService(OntologyIconsPostgres(self.repo.session_factory))
        self.assertEqual((await second_reader.list_icons("a", ALLOWED))[0]["icon"], ICON)
        self.assertEqual(await second_reader.list_icons("b", ALLOWED), [])
        self.assertEqual(await second_reader.list_icons("a", {("annotation", "urn:term")}), [])
        self.assertEqual(await second_reader.list_icons("a", set()), [])

    async def test_upsert_and_reset_only_change_the_selected_object(self):
        for workspace in ("a", "b"):
            await self.repo.save_icon(workspace, "entity", "urn:term", ICON, "user1")
        await self.repo.save_icon("a", "annotation", "urn:term", ICON, "user1")
        await self.service.save_icon("a", "admin", "user2", ALLOWED, "entity", "urn:term", OTHER)
        self.assertEqual((await self.service.list_icons("a", ALLOWED))[0]["icon"], OTHER)
        async with self.repo.session_factory() as db:
            self.assertEqual((await db.execute(text("select count(*) from ontology_icons"))).scalar(), 3)
        await self.service.save_icon("a", "member", "user2", ALLOWED, "entity", "urn:term", None)
        self.assertEqual(await self.service.list_icons("a", ALLOWED), [])
        self.assertEqual(len(await self.repo.list_icons("a")), 1)
        self.assertEqual(len(await self.repo.list_icons("b")), 1)

    async def test_unauthorized_or_hidden_targets_are_never_written(self):
        for role in ("viewer", "guest", ""):
            with self.assertRaises(PermissionError):
                await self.service.save_icon("a", role, "u", ALLOWED, "entity", "urn:term", ICON)
        for kind, resource in (("entity", "urn:hidden"), ("annotation", "urn:term")):
            with self.assertRaises(LookupError):
                await self.service.save_icon("a", "owner", "u", ALLOWED, kind, resource, ICON)
        for icon in ("", "javascript:alert(1)", "<svg/>", "other:public", "data:image/png;base64,xx"):
            with self.assertRaises(ValueError):
                await self.service.save_icon("a", "member", "u", ALLOWED, "entity", "urn:term", icon)
        self.assertEqual(await self.repo.list_icons("a"), [])

    async def test_image_url_and_graph_individual_are_persisted(self):
        image = "https://cdn.example/face.png"
        iri = "http://example.org/person/1"
        await self.service.save_icon("a", "member", "user1", ALLOWED, "individual", iri, image)
        items = await self.service.list_icons("a", set())
        self.assertEqual(items, [{"kind": "individual", "resource_id": iri, "icon": image}])
        await self.service.save_icon("a", "admin", "user2", ALLOWED, "entity", "urn:term", image)
        self.assertEqual((await self.service.list_icons("a", ALLOWED))[0]["icon"], image)
        klass = "https://www.commoncoreontologies.org/ont00001262"
        await self.service.save_icon("a", "member", "user1", set(), "entity", klass, ICON)
        listed = await self.service.list_icons("a", set())
        self.assertTrue(any(item["resource_id"] == klass and item["icon"] == ICON for item in listed))

    async def test_http_contract_authorization_catalog_scoping_and_shared_read(self):
        app = FastAPI()
        app.include_router(http.router, prefix="/api/ontology")
        user = SimpleNamespace(id="member")
        catalog = SimpleNamespace(
            workspace_dictionary=AsyncMock(return_value={"items": [{"type": "entity", "id": "urn:term"}]}),
            list_ontology_files=AsyncMock(return_value=[SimpleNamespace(path="/ontology.ttl")]),
        )
        app.dependency_overrides[http.get_current_user_required] = lambda: user
        app.dependency_overrides[http.get_ontology_service] = lambda: catalog
        app.dependency_overrides[http.get_ontology_icons_service] = lambda: self.service
        with patch.object(http, "require_workspace_access", new=AsyncMock(return_value="member")) as access, patch.object(
            http, "_catalog_refs_for_workspace", new=AsyncMock(return_value=["permitted:ontology.ttl"])
        ):
            async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
                route = "/api/ontology" + http.router.prefix + "/icons"
                self.assertEqual((await client.get(route)).status_code, 422)
                url = route + "?workspace_id=a"
                body = {"kind": "entity", "resource_id": "urn:term", "icon": ICON}
                self.assertEqual((await client.put(url, json=body)).status_code, 200)
                user.id = "another-member"
                result = (await client.get(url)).json()
                self.assertEqual(result["items"][0]["icon"], ICON)
                self.assertTrue(result["can_edit"])
                catalog.workspace_dictionary.assert_awaited_with(catalog_refs=["permitted:ontology.ttl"])
                self.assertEqual((await client.put(url, json={**body, "resource_id": "urn:hidden"})).status_code, 404)
                catalog.workspace_dictionary.reset_mock()
                person = {"kind": "individual", "resource_id": "http://example.org/person/ada", "icon": ICON}
                self.assertEqual((await client.put(url, json=person)).status_code, 200)
                catalog.workspace_dictionary.assert_not_awaited()
                access.return_value = "viewer"
                self.assertFalse((await client.get(url)).json()["can_edit"])
                self.assertEqual((await client.put(url, json=body)).status_code, 403)
                access.side_effect = HTTPException(status_code=403)
                self.assertEqual((await client.get(url)).status_code, 403)
