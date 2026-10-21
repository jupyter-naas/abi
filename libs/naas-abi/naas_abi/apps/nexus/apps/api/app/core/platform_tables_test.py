from __future__ import annotations

from datetime import datetime

import pytest
import pytest_asyncio
from naas_abi.apps.nexus.apps.api.app.core.platform_tables import (
    MAX_CELL_CHARS,
    PLATFORM_TABLES,
    REDACTED,
    UnknownPlatformRowError,
    UnknownPlatformTableError,
    _json_value,
    is_redacted,
    list_platform_tables,
    read_platform_table,
    read_platform_table_row,
    read_platform_table_schema,
    row_id,
)
from naas_abi.apps.nexus.apps.api.app.models import (
    AuthSessionModel,
    OrganizationMemberModel,
    OrganizationModel,
    UserModel,
)
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

NOW = datetime(2026, 1, 1)


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        for model in (UserModel, OrganizationModel, OrganizationMemberModel, AuthSessionModel):
            await conn.run_sync(lambda sync, m=model: m.__table__.create(sync))
    async with AsyncSession(engine) as session:
        for uid in ("alice", "bob"):
            session.add(
                UserModel(
                    id=uid,
                    email=f"{uid}@example.com",
                    name=uid.title(),
                    is_superadmin=uid == "alice",
                    created_at=NOW,
                    updated_at=NOW,
                )
            )
        session.add(
            AuthSessionModel(
                id="s1",
                user_id="alice",
                principal_id="usr_alice",
                provider="builtin",
                refresh_token_enc="sealed-refresh",
                id_token_enc="sealed-id",
                refresh_at=NOW,
                expires_at=NOW,
                created_at=NOW,
            )
        )
        await session.commit()
        yield session
    await engine.dispose()


def test_registry_lists_every_nexus_table_by_section() -> None:
    assert list(PLATFORM_TABLES) == [
        # People & access
        "users",
        "organizations",
        "organization_members",
        "organization_role_features",
        "organization_domains",
        "workspaces",
        "workspace_members",
        "workspace_resource_policies",
        "invitations",
        # Sign-in & security
        "auth_sessions",
        "secrets",
        "rate_limit_events",
        "audit_logs",
        # Chat, agents & models
        "conversations",
        "messages",
        "chat_ingestion_jobs",
        "agent_configs",
        "skills",
        "model_catalog",
        "provider_configs",
        "inference_servers",
        # Apps
        "app_configs",
        # Code
        "coding_environments",
        # Maps
        "maps_layouts",
        "maps_feed_layers",
        "maps_basemaps",
        "maps_grants",
        "maps_settings",
        # Graph
        "graph_nodes",
        "graph_edges",
        "graph_views",
        # Ontology
        "ontologies",
        "ontology_icons",
        # Search
        "search_settings",
        "search_topics",
    ]


@pytest.mark.parametrize(
    ("table", "column"),
    [
        ("auth_sessions", "refresh_token_enc"),
        ("auth_sessions", "id_token_enc"),
        ("secrets", "encrypted_value"),
        ("coding_environments", "sidecar_secret"),
        ("inference_servers", "api_key"),
        ("provider_configs", "config"),
    ],
)
def test_credentials_are_masked(table: str, column: str) -> None:
    assert is_redacted(table, column)


@pytest.mark.parametrize(
    ("table", "column"),
    [
        ("auth_sessions", "provider"),
        ("auth_sessions", "principal_id"),
        ("secrets", "key"),
        ("chat_ingestion_jobs", "file_sha256"),
        ("users", "email"),
    ],
)
def test_other_columns_stay_visible(table: str, column: str) -> None:
    assert not is_redacted(table, column)


def test_long_values_are_cut() -> None:
    value = _json_value("x" * (MAX_CELL_CHARS + 5))
    assert value.startswith("x" * MAX_CELL_CHARS)
    assert value.endswith(f"… ({MAX_CELL_CHARS + 5} chars)")


@pytest.mark.asyncio
async def test_reads_every_column_and_row_with_sealed_tokens_masked(db: AsyncSession) -> None:
    sessions = await read_platform_table(db, "auth_sessions")
    assert sessions.total == 1
    assert sessions.rows[0]["provider"] == "builtin"
    assert sessions.rows[0]["refresh_token_enc"] == REDACTED
    assert sessions.rows[0]["id_token_enc"] == REDACTED

    table = await read_platform_table(db, "users")

    assert table.name == "users"
    # Nexus keeps no password: the account has no such column.
    assert "hashed_password" not in table.columns
    assert "is_superadmin" in table.columns
    assert table.total == 2
    assert table.truncated is False
    assert {row["email"] for row in table.rows} == {"alice@example.com", "bob@example.com"}
    # SQLite hands raw text back for timestamps; Postgres datetimes become ISO.
    assert str(table.rows[0]["created_at"]).startswith("2026-01-01")


def test_json_values_are_serializable() -> None:
    assert _json_value(datetime(2026, 1, 1)) == "2026-01-01T00:00:00"
    assert _json_value(b"abc") == "<3 bytes>"
    assert _json_value(True) is True


@pytest.mark.asyncio
async def test_caps_rows_but_reports_the_total(db: AsyncSession) -> None:
    table = await read_platform_table(db, "users", limit=1)

    assert len(table.rows) == 1
    assert table.total == 2
    assert table.truncated is True


@pytest.mark.asyncio
async def test_refuses_tables_outside_the_registry(db: AsyncSession) -> None:
    with pytest.raises(UnknownPlatformTableError):
        await read_platform_table(db, "alembic_version")
    with pytest.raises(UnknownPlatformTableError):
        await read_platform_table(db, 'users"; DROP TABLE users; --')


@pytest.mark.asyncio
async def test_lists_tables_with_row_counts(db: AsyncSession) -> None:
    summaries = {s.name: s for s in await list_platform_tables(db)}

    assert summaries["users"].rows == 2
    assert summaries["users"].columns == len(UserModel.__table__.columns)
    assert summaries["organization_members"].rows == 0
    # Tables missing from this database are listed with no counts.
    assert summaries["workspaces"].rows is None
    assert summaries["workspaces"].columns is None


@pytest.mark.asyncio
async def test_schema_lists_types_keys_and_masked_columns(db: AsyncSession) -> None:
    schema = await read_platform_table_schema(db, "organization_members")
    columns = {column.name: column for column in schema.columns}

    assert columns["id"].primary_key is True
    assert columns["user_id"].references == "users.id"
    assert columns["user_id"].nullable is False
    assert columns["bio"].nullable is True
    assert "VARCHAR" in columns["name"].type.upper()

    users = await read_platform_table_schema(db, "users")
    assert [c.name for c in users.columns if c.redacted] == []
    sessions = await read_platform_table_schema(db, "auth_sessions")
    assert {c.name for c in sessions.columns if c.redacted} == {
        "refresh_token_enc",
        "id_token_enc",
    }


@pytest.mark.asyncio
async def test_schema_refuses_unknown_or_missing_tables(db: AsyncSession) -> None:
    with pytest.raises(UnknownPlatformTableError):
        await read_platform_table_schema(db, "alembic_version")
    with pytest.raises(UnknownPlatformTableError):
        await read_platform_table_schema(db, "workspaces")


@pytest.mark.asyncio
async def test_table_lists_its_primary_key(db: AsyncSession) -> None:
    table = await read_platform_table(db, "users")

    assert table.primary_key == ["id"]


def test_row_id_joins_composite_keys() -> None:
    assert row_id({"id": "user-1"}, ["id"]) == "user-1"
    assert (
        row_id({"workspace_id": "ws-1", "resource_kind": "maps"}, ["workspace_id", "resource_kind"])
        == "ws-1~maps"
    )


@pytest.mark.asyncio
async def test_reads_one_row_by_id_with_secrets_masked(db: AsyncSession) -> None:
    row = await read_platform_table_row(db, "users", "alice")

    assert row.name == "users"
    assert row.id == "alice"
    assert row.primary_key == ["id"]
    assert row.columns[0] == "id"
    assert row.row["email"] == "alice@example.com"
    sealed = await read_platform_table_row(db, "auth_sessions", "s1")
    assert sealed.row["refresh_token_enc"] == REDACTED


@pytest.mark.asyncio
async def test_missing_rows_and_bad_ids_raise(db: AsyncSession) -> None:
    with pytest.raises(UnknownPlatformRowError):
        await read_platform_table_row(db, "users", "nobody")
    with pytest.raises(UnknownPlatformRowError):
        await read_platform_table_row(db, "users", "alice~extra")
    with pytest.raises(UnknownPlatformTableError):
        await read_platform_table_row(db, "alembic_version", "x")
