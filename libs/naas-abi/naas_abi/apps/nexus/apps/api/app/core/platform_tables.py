"""Read-only view of the Nexus database tables for Platform Settings.

Platform Settings lists these tables on its Nexus tables page (``/settings/tables``),
with their row and column counts and schemas, and opens each one at
``/settings/tables/<name>``. The web app reads the list, labels and sections from
here (``GET /api/admin/tables``): this registry is the only copy.

Every table of nexus.db is either in ``PLATFORM_TABLES`` or in ``EXCLUDED_TABLES``
with the reason (a test runs the migrations and checks it). Only registered tables
can be read, so a table name from the URL is never interpolated unless it is one of
these constants. Secret columns are masked: the column stays visible, its values
never leave the API, and a row whose key is a secret cannot be opened by id.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

REDACTED = "••••••"
# Long text (messages, JSON definitions) is cut so a page stays light.
MAX_CELL_CHARS = 2000
# Joins primary key values into one row id (workspace_resource_policies has two).
ROW_ID_SEPARATOR = "~"
DEFAULT_ROW_LIMIT = 5000


@dataclass(frozen=True)
class PlatformTableEntry:
    """One table of the registry: how Platform Settings names and groups it."""

    name: str
    label: str
    section: str
    description: str


def _section(label: str, *tables: tuple[str, str, str]) -> list[PlatformTableEntry]:
    return [
        PlatformTableEntry(name=name, label=table_label, section=label, description=description)
        for name, table_label, description in tables
    ]


_ENTRIES: list[PlatformTableEntry] = [
    *_section(
        "People & access",
        (
            "users",
            "Users",
            "Accounts: email, name, identity provider link, avatar, organization, job title, "
            "bio, superadmin flag.",
        ),
        (
            "organizations",
            "Organizations",
            "Organizations with their owner, branding and login page settings.",
        ),
        (
            "organization_members",
            "Organization members",
            "Each user's profile in an organization (roles are IAM's attachments, not rows here).",
        ),
        (
            "organization_domains",
            "Organization domains",
            "Email domains of an organization, with the identity provider their sign-in goes to.",
        ),
        ("workspaces", "Workspaces", "Workspaces with their organization and owner."),
        (
            "workspace_members",
            "Workspace members",
            "Workspace members (roles are IAM's attachments, not rows here).",
        ),
        (
            "workspace_resource_policies",
            "Workspace resource policies",
            "Access rules for resources inside a workspace.",
        ),
        (
            "invitations",
            "Invitations",
            "Invitations to an organization or a workspace, pending, accepted or revoked.",
        ),
    ),
    *_section(
        "Sign-in & security",
        (
            "auth_sessions",
            "Sessions",
            "Browser sessions the API holds after a sign-in at an identity provider: one row "
            "per session, with the provider and expiry.",
        ),
        ("secrets", "Secrets", "Workspace secrets (values are encrypted)."),
        ("rate_limit_events", "Rate limit events", "Requests counted by the rate limiter."),
        ("audit_logs", "Audit logs", "Security-relevant actions: who did what, from where."),
        (
            "iam_migrations",
            "IAM migrations",
            "One-time moves of Nexus role data into IAM, with when they ran and their report.",
        ),
    ),
    *_section(
        "Chat, agents & models",
        ("conversations", "Conversations", "Chat conversations per workspace and user."),
        ("messages", "Messages", "Chat messages in each conversation."),
        (
            "chat_ingestion_jobs",
            "Chat ingestion jobs",
            "Files indexed for chat (embedding jobs and their status).",
        ),
        (
            "agent_configs",
            "Agents",
            "Agents installed in each workspace, with their model and prompt.",
        ),
        ("skills", "Skills", "Skills (reusable prompts) per workspace, organization or user."),
        ("model_catalog", "Model catalog", "Models known to the platform, with overrides."),
        ("provider_configs", "Providers", "Model provider settings per workspace."),
        (
            "inference_servers",
            "Inference servers",
            "Inference servers registered in each workspace.",
        ),
    ),
    *_section("Apps", ("app_configs", "Apps", "Apps installed in each workspace.")),
    *_section(
        "Workflows",
        (
            "workflow_run_owners",
            "Workflow runs",
            "Who started each workflow or pipeline run, from which workspace.",
        ),
    ),
    *_section(
        "Tasks",
        ("tasks", "Tasks", "Tasks of each workspace; one with no iteration is in the backlog."),
        ("task_comments", "Task comments", "Comments on each task."),
        (
            "task_activity",
            "Task activity",
            "Changes, comments and deletions of tasks: the feed, kept after a task goes.",
        ),
        ("task_iterations", "Task iterations", "Runs of whole weeks of a workspace's tasks."),
        (
            "task_settings",
            "Task settings",
            "Each workspace's tasks configuration: iterations, stages, priorities, labels.",
        ),
    ),
    *_section(
        "Code",
        (
            "coding_environments",
            "Coding environments",
            "Coding environments (sidecars) per workspace and user.",
        ),
    ),
    *_section(
        "Maps",
        ("maps_layouts", "Map feeds", "Map feeds per workspace."),
        ("maps_feed_layers", "Map feed layers", "Layers of each map feed."),
        ("maps_basemaps", "Basemaps", "Basemaps per workspace, with their preview image."),
        (
            "maps_grants",
            "Map grants",
            "Map feeds and basemaps shared with other workspaces.",
        ),
        ("maps_settings", "Maps settings", "Maps settings per workspace."),
    ),
    *_section(
        "Graph",
        ("graph_nodes", "Graph nodes", "Workspace graph nodes."),
        ("graph_edges", "Graph edges", "Workspace graph edges."),
        ("graph_views", "Graph views", "Saved graph views."),
    ),
    *_section(
        "Ontology",
        ("ontologies", "Ontologies", "Ontologies per workspace."),
        (
            "ontology_icons",
            "Ontology icons",
            "Icons chosen for ontology classes and resources.",
        ),
    ),
    *_section(
        "Search",
        ("search_settings", "Search settings", "Search settings per workspace."),
        ("search_topics", "Search topics", "Search topics per workspace."),
    ),
]

# Registry order is section order: Platform Settings lists the tables this way.
PLATFORM_TABLES: dict[str, PlatformTableEntry] = {entry.name: entry for entry in _ENTRIES}

# Tables of nexus.db (or of the models) that Platform Settings never serves, and why.
EXCLUDED_TABLES: dict[str, str] = {
    "oidc_login_requests": "Sign-ins in flight: each row is a PKCE code verifier, a nonce and "
    "hashed state, kept for minutes. Nothing in it is worth reading and all of it is secret.",
    "abi_servers": "No migration creates it (a model of the legacy ABI server routes): nexus.db "
    "has no such table.",
}

# Credentials are masked wherever they appear: password and token hashes, sign-in and
# verification tokens, PKCE verifiers and nonces, API keys, sidecar secrets and
# encrypted values.
SECRET_COLUMN = re.compile(
    r"password|secret|api_key|encrypted|verifier|nonce|_hash$|_enc$|(^|_)token$"
)

# Credential columns whose names do not look secret.
REDACTED_COLUMNS: dict[str, frozenset[str]] = {
    "provider_configs": frozenset({"config"}),  # may hold provider API keys
}


@dataclass
class UnknownPlatformTableError(LookupError):
    name: str

    def __str__(self) -> str:
        return f"unknown_platform_table:{self.name}"


@dataclass
class UnknownPlatformRowError(LookupError):
    table: str
    row_id: str

    def __str__(self) -> str:
        return f"unknown_platform_row:{self.table}:{self.row_id}"


@dataclass
class PlatformTableSummary:
    name: str
    description: str
    label: str
    section: str
    rows: int | None
    columns: int | None = None


@dataclass
class PlatformColumn:
    name: str
    type: str
    nullable: bool
    default: str | None
    primary_key: bool
    references: str | None
    redacted: bool


@dataclass
class PlatformTableSchema:
    name: str
    description: str
    columns: list[PlatformColumn]


@dataclass
class PlatformTable:
    name: str
    label: str
    description: str
    columns: list[str]
    rows: list[dict[str, Any]] = field(default_factory=list)
    total: int = 0
    truncated: bool = False
    primary_key: list[str] = field(default_factory=list)


@dataclass
class PlatformTableRow:
    name: str
    label: str
    description: str
    id: str
    primary_key: list[str]
    columns: list[str]
    row: dict[str, Any]


def row_id(row: dict[str, Any], primary_key: list[str]) -> str:
    """The id a row page uses: its primary key value(s), joined with ``~``."""
    return ROW_ID_SEPARATOR.join(str(row[column]) for column in primary_key)


def _json_value(value: Any) -> Any:
    if value is None or isinstance(value, bool | int | float):
        return value
    if isinstance(value, str):
        if len(value) > MAX_CELL_CHARS:
            return f"{value[:MAX_CELL_CHARS]}… ({len(value)} chars)"
        return value
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, bytes | bytearray | memoryview):
        return f"<{len(bytes(value))} bytes>"
    return _json_value(str(value))


def _require_known(name: str) -> str:
    if name not in PLATFORM_TABLES:
        raise UnknownPlatformTableError(name=name)
    return name


async def _count(db: AsyncSession, name: str) -> int:
    # The table name is one of the PLATFORM_TABLES constants (_require_known).
    result = await db.execute(text(f'SELECT COUNT(*) FROM "{_require_known(name)}"'))  # nosec B608
    return int(result.scalar_one())


def is_redacted(table: str, column: str) -> bool:
    return bool(SECRET_COLUMN.search(column)) or column in REDACTED_COLUMNS.get(table, frozenset())


def _masked_row(table: str, columns: list[str], values: Any) -> dict[str, Any]:
    return {
        column: (
            REDACTED if is_redacted(table, column) and value is not None else _json_value(value)
        )
        for column, value in zip(columns, values, strict=True)
    }


async def _primary_key(db: AsyncSession, table: str) -> list[str]:
    """The columns of a row id. Empty (no row pages) when a key column is a secret: its value
    would be the URL, and a lookup by it would tell whether a guessed secret exists."""
    primary_key: list[str] = await db.run_sync(
        lambda session: list(
            inspect(session.connection()).get_pk_constraint(table).get("constrained_columns") or []
        )
    )
    if any(is_redacted(table, column) for column in primary_key):
        return []
    return primary_key


async def _existing_tables(db: AsyncSession) -> set[str]:
    return set(await db.run_sync(lambda session: inspect(session.connection()).get_table_names()))


async def list_platform_tables(db: AsyncSession) -> list[PlatformTableSummary]:
    """Every table with its row and column counts (``None`` when missing here)."""
    existing = await _existing_tables(db)
    column_counts: dict[str, int] = await db.run_sync(
        lambda session: {
            name: len(inspect(session.connection()).get_columns(name))
            for name in PLATFORM_TABLES
            if name in existing
        }
    )
    summaries: list[PlatformTableSummary] = []
    for name, entry in PLATFORM_TABLES.items():
        rows: int | None = None
        if name in existing:
            try:
                rows = await _count(db, name)
            except SQLAlchemyError:
                await db.rollback()
        summaries.append(
            PlatformTableSummary(
                name=name,
                label=entry.label,
                section=entry.section,
                description=entry.description,
                rows=rows,
                columns=column_counts.get(name),
            )
        )
    return summaries


async def read_platform_table_schema(db: AsyncSession, name: str) -> PlatformTableSchema:
    """Columns with type, nullability, default, primary key and foreign key."""
    table_name = _require_known(name)
    if table_name not in await _existing_tables(db):
        raise UnknownPlatformTableError(name=table_name)

    def _inspect(session: Any) -> tuple[list[Any], list[str], list[Any]]:
        inspector = inspect(session.connection())
        return (
            list(inspector.get_columns(table_name)),
            inspector.get_pk_constraint(table_name).get("constrained_columns") or [],
            list(inspector.get_foreign_keys(table_name)),
        )

    columns, primary_key, foreign_keys = await db.run_sync(_inspect)
    references: dict[str, str] = {}
    for fk in foreign_keys:
        for local, remote in zip(
            fk.get("constrained_columns") or [], fk.get("referred_columns") or [], strict=False
        ):
            references[local] = f"{fk.get('referred_table')}.{remote}"
    return PlatformTableSchema(
        name=table_name,
        description=PLATFORM_TABLES[table_name].description,
        columns=[
            PlatformColumn(
                name=column["name"],
                type=str(column["type"]),
                nullable=bool(column.get("nullable", True)),
                default=None if column.get("default") is None else str(column["default"]),
                primary_key=column["name"] in primary_key,
                references=references.get(column["name"]),
                redacted=is_redacted(table_name, column["name"]),
            )
            for column in columns
        ],
    )


async def read_platform_table(
    db: AsyncSession, name: str, *, limit: int = DEFAULT_ROW_LIMIT
) -> PlatformTable:
    """Every column of the table and up to ``limit`` rows, secrets masked."""
    table_name = _require_known(name)
    total = await _count(db, table_name)
    # Allowlisted table name (_require_known); the limit is a bound parameter.
    result = await db.execute(
        text(f'SELECT * FROM "{table_name}" LIMIT :limit'),  # nosec B608
        {"limit": limit},
    )
    columns = list(result.keys())
    rows = [_masked_row(table_name, columns, row) for row in result.all()]
    return PlatformTable(
        name=table_name,
        label=PLATFORM_TABLES[table_name].label,
        description=PLATFORM_TABLES[table_name].description,
        columns=columns,
        rows=rows,
        total=total,
        truncated=total > len(rows),
        primary_key=await _primary_key(db, table_name),
    )


async def read_platform_table_row(db: AsyncSession, name: str, id: str) -> PlatformTableRow:
    """One row by its id (primary key value, or values joined with ``~``), secrets masked."""
    table_name = _require_known(name)
    primary_key = await _primary_key(db, table_name)
    values = id.split(ROW_ID_SEPARATOR, len(primary_key) - 1) if primary_key else []
    if not primary_key or len(values) != len(primary_key):
        raise UnknownPlatformRowError(table=table_name, row_id=id)
    # Column names come from the database catalog, values are bound parameters.
    where = " AND ".join(
        f'CAST("{column}" AS TEXT) = :key_{index}' for index, column in enumerate(primary_key)
    )
    result = await db.execute(
        # Allowlisted table, column names from the database catalog, values bound.
        text(f'SELECT * FROM "{table_name}" WHERE {where} LIMIT 1'),  # nosec B608
        {f"key_{index}": value for index, value in enumerate(values)},
    )
    found = result.first()
    if found is None:
        raise UnknownPlatformRowError(table=table_name, row_id=id)
    columns = list(result.keys())
    return PlatformTableRow(
        name=table_name,
        label=PLATFORM_TABLES[table_name].label,
        description=PLATFORM_TABLES[table_name].description,
        id=id,
        primary_key=primary_key,
        columns=columns,
        row=_masked_row(table_name, columns, found),
    )
