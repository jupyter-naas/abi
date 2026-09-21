"""Persistent config seeds and admin overrides using an isolated SQLite database."""

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from naas_abi.apps.nexus.apps.api.app.models import (
    OrganizationModel,
    UserModel,
    WorkspaceModel,
    WorkspaceResourcePolicyModel,
)
from naas_abi.apps.nexus.apps.api.app.services.workspaces.adapters.secondary import (
    resource_access_postgres as repo,
)
from naas_abi.apps.nexus.apps.api.app.services.workspaces.resource_access import (
    PolicyConflictError,
    ResourceAccessService,
)
from naas_abi.apps.nexus.graph_policy_config import (
    NEXUS_GRAPH,
    SCHEMA_GRAPH,
    WorkspaceGraphPolicyConfig,
)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


class ResourceAccessTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite://")
        tables = [
            UserModel.__table__,
            OrganizationModel.__table__,
            WorkspaceModel.__table__,
            WorkspaceResourcePolicyModel.__table__,
        ]
        async with self.engine.begin() as connection:
            for table in tables:
                await connection.run_sync(table.create)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.sessions() as db:
            db.add(
                UserModel(
                    id="admin",
                    name="Admin",
                    email="a@example.org",
                    hashed_password="unused",
                )
            )
            db.add(
                OrganizationModel(
                    id="org", name="Organization", slug="org", owner_id="admin"
                )
            )
            db.add(
                WorkspaceModel(
                    id="a", name="A", slug="a", owner_id="admin", organization_id="org"
                )
            )
            db.add(
                WorkspaceModel(
                    id="b", name="B", slug="b", owner_id="admin", organization_id="org"
                )
            )
            await db.commit()
        self.seed = SimpleNamespace(
            slug="a",
            ontologies=["fixture:Public.ttl"],
            graphs=WorkspaceGraphPolicyConfig(read=["urn:public"], include_owned=False),
        )
        self.settings = SimpleNamespace(
            organizations=[SimpleNamespace(slug="org", workspaces=[self.seed])]
        )
        self.config = patch.object(repo, "live_settings", return_value=self.settings)
        self.config.start()
        self.addCleanup(self.config.stop)

    async def asyncTearDown(self):
        await self.engine.dispose()

    async def test_seed_once_and_admin_changes_survive_config_changes_and_new_sessions(
        self,
    ):
        async with self.sessions() as db:
            first = await repo.load_resource_policy(db, "a", "ontologies")
            self.assertEqual(first.data["enabled"], ["fixture:Public.ttl"])
            await ResourceAccessService(repo.ResourcePolicyPostgres(db)).save(
                "a", "ontologies", {"enabled": []}, first.revision, "admin", "admin"
            )
        self.seed.ontologies = ["fixture:Private.ttl"]
        async with self.sessions() as db:
            saved = await repo.load_resource_policy(db, "a", "ontologies")
            self.assertEqual(saved.data, {"enabled": []})
            self.assertEqual(saved.revision, 2)
            self.assertEqual(saved.updated_by, "admin")
            self.assertEqual(
                (await repo.load_resource_policy(db, "b", "ontologies")).data,
                {"enabled": []},
            )

    async def test_initial_seed_is_not_reapplied_even_before_first_admin_edit(self):
        async with self.sessions() as db:
            first = await repo.load_resource_policy(db, "a", "graphs")
        self.seed.graphs = WorkspaceGraphPolicyConfig(read_all=True)
        async with self.sessions() as db:
            second = await repo.load_resource_policy(db, "a", "graphs")
            self.assertEqual(first.data, second.data)

    async def test_wrong_organization_does_not_supply_seed(self):
        self.settings.organizations[0].slug = "other"
        async with self.sessions() as db:
            self.assertEqual(
                (await repo.load_resource_policy(db, "a", "ontologies")).data,
                {"enabled": []},
            )
            self.assertFalse(
                (await repo.load_resource_policy(db, "a", "graphs")).data["read_all"]
            )

    async def test_stale_admin_save_cannot_overwrite_newer_assignments(self):
        async with self.sessions() as db:
            saved = await repo.load_resource_policy(db, "a", "graphs")
            service = ResourceAccessService(repo.ResourcePolicyPostgres(db))
            await service.save(
                "a",
                "graphs",
                {"read": ["urn:changed"]},
                saved.revision,
                "admin",
                "owner",
            )
            with self.assertRaises(PolicyConflictError):
                await service.save(
                    "a", "graphs", {"read_all": True}, saved.revision, "admin", "admin"
                )
            self.assertEqual(
                (await repo.load_resource_policy(db, "a", "graphs")).data["read"],
                ["urn:changed"],
            )

    async def test_members_cannot_save_and_protected_graphs_cannot_be_granted(self):
        async with self.sessions() as db:
            saved = await repo.load_resource_policy(db, "a", "graphs")
            service = ResourceAccessService(repo.ResourcePolicyPostgres(db))
            for role in ["member", "viewer"]:
                with self.assertRaises(PermissionError):
                    await service.save(
                        "a", "graphs", {"read_all": True}, saved.revision, "admin", role
                    )
            for data in [
                {"write": [SCHEMA_GRAPH]},
                {"read": [NEXUS_GRAPH]},
                {"read": ["*"]},
            ]:
                with self.assertRaises(ValueError):
                    await service.save(
                        "a", "graphs", data, saved.revision, "admin", "admin"
                    )

    async def test_graph_scope_and_cache_key_follow_saved_revocation(self):
        from naas_abi.apps.nexus.apps.api.app.services.graph.access_test import (
            ALPHA,
            fixtures,
        )
        from naas_abi.apps.nexus.apps.api.app.services.graph.adapters.secondary.workspace_policy import (
            load_workspace_scope,
        )

        self.seed.graphs = WorkspaceGraphPolicyConfig(read=[ALPHA], include_owned=False)
        async with self.sessions() as db:
            before = await load_workspace_scope(db, fixtures(), "a", "member")
            self.assertIn(ALPHA, before.readable)
            saved = await repo.load_resource_policy(db, "a", "graphs")
            await ResourceAccessService(repo.ResourcePolicyPostgres(db)).save(
                "a",
                "graphs",
                {"include_owned": False},
                saved.revision,
                "admin",
                "admin",
            )
            after = await load_workspace_scope(db, fixtures(), "a", "member")
            self.assertFalse(after.readable)
            self.assertNotEqual(before.cache_key, after.cache_key)
            self.assertEqual(
                (await repo.effective_graph_policies(db))["org/a"].read, []
            )

    async def test_migration_is_idempotent(self):
        from pathlib import Path

        # Resolve from this module in the real checkout or staging overlay.
        migration = (
            Path(__file__).parents[3]
            / "migrations"
            / "0044_add_workspace_resource_policies.sql"
        )
        async with self.sessions() as db:
            for _ in range(2):
                await db.execute(text(migration.read_text()))
            await db.commit()

    async def test_ontology_editor_uses_portable_ids_and_retains_unavailable_assignments(
        self,
    ):
        from naas_abi.apps.nexus.apps.api.app.services.workspaces.adapters.primary import (
            resource_access as http,
        )
        from naas_abi.apps.nexus.apps.api.app.services.workspaces.resource_access import (
            ResourcePolicy,
        )

        ontologies = SimpleNamespace(
            list_ontology_files=AsyncMock(
                return_value=[
                    SimpleNamespace(
                        path="/deployment/ontologies/modules/Public.ttl",
                        name="Public",
                        module_name="fixture",
                    ),
                ]
            )
        )
        catalog = await http.assignment_catalog("ontologies", "a", ontologies, None)
        self.assertEqual(catalog[0]["id"], "fixture:public.ttl")
        payload = http.editor_payload(
            "ontologies",
            ResourcePolicy(
                {
                    "enabled": [
                        "/deployment/ontologies/modules/Public.ttl",
                        "missing.ttl",
                    ]
                },
                1,
            ),
            catalog,
        )
        self.assertEqual(
            payload["data"]["enabled"], ["fixture:public.ttl", "missing.ttl"]
        )
        self.assertFalse(payload["catalog"][-1]["available"])
        # A relocated deployment still recognizes the saved qualified assignment.
        ontologies.list_ontology_files.return_value[
            0
        ].path = "/other/ontologies/modules/Public.ttl"
        moved_catalog = await http.assignment_catalog(
            "ontologies", "a", ontologies, None
        )
        self.assertEqual(moved_catalog[0]["id"], "fixture:public.ttl")

    async def test_http_permissions_validation_persistence_and_conflicts(self):
        from naas_abi.apps.nexus.apps.api.app.services.graph.access_test import (
            ServiceIsolationTest,
        )

        ServiceIsolationTest.setUpClass()
        from naas_abi.apps.nexus.apps.api.app.services.workspaces.adapters.primary import (
            resource_access as http,
        )

        app = FastAPI()
        app.include_router(http.router, prefix="/api/workspaces")

        async def get_db():
            async with self.sessions() as db:
                yield db

        app.dependency_overrides[http.get_db] = get_db
        app.dependency_overrides[http.get_current_user_required] = lambda: (
            SimpleNamespace(id="admin")
        )
        app.dependency_overrides[http.get_graph_service] = lambda: SimpleNamespace()
        app.dependency_overrides[http.get_ontology_service] = lambda: SimpleNamespace()
        rows = [
            {
                "id": "urn:public",
                "name": "Public",
                "available": True,
                "description": "Public",
            }
        ]
        with (
            patch.object(http, "require_workspace_admin", AsyncMock()) as guard,
            patch.object(
                http, "assignment_catalog", AsyncMock(return_value=rows)
            ) as catalog,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://synthetic"
            ) as client:
                uri = "/api/workspaces/a/resource-access/graphs"
                first = await client.get(uri)
                self.assertEqual(first.status_code, 200, first.text)
                body = {
                    "revision": first.json()["revision"],
                    "policy": {"read": [], "include_owned": False},
                }
                response = await client.put(uri, json=body)
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()["data"]["read"], [])
                self.assertEqual((await client.put(uri, json=body)).status_code, 409)
                body["revision"] = response.json()["revision"]
                body["policy"] = {"read": ["urn:not-in-catalog"]}
                self.assertEqual((await client.put(uri, json=body)).status_code, 422)
                calls = catalog.await_count
                guard.side_effect = HTTPException(403, "Workspace admin role required")
                self.assertEqual((await client.get(uri)).status_code, 403)
                self.assertEqual((await client.put(uri, json=body)).status_code, 403)
                self.assertEqual(catalog.await_count, calls)
