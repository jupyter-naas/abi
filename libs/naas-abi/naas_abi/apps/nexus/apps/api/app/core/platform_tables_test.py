from __future__ import annotations

import contextlib
import io
import re
from datetime import datetime

import pytest
import pytest_asyncio
from naas_abi.apps.nexus.apps.api.app.core import database, platform_tables
from naas_abi.apps.nexus.apps.api.app.core.database import Base
from naas_abi.apps.nexus.apps.api.app.core.platform_tables import (
    EXCLUDED_TABLES,
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
from sqlalchemy import inspect, text
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
    assert [(entry.section, entry.name) for entry in PLATFORM_TABLES.values()] == [
        ("People & access", "users"),
        ("People & access", "organizations"),
        ("People & access", "organization_members"),
        ("People & access", "organization_role_features"),
        ("People & access", "organization_domains"),
        ("People & access", "workspaces"),
        ("People & access", "workspace_members"),
        ("People & access", "workspace_resource_policies"),
        ("People & access", "invitations"),
        ("Sign-in & security", "auth_sessions"),
        ("Sign-in & security", "secrets"),
        ("Sign-in & security", "rate_limit_events"),
        ("Sign-in & security", "audit_logs"),
        ("Sign-in & security", "iam_migrations"),
        ("Chat, agents & models", "conversations"),
        ("Chat, agents & models", "messages"),
        ("Chat, agents & models", "chat_ingestion_jobs"),
        ("Chat, agents & models", "agent_configs"),
        ("Chat, agents & models", "skills"),
        ("Chat, agents & models", "model_catalog"),
        ("Chat, agents & models", "provider_configs"),
        ("Chat, agents & models", "inference_servers"),
        ("Apps", "app_configs"),
        ("Workflows", "workflow_run_owners"),
        ("Workflows", "workflow_visibility"),
        ("Code", "coding_environments"),
        ("Maps", "maps_layouts"),
        ("Maps", "maps_feed_layers"),
        ("Maps", "maps_basemaps"),
        ("Maps", "maps_grants"),
        ("Maps", "maps_settings"),
        ("Graph", "graph_nodes"),
        ("Graph", "graph_edges"),
        ("Graph", "graph_views"),
        ("Ontology", "ontologies"),
        ("Ontology", "ontology_icons"),
        ("Search", "search_settings"),
        ("Search", "search_topics"),
        ("Tasks", "tasks"),
        ("Tasks", "task_iterations"),
        ("Tasks", "task_comments"),
        ("Tasks", "task_activity"),
        ("Tasks", "task_settings"),
    ]
    # One section is one run of tables: the page groups them in this order.
    sections = [entry.section for entry in PLATFORM_TABLES.values()]
    assert sections == sorted(sections, key=sections.index)
    assert all(entry.label and entry.description for entry in PLATFORM_TABLES.values())


def test_an_excluded_table_is_never_listed() -> None:
    assert not set(EXCLUDED_TABLES) & set(PLATFORM_TABLES)
    assert all(reason.strip() for reason in EXCLUDED_TABLES.values())


@pytest_asyncio.fixture
async def nexus_db(tmp_path, monkeypatch):
    """nexus.db as the API builds it: every migration, run on SQLite."""
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'nexus.db'}")
    monkeypatch.setattr(database, "async_engine", engine)
    monkeypatch.setattr(database, "_is_sqlite", True)
    with contextlib.redirect_stdout(io.StringIO()):
        await database.init_db()
    async with AsyncSession(engine) as session:
        yield session
    await engine.dispose()


async def _columns(db: AsyncSession) -> dict[str, list[str]]:
    return await db.run_sync(
        lambda session: {
            table: [column["name"] for column in inspect(session.connection()).get_columns(table)]
            for table in inspect(session.connection()).get_table_names()
        }
    )


@pytest.mark.asyncio
async def test_every_table_of_nexus_db_is_listed_or_excluded_with_a_reason(nexus_db) -> None:
    tables = set(await _columns(nexus_db))
    # The models too: a table a model declares is one a migration may add next.
    tables |= set(Base.metadata.tables)

    unaccounted = tables - set(PLATFORM_TABLES) - set(EXCLUDED_TABLES)
    assert unaccounted == set(), (
        f"{sorted(unaccounted)}: add each to PLATFORM_TABLES, or to EXCLUDED_TABLES with the reason"
    )
    # Nothing listed is missing from a fresh database.
    assert set(PLATFORM_TABLES) - tables == set()


# Column names that may hold a credential. Each such column of a listed table is masked,
# or is named here with what it holds instead.
_LOOKS_SECRET = re.compile(r"token|secret|password|key|hash|enc|verifier|nonce|credential|config")
_NOT_SECRET: dict[tuple[str, str], str] = {
    ("secrets", "key"): "the secret's name, not its value",
    ("ontology_icons", "target_key"): "the class or resource an icon is for",
}


@pytest.mark.asyncio
async def test_every_column_that_may_hold_a_credential_is_masked(nexus_db) -> None:
    columns = await _columns(nexus_db)
    unmasked = [
        (table, column)
        for table in PLATFORM_TABLES
        for column in columns.get(table, [])
        if _LOOKS_SECRET.search(column)
        and not is_redacted(table, column)
        and (table, column) not in _NOT_SECRET
    ]
    assert unmasked == []


@pytest.mark.asyncio
async def test_a_listed_table_serves_no_secret_value(nexus_db) -> None:
    await nexus_db.execute(
        text(
            "INSERT INTO organizations (id, name, slug, owner_id, created_at, updated_at) "
            "VALUES ('org-1', 'Org', 'org', 'alice', '2026-01-01', '2026-01-01')"
        )
    )
    await nexus_db.execute(
        text(
            "INSERT INTO organization_domains (id, organization_id, domain, is_verified, "
            "verification_token, created_at) "
            "VALUES ('dom-1', 'org-1', 'example.com', 0, 'txt-proof', '2026-01-01')"
        )
    )
    await nexus_db.commit()

    table = await read_platform_table(nexus_db, "organization_domains")
    assert table.rows[0]["verification_token"] == REDACTED
    row = await read_platform_table_row(nexus_db, "organization_domains", "dom-1")
    assert row.row["verification_token"] == REDACTED
    assert "txt-proof" not in repr(table) + repr(row)


@pytest.mark.parametrize(
    ("table", "column"),
    [
        ("auth_sessions", "refresh_token_enc"),
        ("auth_sessions", "id_token_enc"),
        ("secrets", "encrypted_value"),
        ("coding_environments", "sidecar_secret"),
        ("inference_servers", "api_key"),
        ("provider_configs", "config"),
        ("organization_domains", "verification_token"),
        ("oidc_login_requests", "code_verifier"),
        ("oidc_login_requests", "nonce"),
        ("oidc_login_requests", "state_hash"),
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
        ("model_catalog", "context_window"),
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
    assert table.label == "Users"
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

    assert list(summaries) == list(PLATFORM_TABLES)
    assert summaries["users"].label == "Users"
    assert summaries["users"].section == "People & access"
    assert summaries["auth_sessions"].label == "Sessions"
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


@pytest.mark.asyncio
async def test_a_row_keyed_by_a_secret_cannot_be_opened(db: AsyncSession, monkeypatch) -> None:
    # As if a table's key were a credential (oidc_login_requests' is, and is excluded).
    monkeypatch.setitem(platform_tables.REDACTED_COLUMNS, "users", frozenset({"id"}))
    table = await read_platform_table(db, "users")
    assert table.primary_key == []
    assert {row["id"] for row in table.rows} == {REDACTED}
    with pytest.raises(UnknownPlatformRowError):
        await read_platform_table_row(db, "users", "alice")
