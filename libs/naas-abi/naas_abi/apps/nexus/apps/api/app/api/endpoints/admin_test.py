from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from naas_abi.apps.nexus.apps.api.app.api.endpoints.admin import (
    get_organization_service,
    router,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (
    get_auth_service,
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__schemas import (
    User,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.port import AuthUserRecord
from naas_abi.apps.nexus.apps.api.app.services.auth.service import SuperadminChangeError
from naas_abi.apps.nexus.apps.api.app.services.organizations.port import (
    UserOrganizationMembershipRecord,
)

NOW = datetime(2026, 1, 1)


def _client(*, superadmin: bool, auth_service, organization_service=None) -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/api/admin")
    app.dependency_overrides[get_current_user_required] = lambda: User(
        id="user-1", email="me@example.com", name="Me", is_superadmin=superadmin, created_at=NOW
    )
    app.dependency_overrides[get_auth_service] = lambda: auth_service
    if organization_service is None:
        organization_service = AsyncMock()
        organization_service.list_all_memberships.return_value = []
    app.dependency_overrides[get_organization_service] = lambda: organization_service
    return TestClient(app)


def _record(user_id: str, *, is_superadmin: bool) -> AuthUserRecord:
    return AuthUserRecord(
        id=user_id,
        email=f"{user_id}@example.com",
        name=user_id,
        hashed_password="secret-hash",
        created_at=NOW,
        is_superadmin=is_superadmin,
    )


def test_non_superadmins_cannot_list_or_change_users() -> None:
    service = AsyncMock()
    client = _client(superadmin=False, auth_service=service)

    assert client.get("/api/admin/users").status_code == 403
    assert client.patch("/api/admin/users/user-2", json={"is_superadmin": True}).status_code == 403
    service.set_superadmin.assert_not_called()


def test_superadmin_lists_users_with_organizations_and_no_password_hashes() -> None:
    service = AsyncMock()
    service.list_users.return_value = [
        _record("user-2", is_superadmin=False),
        _record("user-3", is_superadmin=False),
    ]
    organizations = AsyncMock()
    organizations.list_all_memberships.return_value = [
        UserOrganizationMembershipRecord(
            user_id="user-2",
            organization_id="org-1",
            organization_name="Forvis Mazars",
            role="admin",
        )
    ]
    client = _client(superadmin=True, auth_service=service, organization_service=organizations)

    response = client.get("/api/admin/users")

    assert response.status_code == 200
    first, second = response.json()
    assert first["email"] == "user-2@example.com"
    assert "hashed_password" not in first
    assert first["organizations"] == [{"id": "org-1", "name": "Forvis Mazars", "role": "admin"}]
    assert second["organizations"] == []


def test_superadmin_promotes_a_user() -> None:
    service = AsyncMock()
    service.set_superadmin.return_value = _record("user-2", is_superadmin=True)
    client = _client(superadmin=True, auth_service=service)

    response = client.patch("/api/admin/users/user-2", json={"is_superadmin": True})

    assert response.status_code == 200
    assert response.json()["is_superadmin"] is True
    service.set_superadmin.assert_awaited_once_with(
        actor_id="user-1", user_id="user-2", is_superadmin=True
    )


def test_refused_changes_return_400() -> None:
    service = AsyncMock()
    service.set_superadmin.side_effect = SuperadminChangeError(reason="last_superadmin")
    client = _client(superadmin=True, auth_service=service)

    response = client.patch("/api/admin/users/user-2", json={"is_superadmin": False})

    assert response.status_code == 400
    assert "at least one superadmin" in response.json()["detail"]


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
        "description": "Accounts",
        "columns": ["id", "hashed_password"],
        "rows": [{"id": "user-2", "hashed_password": "••••••"}],
        "total": 1,
        "truncated": False,
        "primary_key": [],
    }
    assert client.get("/api/admin/tables/alembic_version").status_code == 404


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
    assert client.get("/api/admin/tables/users/rows/nobody").json()["detail"] == "Row not found"
    assert client.get("/api/admin/tables/alembic_version/rows/x").status_code == 404
