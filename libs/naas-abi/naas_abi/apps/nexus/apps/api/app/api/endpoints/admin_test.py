from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from naas_abi.apps.nexus.apps.api.app.api.endpoints.admin import router
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__schemas import (
    User,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.port import AuthUserRecord
from naas_abi.apps.nexus.apps.api.app.services.iam.testing import NexusIam

NOW = datetime(2026, 1, 1)
IAM: dict[str, NexusIam] = {}


@pytest.fixture(autouse=True)
def iam(nexus_iam: NexusIam) -> NexusIam:
    """The real IAM the routes decide with: ``user-1`` is a platform admin or not."""
    IAM["nexus"] = nexus_iam
    return nexus_iam


def _client(*, superadmin: bool, auth_service=None) -> TestClient:
    (IAM["nexus"].platform_admin if superadmin else IAM["nexus"].user)("user-1")
    app = FastAPI()
    app.include_router(router, prefix="/api/admin")
    app.dependency_overrides[get_current_user_required] = lambda: User(
        id="user-1", email="me@example.com", name="Me", is_superadmin=superadmin, created_at=NOW
    )
    return TestClient(app)


def _record(user_id: str, *, is_superadmin: bool) -> AuthUserRecord:
    return AuthUserRecord(
        id=user_id,
        email=f"{user_id}@example.com",
        name=user_id,
        created_at=NOW,
        is_superadmin=is_superadmin,
    )


def test_tables_are_superadmin_only() -> None:
    client = _client(superadmin=False, auth_service=AsyncMock())

    assert client.get("/api/admin/tables").status_code == 403
    assert client.get("/api/admin/tables/users").status_code == 403
    assert client.get("/api/admin/tables/users/schema").status_code == 403
    assert client.get("/api/admin/tables/users/rows/user-2").status_code == 403


def test_superadmin_reads_a_table_and_unknown_tables_404(monkeypatch) -> None:
    from naas_abi.apps.nexus.apps.api.app.api.endpoints import admin
    from naas_abi.apps.nexus.apps.api.app.core.database import get_db
    from naas_abi.apps.nexus.apps.api.app.core.platform_tables import (
        PlatformTable,
        UnknownPlatformTableError,
    )

    async def fake_read(_db, name: str):
        if name != "users":
            raise UnknownPlatformTableError(name=name)
        return PlatformTable(
            name="users",
            label="Users",
            description="Accounts",
            columns=["id", "hashed_password"],
            rows=[{"id": "user-2", "hashed_password": "••••••"}],
            total=1,
        )

    monkeypatch.setattr(admin, "read_platform_table", fake_read)
    client = _client(superadmin=True, auth_service=AsyncMock())
    client.app.dependency_overrides[get_db] = lambda: None

    resp = client.get("/api/admin/tables/users")
    assert resp.status_code == 200
    assert resp.json() == {
        "name": "users",
        "label": "Users",
        "description": "Accounts",
        "columns": ["id", "hashed_password"],
        "rows": [{"id": "user-2", "hashed_password": "••••••"}],
        "total": 1,
        "truncated": False,
        "primary_key": [],
    }
    assert client.get("/api/admin/tables/alembic_version").status_code == 404


def test_the_table_list_carries_labels_and_sections(monkeypatch) -> None:
    """The web app reads the tables from here, never from a copy of its own."""
    from naas_abi.apps.nexus.apps.api.app.api.endpoints import admin
    from naas_abi.apps.nexus.apps.api.app.core.database import get_db
    from naas_abi.apps.nexus.apps.api.app.core.platform_tables import PlatformTableSummary

    async def fake_list(_db):
        return [
            PlatformTableSummary(
                name="users",
                label="Users",
                section="People & access",
                description="Accounts",
                rows=2,
                columns=14,
            )
        ]

    monkeypatch.setattr(admin, "list_platform_tables", fake_list)
    client = _client(superadmin=True, auth_service=AsyncMock())
    client.app.dependency_overrides[get_db] = lambda: None

    resp = client.get("/api/admin/tables")
    assert resp.status_code == 200
    assert resp.json() == [
        {
            "name": "users",
            "label": "Users",
            "section": "People & access",
            "description": "Accounts",
            "rows": 2,
            "columns": 14,
        }
    ]


def test_superadmin_reads_a_table_schema(monkeypatch) -> None:
    from naas_abi.apps.nexus.apps.api.app.api.endpoints import admin
    from naas_abi.apps.nexus.apps.api.app.core.database import get_db
    from naas_abi.apps.nexus.apps.api.app.core.platform_tables import (
        PlatformColumn,
        PlatformTableSchema,
        UnknownPlatformTableError,
    )

    async def fake_schema(_db, name: str):
        if name != "users":
            raise UnknownPlatformTableError(name=name)
        return PlatformTableSchema(
            name="users",
            description="Accounts",
            columns=[
                PlatformColumn(
                    name="id",
                    type="VARCHAR",
                    nullable=False,
                    default=None,
                    primary_key=True,
                    references=None,
                    redacted=False,
                )
            ],
        )

    monkeypatch.setattr(admin, "read_platform_table_schema", fake_schema)
    client = _client(superadmin=True, auth_service=AsyncMock())
    client.app.dependency_overrides[get_db] = lambda: None

    resp = client.get("/api/admin/tables/users/schema")
    assert resp.status_code == 200
    assert resp.json()["columns"] == [
        {
            "name": "id",
            "type": "VARCHAR",
            "nullable": False,
            "default": None,
            "primary_key": True,
            "references": None,
            "redacted": False,
        }
    ]
    assert client.get("/api/admin/tables/alembic_version/schema").status_code == 404


def test_superadmin_reads_one_row_and_missing_rows_404(monkeypatch) -> None:
    from naas_abi.apps.nexus.apps.api.app.api.endpoints import admin
    from naas_abi.apps.nexus.apps.api.app.core.database import get_db
    from naas_abi.apps.nexus.apps.api.app.core.platform_tables import (
        PlatformTableRow,
        UnknownPlatformRowError,
        UnknownPlatformTableError,
    )

    async def fake_row(_db, name: str, row_id: str):
        if name != "users":
            raise UnknownPlatformTableError(name=name)
        if row_id != "user-2":
            raise UnknownPlatformRowError(table=name, row_id=row_id)
        return PlatformTableRow(
            name="users",
            label="Users",
            description="Accounts",
            id="user-2",
            primary_key=["id"],
            columns=["id", "hashed_password"],
            row={"id": "user-2", "hashed_password": "••••••"},
        )

    monkeypatch.setattr(admin, "read_platform_table_row", fake_row)
    client = _client(superadmin=True, auth_service=AsyncMock())
    client.app.dependency_overrides[get_db] = lambda: None

    resp = client.get("/api/admin/tables/users/rows/user-2")
    assert resp.status_code == 200
    assert resp.json()["row"] == {"id": "user-2", "hashed_password": "••••••"}
    assert resp.json()["label"] == "Users"
    assert client.get("/api/admin/tables/users/rows/nobody").json()["detail"] == "Row not found"
    assert client.get("/api/admin/tables/alembic_version/rows/x").status_code == 404
