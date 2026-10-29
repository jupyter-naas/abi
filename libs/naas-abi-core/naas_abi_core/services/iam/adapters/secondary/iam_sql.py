"""The ``IAMStore`` on SQLAlchemy Core, shared by the SQLite and PostgreSQL adapters.

One schema, one set of statements. The adapters only build the engine: SQLite
with WAL and ``BEGIN IMMEDIATE`` for writes, PostgreSQL in its own schema.
Every write bumps ``iam_revision`` in the same transaction.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

from naas_abi_core import logger
from naas_abi_core.services.iam.catalog import ActionCatalog
from naas_abi_core.services.iam.IAMPorts import (
    Attachment,
    ContainerRecord,
    GroupMapping,
    IAMConflictError,
    IAMNotFoundError,
    IAMStore,
    KeyRecord,
    LegacyPlacement,
    LegacyScopeSet,
    ManifestRecord,
    ManifestStatus,
    NameRewriter,
    Page,
    PendingGrant,
    Placement,
    Policy,
    PrincipalKind,
    PrincipalRecord,
    RevisionConflictError,
    SigningKeyRecord,
)
from naas_abi_core.services.iam.names import (
    PLATFORM_SCOPE,
    UNRESOLVED,
    as_container,
    matches,
    within,
)
from naas_abi_core.services.iam.policy import PolicyDocument
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    and_,
    delete,
    exists,
    func,
    insert,
    inspect,
    literal,
    select,
    text,
    update,
)
from sqlalchemy.engine import Connection, Engine, Row
from sqlalchemy.exc import IntegrityError

# 2: the owner scope of policies and groups (``owner_scope``).
# 3: the sets of orgs and workspaces (``iam_scope_sets``, made by create_all).
# 4: the parent of a policy (``iam_policies.parent_id``, "Sub-policies").
# 5: no more sets: ``iam:GetSet`` and ``iam:PutSet`` leave the policies;
# ``iam_scope_sets`` stays, unread, until its rows are moved
# (``legacy_scope_sets``, ``drop_legacy_scope_sets``).
# 6: container paths: ``iam_containers``, the registry of containers, and
# ``iam_placements.container``; a placement of the old form (``org``,
# ``workspace``) waits for the rewrite of the names (``rewrite_names``).
SCHEMA_VERSION = 6

# The platform before container paths, as schemas 2 to 5 stored it.
_OLD_PLATFORM = "abi:-:-"

metadata = MetaData()

principals = Table(
    "iam_principals",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("kind", String(32), nullable=False),
    Column("status", String(16), nullable=False),
    Column("name", Text),
    # Unique service-account names: the name, set for service accounts only.
    Column("service_account_name", Text, unique=True),
    Column("issuer", Text),
    Column("subject", Text),
    Column("provider", Text),
    Column("email", Text),
    Column("email_verified", Boolean, nullable=False, default=False),
    Column("display_name", Text),
    # Before container paths: a group's org. Read by the upgrade to schema 2 only.
    Column("org", Text),
    Column("owner_id", String(64)),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("owner_scope", Text, nullable=False, default=PLATFORM_SCOPE),
    UniqueConstraint("issuer", "subject", name="iam_principals_user_identity"),
)

# Identities added to a user that holds another as its own: the users of the
# built-in login that moved to an identity provider (``IAMService.link_user``).
identity_links = Table(
    "iam_identity_links",
    metadata,
    Column("issuer", Text, primary_key=True),
    Column("subject", Text, primary_key=True),
    Column(
        "principal_id",
        String(64),
        ForeignKey("iam_principals.id", ondelete="CASCADE"),
        nullable=False,
    ),
)

group_members = Table(
    "iam_group_members",
    metadata,
    Column(
        "group_id",
        String(64),
        ForeignKey("iam_principals.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "member_id",
        String(64),
        ForeignKey("iam_principals.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

group_mappings = Table(
    "iam_group_mappings",
    metadata,
    Column("provider", String(64), primary_key=True),
    Column("claim_value", Text, primary_key=True),
    Column(
        "group_id",
        String(64),
        ForeignKey("iam_principals.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

policies = Table(
    "iam_policies",
    metadata,
    Column("id", String(255), primary_key=True),
    Column("name", Text, nullable=False),
    Column("description", Text, nullable=False, default=""),
    Column("document", Text, nullable=False),
    Column("managed", Boolean, nullable=False, default=False),
    Column("revision", Integer, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("owner_scope", Text, nullable=False, default=PLATFORM_SCOPE),
    # The policy this one is a sub-policy of; the store refuses one that does
    # not exist, and deleting a parent while it has sub-policies.
    Column("parent_id", String(255), nullable=True),
    Index("iam_policies_parent", "parent_id"),
)

attachments = Table(
    "iam_attachments",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("policy_id", String(255), ForeignKey("iam_policies.id"), nullable=False),
    Column("principal_id", String(64), ForeignKey("iam_principals.id"), nullable=False),
    # "" for an attachment without scope, so the unique constraint holds.
    Column("scope", Text, nullable=False, default=""),
    Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("policy_id", "principal_id", "scope", name="iam_attachments_once"),
)

pending_grants = Table(
    "iam_pending_grants",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("provider", String(64), nullable=False),
    Column("email", String(320), nullable=False),
    Column("policy_id", String(255), ForeignKey("iam_policies.id"), nullable=False),
    # "" for a grant without scope, so the unique constraint holds.
    Column("scope", Text, nullable=False, default=""),
    Column("created_by", String(64)),
    Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint(
        "provider", "email", "policy_id", "scope", name="iam_pending_grants_once"
    ),
)

placements = Table(
    "iam_placements",
    metadata,
    Column("service", String(64), primary_key=True),
    Column("id_key", Text, primary_key=True),
    # Before container paths: the org and the workspace (``-`` for none). A row
    # of today has both ``-`` and its ``container``.
    Column("org", String(64), nullable=False),
    Column("workspace", String(64), nullable=False),
    Column("container", Text, nullable=True),
)

containers = Table(
    "iam_containers",
    metadata,
    Column("service", String(64), primary_key=True),
    Column("type", String(64), primary_key=True),
    Column("id", Text, primary_key=True),
    Column("parent", Text, nullable=False, default=PLATFORM_SCOPE),
)

# Before container paths: the orgs and workspaces Nexus registered. Read by
# nothing; the rewrite of the names registers containers instead.
scopes = Table(
    "iam_scopes",
    metadata,
    Column("org", String(64), primary_key=True),
    Column("workspace", String(64), primary_key=True),
)

# An older version's sets (schema 3 and 4): never created any more, read once by
# whoever moves them into policies, then dropped. A part is a JSON list; NULL
# was "nothing recorded".
legacy_metadata = MetaData()
legacy_scope_sets = Table(
    "iam_scope_sets",
    legacy_metadata,
    Column("org", String(64), primary_key=True),
    Column("workspace", String(64), primary_key=True),
    Column("modules", Text, nullable=True),
    Column("features", Text, nullable=True),
)

catalogs = Table(
    "iam_catalogs",
    metadata,
    Column("service", String(64), primary_key=True),
    Column("version", Integer, nullable=False),
    Column("document", Text, nullable=False),
)

keys = Table(
    "iam_keys",
    metadata,
    Column("key_id", String(32), primary_key=True),
    Column("principal_id", String(64), ForeignKey("iam_principals.id"), nullable=False),
    Column("kind", String(16), nullable=False),
    # sha256(secret), hex: the secret has 256 bits of entropy.
    Column("secret_hash", String(64), nullable=False),
    Column("description", Text, nullable=False, default=""),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("expires_at", DateTime(timezone=True)),
    Column("last_used_at", DateTime(timezone=True)),
    Column("revoked_at", DateTime(timezone=True)),
)

# What narrows a personal or grant key. A table of its own, so
# an install that already has ``iam_keys`` needs no migration.
key_narrowing = Table(
    "iam_key_narrowing",
    metadata,
    Column("key_id", String(32), ForeignKey("iam_keys.key_id"), primary_key=True),
    Column("audience", Text),
    Column("resource", Text),
    # JSON: the token's abi_scope. NULL: no narrowing.
    Column("scope", Text),
)

# Tokens of a principal issued at or before the floor are revoked (§2: revoke
# all of a user's tokens, delegated ones included).
token_floors = Table(
    "iam_token_floors",
    metadata,
    Column(
        "principal_id", String(64), ForeignKey("iam_principals.id"), primary_key=True
    ),
    Column("not_before", DateTime(timezone=True), nullable=False),
)

manifests = Table(
    "iam_manifests",
    metadata,
    Column(
        "principal_id",
        String(64),
        ForeignKey("iam_principals.id"),
        primary_key=True,
    ),
    Column("sha256", String(64), primary_key=True),
    Column("module_id", Text, nullable=False),
    Column("project", Text, nullable=False),
    Column("document", Text, nullable=False),
    Column("status", String(16), nullable=False),
    Column("submitted_at", DateTime(timezone=True), nullable=False),
    Column("decided_at", DateTime(timezone=True)),
    Column("decided_by", String(64)),
    Column("reason", Text, nullable=False, default=""),
)

# Metadata only: the private keys live in the secret service.
signing_keys = Table(
    "iam_signing_keys",
    metadata,
    Column("kid", String(64), primary_key=True),
    Column("public_jwk", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("activates_at", DateTime(timezone=True), nullable=False),
    Column("retires_at", DateTime(timezone=True)),
)

state = Table(
    "iam_state",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("revision", BigInteger, nullable=False),
    Column("install_id", String(64), nullable=False),
    Column("schema_version", Integer, nullable=False),
)


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(value: datetime | None) -> datetime | None:
    # SQLite hands back naive datetimes; everything stored is UTC.
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _principal(row: Row) -> PrincipalRecord:
    return PrincipalRecord(
        id=row.id,
        kind=row.kind,
        status=row.status,
        name=row.name,
        issuer=row.issuer,
        subject=row.subject,
        provider=row.provider,
        email=row.email,
        email_verified=bool(row.email_verified),
        display_name=row.display_name,
        owner_id=row.owner_id,
        created_at=_aware(row.created_at),
        updated_at=_aware(row.updated_at),
        owner_scope=row.owner_scope,
    )


def _principal_values(record: PrincipalRecord) -> dict[str, Any]:
    return {
        "status": record.status,
        "name": record.name,
        "service_account_name": record.name
        if record.kind == "service_account"
        else None,
        "provider": record.provider,
        "email": record.email,
        "email_verified": record.email_verified,
        "display_name": record.display_name,
        "owner_id": record.owner_id,
    }


def _placed_in(row: Row) -> str:
    """A placement's container; one of the old form waits for the rewrite of the
    names in ``names.UNRESOLVED`` (the platform's reads as the platform)."""
    if row.container is not None:
        # Anything but a container's name (written by no IAM of today) names nothing.
        return as_container(row.container)
    if (row.org, row.workspace) == ("-", "-"):
        return PLATFORM_SCOPE
    return UNRESOLVED


def _container(row: Row) -> ContainerRecord:
    return ContainerRecord(row.service, row.type, row.id, row.parent)


def _rewrite_manifest(
    document: dict[str, Any], rewriter: NameRewriter
) -> dict[str, Any]:
    """A manifest as stored (``modules.split_manifest``: its policy, and its
    catalog under ``catalog``), its policy's names rewritten."""
    policy = {k: v for k, v in document.items() if k != "catalog"}
    rewritten = dict(rewriter.document(policy))
    if "catalog" in document:
        rewritten["catalog"] = document["catalog"]
    return rewritten


def _policy(row: Row) -> Policy:
    return Policy(
        id=row.id,
        name=row.name,
        description=row.description,
        document=PolicyDocument.from_dict(json.loads(row.document)),
        managed=bool(row.managed),
        revision=row.revision,
        created_at=_aware(row.created_at),
        updated_at=_aware(row.updated_at),
        owner_scope=row.owner_scope,
        parent_id=row.parent_id,
    )


def _attachment(row: Row) -> Attachment:
    return Attachment(
        id=row.id,
        policy_id=row.policy_id,
        principal_id=row.principal_id,
        scope=row.scope or None,
        created_at=_aware(row.created_at),
    )


def _pending_grant(row: Row) -> PendingGrant:
    return PendingGrant(
        id=row.id,
        provider=row.provider,
        email=row.email,
        policy_id=row.policy_id,
        scope=row.scope or None,
        created_by=row.created_by,
        created_at=_aware(row.created_at),
    )


def _key(row: Row) -> KeyRecord:
    scope = json.loads(row.scope) if row.scope is not None else None
    return KeyRecord(
        key_id=row.key_id,
        principal_id=row.principal_id,
        secret_hash=row.secret_hash,
        kind=row.kind,
        description=row.description,
        created_at=_aware(row.created_at),
        expires_at=_aware(row.expires_at),
        last_used_at=_aware(row.last_used_at),
        revoked_at=_aware(row.revoked_at),
        audience=row.audience,
        resource=row.resource,
        scope=tuple(scope) if scope is not None else None,
    )


def _manifest(row: Row) -> ManifestRecord:
    return ManifestRecord(
        principal_id=row.principal_id,
        sha256=row.sha256,
        module_id=row.module_id,
        project=row.project,
        document=json.loads(row.document),
        status=row.status,
        submitted_at=_aware(row.submitted_at),
        decided_at=_aware(row.decided_at),
        decided_by=row.decided_by,
        reason=row.reason,
    )


def _signing_key(row: Row) -> SigningKeyRecord:
    return SigningKeyRecord(
        kid=row.kid,
        public_jwk=json.loads(row.public_jwk),
        created_at=_aware(row.created_at),  # type: ignore[arg-type]
        activates_at=_aware(row.activates_at),  # type: ignore[arg-type]
        retires_at=_aware(row.retires_at),
    )


def _list_json(raw: str | None) -> tuple[str, ...] | None:
    if raw is None:
        return None
    return tuple(str(item) for item in json.loads(raw))


def _check_limit(limit: int) -> None:
    if not 1 <= limit <= 1000:
        raise ValueError("limit must be between 1 and 1000")


class IAMStoreSQL(IAMStore):
    """Subclasses pass an engine; ``_write_options`` selects the write transaction."""

    _write_options: dict[str, Any] = {}

    def __init__(self, engine: Engine, *, schema: str | None = None) -> None:
        self._engine = engine
        self._schema = schema
        self._closed = False
        with engine.begin() as conn:
            if conn.dialect.name == "postgresql":
                # Two processes opening one store (the engine and the API): the
                # second waits here while the first creates a missing table.
                conn.execute(
                    text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
                    {"key": f"abi_iam_schema:{schema or ''}"},
                )
            metadata.create_all(conn)
        with self._write() as conn:
            if conn.execute(select(state.c.id)).first() is None:
                conn.execute(
                    insert(state).values(
                        id=1,
                        revision=0,
                        install_id=uuid.uuid4().hex,
                        schema_version=SCHEMA_VERSION,
                    )
                )
            else:
                self._migrate(conn)

    # -- migrations ---------------------------------------------------------------

    def _migrate(self, conn: Connection) -> None:
        """Bring a store of an earlier schema version up to ``SCHEMA_VERSION``."""
        version = int(conn.execute(select(state.c.schema_version)).scalar() or 1)
        if version < 2:
            self._migrate_owner_scopes(conn)
        if version < 4:
            self._migrate_parents(conn)
        if version < 5:
            self._migrate_set_actions(conn)
        if version < 6:
            self._migrate_containers(conn)
        if version < SCHEMA_VERSION:
            conn.execute(update(state).values(schema_version=SCHEMA_VERSION))

    def _migrate_owner_scopes(self, conn: Connection) -> None:
        """2: every policy and group is owned by the platform, except the groups
        IdP bindings made (``idp:<provider>:<claim value>``, mapped from that
        claim) whose attachments are all in the org they were made for, which
        belong to that org. A binding group also bound elsewhere (another org,
        the platform, unscoped) stays the platform's: an org's admins could
        otherwise hand those grants to their users."""
        postgres = conn.dialect.name == "postgresql"
        for table in (principals, policies):
            name = f'"{self._schema}".{table.name}' if self._schema else table.name
            if postgres:
                # Two processes opening a version 1 store together: the second
                # finds the column the first added.
                add = "ADD COLUMN IF NOT EXISTS"
            else:
                columns = {
                    c["name"]
                    for c in inspect(conn).get_columns(table.name, schema=self._schema)
                }
                if "owner_scope" in columns:
                    continue
                add = "ADD COLUMN"
            conn.execute(
                text(
                    f"ALTER TABLE {name} {add} owner_scope TEXT NOT NULL "
                    f"DEFAULT '{PLATFORM_SCOPE}'"
                )
            )
        made_by_binding = exists().where(
            group_mappings.c.group_id == principals.c.id,
            literal("idp:")
            + group_mappings.c.provider
            + literal(":")
            + group_mappings.c.claim_value
            == principals.c.name,
        )
        in_org = literal("abi:") + principals.c.org + literal(":")
        held_elsewhere = exists().where(
            attachments.c.principal_id == principals.c.id,
            func.substr(attachments.c.scope, 1, func.length(in_org)) != in_org,
        )
        conn.execute(
            update(principals)
            .where(
                principals.c.kind == "group",
                principals.c.org.is_not(None),
                made_by_binding,
                ~held_elsewhere,
            )
            .values(owner_scope=literal("abi:") + principals.c.org + literal(":-"))
        )
        self._warn_old_platform_names(conn)

    def _migrate_parents(self, conn: Connection) -> None:
        """4: every policy starts with no parent (``parent_id`` NULL), indexed
        to list a policy's sub-policies."""
        name = f'"{self._schema}".{policies.name}' if self._schema else policies.name
        add: str | None
        if conn.dialect.name == "postgresql":
            # The schema's advisory lock serializes two processes opening it, and
            # a second one finds the column there.
            add = "ADD COLUMN IF NOT EXISTS"
        else:
            columns = {
                c["name"]
                for c in inspect(conn).get_columns(policies.name, schema=self._schema)
            }
            add = None if "parent_id" in columns else "ADD COLUMN"
        if add is not None:
            conn.execute(text(f"ALTER TABLE {name} {add} parent_id VARCHAR(255)"))
        conn.execute(
            text(
                f"CREATE INDEX IF NOT EXISTS iam_policies_parent ON {name} (parent_id)"
            )
        )

    def _migrate_set_actions(self, conn: Connection) -> None:
        """5: the sets are gone (IAM's catalog 7): ``iam:GetSet`` and
        ``iam:PutSet`` are taken out of the customer policies that named them, a
        statement left with no action with them. They authorized nothing else,
        so no decision changes; without this the catalog would refuse dropping
        actions a policy still names."""
        gone = {"iam:GetSet", "iam:PutSet"}
        for row in conn.execute(
            select(policies.c.id, policies.c.document).where(
                policies.c.managed.is_(False)
            )
        ):
            document = PolicyDocument.from_dict(json.loads(row.document))
            if not any(a in gone for s in document.statements for a in s.actions):
                continue
            kept = tuple(
                replace(statement, actions=actions)
                for statement in document.statements
                if (actions := tuple(a for a in statement.actions if a not in gone))
            )
            conn.execute(
                update(policies)
                .where(policies.c.id == row.id)
                .values(
                    document=replace(document, statements=kept).to_json(),
                    revision=policies.c.revision + 1,
                    updated_at=_now(),
                )
            )
            logger.info(
                f"IAM policy {row.id}: iam:GetSet and iam:PutSet taken out, the "
                "sets they read and wrote are gone"
            )
        conn.execute(update(state).values(revision=state.c.revision + 1))

    def _migrate_containers(self, conn: Connection) -> None:
        """6: ``iam_placements.container`` (``iam_containers`` is created with
        the metadata). A placement of the old form keeps its org and workspace
        until the names are rewritten; the platform's reads as the platform."""
        name = (
            f'"{self._schema}".{placements.name}' if self._schema else placements.name
        )
        add: str | None
        if conn.dialect.name == "postgresql":
            add = "ADD COLUMN IF NOT EXISTS"
        else:
            columns = {
                c["name"]
                for c in inspect(conn).get_columns(placements.name, schema=self._schema)
            }
            add = None if "container" in columns else "ADD COLUMN"
        if add is not None:
            conn.execute(text(f"ALTER TABLE {name} {add} container TEXT"))
        conn.execute(
            update(placements)
            .where(
                placements.c.container.is_(None),
                placements.c.org == "-",
                placements.c.workspace == "-",
            )
            .values(container=PLATFORM_SCOPE)
        )
        # The old platform, ``abi:-:-``, is the platform ``abi:``: as an owner
        # (every platform policy and group of schema 5) and as a scope.
        for table, column in (
            (policies, policies.c.owner_scope),
            (principals, principals.c.owner_scope),
            (attachments, attachments.c.scope),
            (pending_grants, pending_grants.c.scope),
        ):
            conn.execute(
                update(table)
                .where(column == _OLD_PLATFORM)
                .values({column.name: PLATFORM_SCOPE})
            )

    def _warn_old_platform_names(self, conn: Connection) -> None:
        """Schema 2 names the platform's policies and groups
        ``abi:%2A:%2A:iam:<type>/<id>``: a stored customer policy that reached
        them as ``abi:-:-:iam:…`` (or ``${scope}:iam:…`` attached at
        ``abi:-:-``) matches nothing of them any more."""

        def names(type_name: str, item_id: str, owner: str) -> tuple[str, str]:
            # The grammar of schema 1 and 2, written out: a store this old
            # predates container paths, and is rewritten after this.
            return (
                f"abi:-:-:iam:{type_name}/{item_id}",
                f"abi:%2A:%2A:iam:{type_name}/{item_id}",
            )

        renamed = [
            names("policy", row.id, row.owner_scope)
            for row in conn.execute(select(policies.c.id, policies.c.owner_scope))
        ] + [
            names("group", row.id, row.owner_scope)
            for row in conn.execute(
                select(principals.c.id, principals.c.owner_scope).where(
                    principals.c.kind == "group"
                )
            )
        ]
        for row in conn.execute(
            select(policies.c.id, policies.c.document).where(
                policies.c.managed.is_(False)
            )
        ):
            document = PolicyDocument.from_dict(json.loads(row.document))
            stale = sorted(
                {
                    pattern
                    for statement in document.statements
                    for pattern in statement.resources
                    if any(
                        matches(probe, old) and not matches(probe, new)
                        for probe in [pattern.replace("${scope}", "abi:-:-")]
                        for old, new in renamed
                    )
                }
            )
            if stale:
                logger.warning(
                    f"IAM policy {row.id} names the platform's policies or groups "
                    f"as {', '.join(stale)}: the platform's are named "
                    "abi:%2A:%2A:iam:<type>/<id> now (an org's or a workspace's "
                    "abi:<org>:<ws>:iam:...), so these patterns no longer match "
                    "them. Write abi:*:*:iam:policy/... or ...:iam:group/..."
                )

    # -- transactions -------------------------------------------------------------

    @contextmanager
    def _read(self) -> Iterator[Connection]:
        if self._closed:
            raise RuntimeError("IAM store is closed")
        with self._engine.connect() as conn:
            yield conn

    @contextmanager
    def _write(self) -> Iterator[Connection]:
        if self._closed:
            raise RuntimeError("IAM store is closed")
        engine = self._engine.execution_options(**self._write_options)
        with engine.begin() as conn:
            yield conn

    @contextmanager
    def _change(self) -> Iterator[Connection]:
        """A write that bumps the revision; unique violations become conflicts.

        It locks the state row first, so writes are serialized (SQLite's
        ``BEGIN IMMEDIATE`` already does it): a check made inside one, such as a
        parent existing or a policy having no sub-policies, still holds when it
        commits, whatever PostgreSQL's isolation level."""
        try:
            with self._write() as conn:
                conn.execute(select(state.c.id).with_for_update())
                yield conn
                conn.execute(update(state).values(revision=state.c.revision + 1))
        except IntegrityError as exc:
            raise IAMConflictError(f"IAM store refused the write: {exc.orig}") from exc

    # -- principals -------------------------------------------------------------

    def create_principal(self, record: PrincipalRecord) -> PrincipalRecord:
        now = _now()
        with self._change() as conn:
            if conn.execute(
                select(principals.c.id).where(principals.c.id == record.id)
            ).first():
                raise IAMConflictError(f"Principal {record.id} exists")
            conn.execute(
                insert(principals).values(
                    id=record.id,
                    kind=record.kind,
                    issuer=record.issuer,
                    subject=record.subject,
                    owner_scope=record.owner_scope,
                    created_at=now,
                    updated_at=now,
                    **_principal_values(record),
                )
            )
        return self.get_principal(record.id)

    def get_principal(self, principal_id: str) -> PrincipalRecord:
        with self._read() as conn:
            row = conn.execute(
                select(principals).where(principals.c.id == principal_id)
            ).first()
        if row is None:
            raise IAMNotFoundError(f"Principal {principal_id} not found")
        return _principal(row)

    def find_user(self, issuer: str, subject: str) -> PrincipalRecord | None:
        with self._read() as conn:
            row = conn.execute(
                select(principals)
                .join(identity_links, identity_links.c.principal_id == principals.c.id)
                .where(
                    identity_links.c.issuer == issuer,
                    identity_links.c.subject == subject,
                )
            ).first()
            if row is None:
                row = conn.execute(
                    select(principals).where(
                        principals.c.kind == "user",
                        principals.c.issuer == issuer,
                        principals.c.subject == subject,
                    )
                ).first()
        return _principal(row) if row is not None else None

    def linked_identities(self, principal_id: str) -> list[tuple[str, str]]:
        with self._read() as conn:
            rows = conn.execute(
                select(identity_links.c.issuer, identity_links.c.subject).where(
                    identity_links.c.principal_id == principal_id
                )
            ).all()
        return sorted((row.issuer, row.subject) for row in rows)

    def link_identity(self, issuer: str, subject: str, principal_id: str) -> None:
        with self._read() as conn:
            row = conn.execute(
                select(principals.c.kind).where(principals.c.id == principal_id)
            ).first()
            held = conn.execute(
                select(identity_links.c.principal_id).where(
                    identity_links.c.issuer == issuer,
                    identity_links.c.subject == subject,
                )
            ).first()
        if row is None:
            raise IAMNotFoundError(f"Principal {principal_id} not found")
        if row.kind != "user":
            raise IAMConflictError(f"{principal_id} is not a user")
        if held is not None:
            if held.principal_id == principal_id:
                return
            raise IAMConflictError("This identity is linked to another user")
        with self._change() as conn:
            conn.execute(
                insert(identity_links).values(
                    issuer=issuer, subject=subject, principal_id=principal_id
                )
            )

    def find_service_account(self, name: str) -> PrincipalRecord | None:
        with self._read() as conn:
            row = conn.execute(
                select(principals).where(principals.c.service_account_name == name)
            ).first()
        return _principal(row) if row is not None else None

    def list_principals(
        self,
        kind: PrincipalKind | None = None,
        *,
        limit: int = 100,
        after: str | None = None,
        owner_scopes: Sequence[str] | None = None,
    ) -> Page:
        _check_limit(limit)
        query = select(principals).order_by(principals.c.id).limit(limit + 1)
        if kind is not None:
            query = query.where(principals.c.kind == kind)
        if owner_scopes is not None:
            query = query.where(principals.c.owner_scope.in_(list(owner_scopes)))
        if after is not None:
            query = query.where(principals.c.id > after)
        with self._read() as conn:
            rows = [_principal(row) for row in conn.execute(query)]
        return _page(rows, limit)

    def update_principal(self, record: PrincipalRecord) -> PrincipalRecord:
        with self._change() as conn:
            result = conn.execute(
                update(principals)
                .where(principals.c.id == record.id)
                .values(updated_at=_now(), **_principal_values(record))
            )
            if result.rowcount == 0:
                raise IAMNotFoundError(f"Principal {record.id} not found")
        return self.get_principal(record.id)

    # -- groups -------------------------------------------------------------------

    def _require(self, conn: Connection, *principal_ids: str) -> None:
        for principal_id in principal_ids:
            if not conn.execute(
                select(principals.c.id).where(principals.c.id == principal_id)
            ).first():
                raise IAMNotFoundError(f"Principal {principal_id} not found")

    def add_group_member(self, group_id: str, member_id: str) -> None:
        with self._read() as conn:
            exists = conn.execute(
                select(group_members.c.group_id).where(
                    group_members.c.group_id == group_id,
                    group_members.c.member_id == member_id,
                )
            ).first()
        if exists:
            return
        with self._change() as conn:
            self._require(conn, group_id, member_id)
            conn.execute(
                insert(group_members).values(group_id=group_id, member_id=member_id)
            )

    def remove_group_member(self, group_id: str, member_id: str) -> bool:
        return self._delete(
            delete(group_members).where(
                group_members.c.group_id == group_id,
                group_members.c.member_id == member_id,
            )
        )

    def list_group_members(self, group_id: str) -> list[str]:
        with self._read() as conn:
            return list(
                conn.scalars(
                    select(group_members.c.member_id)
                    .where(group_members.c.group_id == group_id)
                    .order_by(group_members.c.member_id)
                )
            )

    def groups_of(self, member_id: str) -> list[str]:
        with self._read() as conn:
            return list(
                conn.scalars(
                    select(group_members.c.group_id)
                    .where(group_members.c.member_id == member_id)
                    .order_by(group_members.c.group_id)
                )
            )

    def map_idp_group(self, mapping: GroupMapping) -> None:
        key = and_(
            group_mappings.c.provider == mapping.provider,
            group_mappings.c.claim_value == mapping.claim_value,
            group_mappings.c.group_id == mapping.group_id,
        )
        with self._read() as conn:
            if conn.execute(select(group_mappings.c.provider).where(key)).first():
                return
        with self._change() as conn:
            self._require(conn, mapping.group_id)
            conn.execute(
                insert(group_mappings).values(
                    provider=mapping.provider,
                    claim_value=mapping.claim_value,
                    group_id=mapping.group_id,
                )
            )

    def unmap_idp_group(self, mapping: GroupMapping) -> bool:
        return self._delete(
            delete(group_mappings).where(
                group_mappings.c.provider == mapping.provider,
                group_mappings.c.claim_value == mapping.claim_value,
                group_mappings.c.group_id == mapping.group_id,
            )
        )

    def list_idp_group_mappings(
        self, group_id: str | None = None
    ) -> list[GroupMapping]:
        query = select(group_mappings).order_by(
            group_mappings.c.provider,
            group_mappings.c.claim_value,
            group_mappings.c.group_id,
        )
        if group_id is not None:
            query = query.where(group_mappings.c.group_id == group_id)
        with self._read() as conn:
            return [
                GroupMapping(row.provider, row.claim_value, row.group_id)
                for row in conn.execute(query)
            ]

    def resolve_idp_groups(
        self, provider: str, claim_values: Iterable[str]
    ) -> list[str]:
        values = sorted(set(claim_values))
        if not values:
            return []
        with self._read() as conn:
            return sorted(
                set(
                    conn.scalars(
                        select(group_mappings.c.group_id).where(
                            group_mappings.c.provider == provider,
                            group_mappings.c.claim_value.in_(values),
                        )
                    )
                )
            )

    # -- policies -----------------------------------------------------------------

    def create_policy(self, policy: Policy) -> Policy:
        now = _now()
        with self._change() as conn:
            if conn.execute(
                select(policies.c.id).where(policies.c.id == policy.id)
            ).first():
                raise IAMConflictError(f"Policy {policy.id} exists")
            self._require_parent(conn, policy.parent_id)
            conn.execute(
                insert(policies).values(
                    id=policy.id,
                    name=policy.name,
                    description=policy.description,
                    document=policy.document.to_json(),
                    managed=policy.managed,
                    revision=1,
                    owner_scope=policy.owner_scope,
                    parent_id=policy.parent_id,
                    created_at=now,
                    updated_at=now,
                )
            )
        return self.get_policy(policy.id)

    def get_policy(self, policy_id: str) -> Policy:
        with self._read() as conn:
            row = conn.execute(
                select(policies).where(policies.c.id == policy_id)
            ).first()
        if row is None:
            raise IAMNotFoundError(f"Policy {policy_id} not found")
        return _policy(row)

    def list_policies(
        self,
        *,
        limit: int = 100,
        after: str | None = None,
        owner_scopes: Sequence[str] | None = None,
    ) -> Page:
        _check_limit(limit)
        query = select(policies).order_by(policies.c.id).limit(limit + 1)
        if owner_scopes is not None:
            query = query.where(policies.c.owner_scope.in_(list(owner_scopes)))
        if after is not None:
            query = query.where(policies.c.id > after)
        with self._read() as conn:
            rows = [_policy(row) for row in conn.execute(query)]
        return _page(rows, limit)

    def update_policy(self, policy: Policy, expected_revision: int) -> Policy:
        with self._change() as conn:
            self._require_parent(conn, policy.parent_id)
            result = conn.execute(
                update(policies)
                .where(
                    policies.c.id == policy.id,
                    policies.c.revision == expected_revision,
                )
                .values(
                    name=policy.name,
                    description=policy.description,
                    document=policy.document.to_json(),
                    parent_id=policy.parent_id,
                    revision=policies.c.revision + 1,
                    updated_at=_now(),
                )
            )
            if result.rowcount == 0:
                current = conn.execute(
                    select(policies.c.revision).where(policies.c.id == policy.id)
                ).scalar()
                if current is None:
                    raise IAMNotFoundError(f"Policy {policy.id} not found")
                raise RevisionConflictError(
                    f"Policy {policy.id} is at revision {current}, "
                    f"not {expected_revision}"
                )
        return self.get_policy(policy.id)

    def put_managed_policy(self, policy: Policy) -> Policy:
        document = policy.document.to_json()
        with self._read() as conn:
            row = conn.execute(
                select(policies).where(policies.c.id == policy.id)
            ).first()
        if row is not None and (row.name, row.description, row.document) == (
            policy.name,
            policy.description,
            document,
        ):
            return _policy(row)
        now = _now()
        with self._change() as conn:
            if row is None:
                conn.execute(
                    insert(policies).values(
                        id=policy.id,
                        name=policy.name,
                        description=policy.description,
                        document=document,
                        managed=True,
                        revision=1,
                        owner_scope=policy.owner_scope,
                        created_at=now,
                        updated_at=now,
                    )
                )
            else:
                conn.execute(
                    update(policies)
                    .where(policies.c.id == policy.id)
                    .values(
                        name=policy.name,
                        description=policy.description,
                        document=document,
                        managed=True,
                        revision=policies.c.revision + 1,
                        updated_at=now,
                    )
                )
        return self.get_policy(policy.id)

    def delete_policy(self, policy_id: str) -> None:
        with self._change() as conn:
            if conn.execute(
                select(attachments.c.id).where(attachments.c.policy_id == policy_id)
            ).first():
                raise IAMConflictError(f"Policy {policy_id} is attached")
            if conn.execute(
                select(pending_grants.c.id).where(
                    pending_grants.c.policy_id == policy_id
                )
            ).first():
                raise IAMConflictError(f"Policy {policy_id} is granted to invitees")
            if conn.execute(
                select(policies.c.id).where(policies.c.parent_id == policy_id)
            ).first():
                raise IAMConflictError(f"Policy {policy_id} has sub-policies")
            result = conn.execute(delete(policies).where(policies.c.id == policy_id))
            if result.rowcount == 0:
                raise IAMNotFoundError(f"Policy {policy_id} not found")

    def list_sub_policies(self, policy_id: str) -> list[Policy]:
        with self._read() as conn:
            return [
                _policy(row)
                for row in conn.execute(
                    select(policies)
                    .where(policies.c.parent_id == policy_id)
                    .order_by(policies.c.id)
                )
            ]

    @staticmethod
    def _require_parent(conn: Connection, parent_id: str | None) -> None:
        if (
            parent_id is not None
            and not conn.execute(
                select(policies.c.id).where(policies.c.id == parent_id)
            ).first()
        ):
            raise IAMNotFoundError(f"Policy {parent_id} not found")

    # -- attachments --------------------------------------------------------------

    def attach(self, attachment: Attachment) -> Attachment:
        with self._change() as conn:
            if not conn.execute(
                select(policies.c.id).where(policies.c.id == attachment.policy_id)
            ).first():
                raise IAMNotFoundError(f"Policy {attachment.policy_id} not found")
            self._require(conn, attachment.principal_id)
            conn.execute(
                insert(attachments).values(
                    id=attachment.id,
                    policy_id=attachment.policy_id,
                    principal_id=attachment.principal_id,
                    scope=attachment.scope or "",
                    created_at=_now(),
                )
            )
        with self._read() as conn:
            row = conn.execute(
                select(attachments).where(attachments.c.id == attachment.id)
            ).one()
        return _attachment(row)

    def detach(self, policy_id: str, principal_id: str, scope: str | None) -> bool:
        return self._delete(
            delete(attachments).where(
                attachments.c.policy_id == policy_id,
                attachments.c.principal_id == principal_id,
                attachments.c.scope == (scope or ""),
            )
        )

    def list_attachments(
        self, *, principal_id: str | None = None, policy_id: str | None = None
    ) -> list[Attachment]:
        query = select(attachments).order_by(attachments.c.id)
        if principal_id is not None:
            query = query.where(attachments.c.principal_id == principal_id)
        if policy_id is not None:
            query = query.where(attachments.c.policy_id == policy_id)
        with self._read() as conn:
            return [_attachment(row) for row in conn.execute(query)]

    def attachments_for(self, principal_ids: Sequence[str]) -> list[Attachment]:
        if not principal_ids:
            return []
        with self._read() as conn:
            return [
                _attachment(row)
                for row in conn.execute(
                    select(attachments)
                    .where(attachments.c.principal_id.in_(list(principal_ids)))
                    .order_by(attachments.c.id)
                )
            ]

    def attachments_of(self, policy_ids: Sequence[str]) -> list[Attachment]:
        if not policy_ids:
            return []
        with self._read() as conn:
            return [
                _attachment(row)
                for row in conn.execute(
                    select(attachments)
                    .where(attachments.c.policy_id.in_(list(policy_ids)))
                    .order_by(attachments.c.id)
                )
            ]

    # -- pending grants -----------------------------------------------------------

    def add_pending_grant(self, grant: PendingGrant) -> PendingGrant:
        with self._change() as conn:
            if not conn.execute(
                select(policies.c.id).where(policies.c.id == grant.policy_id)
            ).first():
                raise IAMNotFoundError(f"Policy {grant.policy_id} not found")
            conn.execute(
                insert(pending_grants).values(
                    id=grant.id,
                    provider=grant.provider,
                    email=grant.email,
                    policy_id=grant.policy_id,
                    scope=grant.scope or "",
                    created_by=grant.created_by,
                    created_at=_now(),
                )
            )
        with self._read() as conn:
            row = conn.execute(
                select(pending_grants).where(pending_grants.c.id == grant.id)
            ).one()
        return _pending_grant(row)

    def list_pending_grants(
        self,
        *,
        provider: str | None = None,
        email: str | None = None,
        policy_id: str | None = None,
    ) -> list[PendingGrant]:
        query = select(pending_grants).order_by(pending_grants.c.id)
        if provider is not None:
            query = query.where(pending_grants.c.provider == provider)
        if email is not None:
            query = query.where(pending_grants.c.email == email)
        if policy_id is not None:
            query = query.where(pending_grants.c.policy_id == policy_id)
        with self._read() as conn:
            return [_pending_grant(row) for row in conn.execute(query)]

    def get_pending_grant(self, grant_id: str) -> PendingGrant | None:
        with self._read() as conn:
            row = conn.execute(
                select(pending_grants).where(pending_grants.c.id == grant_id)
            ).first()
        return _pending_grant(row) if row is not None else None

    def remove_pending_grant(self, grant_id: str) -> bool:
        return self._delete(
            delete(pending_grants).where(pending_grants.c.id == grant_id)
        )

    def claim_pending_grant(
        self, grant_id: str, principal_id: str, attachment_id: str
    ) -> Attachment | None:
        with self._change() as conn:
            row = conn.execute(
                select(pending_grants).where(pending_grants.c.id == grant_id)
            ).first()
            if row is None:
                return None
            self._require(conn, principal_id)
            # The delete is the claim: of two racing claims, one removes the row.
            if (
                conn.execute(
                    delete(pending_grants).where(pending_grants.c.id == grant_id)
                ).rowcount
                == 0
            ):
                return None
            held = conn.execute(
                select(attachments).where(
                    attachments.c.policy_id == row.policy_id,
                    attachments.c.principal_id == principal_id,
                    attachments.c.scope == row.scope,
                )
            ).first()
            if held is None:
                conn.execute(
                    insert(attachments).values(
                        id=attachment_id,
                        policy_id=row.policy_id,
                        principal_id=principal_id,
                        scope=row.scope,
                        created_at=_now(),
                    )
                )
        with self._read() as conn:
            found = conn.execute(
                select(attachments).where(
                    attachments.c.policy_id == row.policy_id,
                    attachments.c.principal_id == principal_id,
                    attachments.c.scope == row.scope,
                )
            ).one()
        return _attachment(found)

    # -- placements and scopes ----------------------------------------------------

    def put_placement(self, placement: Placement) -> None:
        key = (placements.c.service == placement.service) & (
            placements.c.id_key == placement.id_key
        )
        with self._read() as conn:
            row = conn.execute(select(placements).where(key)).first()
        if row is not None and row.container == placement.container:
            return
        with self._change() as conn:
            conn.execute(delete(placements).where(key))
            conn.execute(
                insert(placements).values(
                    service=placement.service,
                    id_key=placement.id_key,
                    org="-",
                    workspace="-",
                    container=placement.container,
                )
            )

    def delete_placement(self, service: str, id_key: str) -> bool:
        return self._delete(
            delete(placements).where(
                placements.c.service == service, placements.c.id_key == id_key
            )
        )

    def list_placements(self, service: str | None = None) -> list[Placement]:
        query = select(placements).order_by(placements.c.service, placements.c.id_key)
        if service is not None:
            query = query.where(placements.c.service == service)
        with self._read() as conn:
            return [
                Placement(row.service, row.id_key, _placed_in(row))
                for row in conn.execute(query)
            ]

    def put_container(self, record: ContainerRecord) -> None:
        key = (
            (containers.c.service == record.service)
            & (containers.c.type == record.type)
            & (containers.c.id == record.id)
        )
        with self._read() as conn:
            row = conn.execute(select(containers).where(key)).first()
        if row is not None:
            if row.parent != record.parent:
                raise IAMConflictError(
                    f"{record.service}:{record.type}/{record.id} is in {row.parent}"
                )
            return
        with self._change() as conn:
            conn.execute(
                insert(containers).values(
                    service=record.service,
                    type=record.type,
                    id=record.id,
                    parent=record.parent,
                )
            )

    def get_container(self, service: str, type: str, id: str) -> ContainerRecord | None:
        with self._read() as conn:
            row = conn.execute(
                select(containers).where(
                    containers.c.service == service,
                    containers.c.type == type,
                    containers.c.id == id,
                )
            ).first()
        return _container(row) if row is not None else None

    def list_containers(self) -> list[ContainerRecord]:
        with self._read() as conn:
            return [
                _container(row)
                for row in conn.execute(
                    select(containers).order_by(
                        containers.c.service, containers.c.type, containers.c.id
                    )
                )
            ]

    def delete_containers(self, records: Sequence[ContainerRecord]) -> int:
        if not records:
            return 0
        names = {record.name for record in records}
        with self._change() as conn:
            for record in records:
                conn.execute(
                    delete(containers).where(
                        containers.c.service == record.service,
                        containers.c.type == record.type,
                        containers.c.id == record.id,
                    )
                )
            for row in conn.execute(select(placements)).all():
                if row.container is not None and any(
                    within(row.container, name) for name in names
                ):
                    conn.execute(
                        delete(placements).where(
                            placements.c.service == row.service,
                            placements.c.id_key == row.id_key,
                        )
                    )
        return len(records)

    # -- the names before container paths -------------------------------------------

    def rewrite_names(self, rewriter: NameRewriter) -> dict[str, int]:
        counts = dict.fromkeys(
            (
                "containers",
                "policies",
                "groups",
                "attachments",
                "pending_grants",
                "placements",
                "keys",
                "manifests",
            ),
            0,
        )
        with self._change() as conn:
            for record in rewriter.containers():
                found = conn.execute(
                    select(containers.c.parent).where(
                        containers.c.service == record.service,
                        containers.c.type == record.type,
                        containers.c.id == record.id,
                    )
                ).first()
                if found is None:
                    conn.execute(
                        insert(containers).values(
                            service=record.service,
                            type=record.type,
                            id=record.id,
                            parent=record.parent,
                        )
                    )
                    counts["containers"] += 1
                elif found.parent != record.parent:
                    raise IAMConflictError(
                        f"{record.service}:{record.type}/{record.id} is in {found.parent}"
                    )
            for row in conn.execute(select(policies)).all():
                before = json.loads(row.document)
                document = dict(rewriter.document(before))
                owner = rewriter.owner(row.owner_scope)
                if document == before and owner == row.owner_scope:
                    continue
                checked = PolicyDocument.from_dict(document).to_json()
                conn.execute(
                    update(policies)
                    .where(policies.c.id == row.id)
                    .values(
                        document=checked,
                        owner_scope=owner,
                        revision=policies.c.revision + 1,
                        updated_at=_now(),
                    )
                )
                counts["policies"] += 1
            for row in conn.execute(
                select(principals.c.id, principals.c.owner_scope).where(
                    principals.c.kind == "group"
                )
            ).all():
                owner = rewriter.owner(row.owner_scope)
                if owner != row.owner_scope:
                    conn.execute(
                        update(principals)
                        .where(principals.c.id == row.id)
                        .values(owner_scope=owner)
                    )
                    counts["groups"] += 1
            for table, name in (
                (attachments, "attachments"),
                (pending_grants, "pending_grants"),
            ):
                for row in conn.execute(select(table.c.id, table.c.scope)).all():
                    scope = rewriter.scope(row.scope or None) or ""
                    if scope != (row.scope or ""):
                        conn.execute(
                            update(table)
                            .where(table.c.id == row.id)
                            .values(scope=scope)
                        )
                        counts[name] += 1
            for row in conn.execute(select(placements)).all():
                if row.container is not None:
                    continue  # a placement of today
                container = rewriter.placement(
                    LegacyPlacement(
                        row.service, row.id_key, f"abi:{row.org}:{row.workspace}"
                    )
                )
                if as_container(container) == UNRESOLVED:
                    # No container to name (a workspace that is gone): kept in the
                    # old form, read as UNRESOLVED, tried again by a later rewrite.
                    continue
                conn.execute(
                    update(placements)
                    .where(
                        placements.c.service == row.service,
                        placements.c.id_key == row.id_key,
                    )
                    .values(container=container, org="-", workspace="-")
                )
                counts["placements"] += 1
            for row in conn.execute(select(key_narrowing)).all():
                narrowing = json.loads(row.scope) if row.scope is not None else None
                rewritten = (
                    [dict(s) for s in rewriter.statements(narrowing)]
                    if narrowing is not None
                    else None
                )
                resource = rewriter.resource(row.resource)
                if rewritten == narrowing and resource == row.resource:
                    continue
                conn.execute(
                    update(key_narrowing)
                    .where(key_narrowing.c.key_id == row.key_id)
                    .values(
                        scope=json.dumps(rewritten) if rewritten is not None else None,
                        resource=resource,
                    )
                )
                counts["keys"] += 1
            for row in conn.execute(select(manifests)).all():
                before = json.loads(row.document)
                document = _rewrite_manifest(before, rewriter)
                if document == before:
                    continue
                conn.execute(
                    update(manifests)
                    .where(
                        manifests.c.principal_id == row.principal_id,
                        manifests.c.sha256 == row.sha256,
                    )
                    .values(document=json.dumps(document, sort_keys=True))
                )
                counts["manifests"] += 1
        return counts

    # -- what an older version left ------------------------------------------------

    def legacy_scope_sets(self) -> list[LegacyScopeSet]:
        table = legacy_scope_sets
        with self._read() as conn:
            if not inspect(conn).has_table(table.name, schema=self._schema):
                return []
            return [
                LegacyScopeSet(
                    row.org,
                    row.workspace,
                    _list_json(row.modules),
                    _list_json(row.features),
                )
                for row in conn.execute(
                    select(table).order_by(table.c.org, table.c.workspace)
                )
            ]

    def drop_legacy_scope_sets(self) -> bool:
        table = legacy_scope_sets
        with self._change() as conn:
            if not inspect(conn).has_table(table.name, schema=self._schema):
                return False
            table.drop(conn)
            return True

    # -- catalogs -----------------------------------------------------------------

    def put_catalog(self, catalog: ActionCatalog) -> None:
        document = json.dumps(catalog.to_dict(stored=True), sort_keys=True)
        with self._read() as conn:
            current = conn.execute(
                select(catalogs.c.document).where(catalogs.c.service == catalog.service)
            ).scalar()
        if current == document:
            return
        with self._change() as conn:
            conn.execute(delete(catalogs).where(catalogs.c.service == catalog.service))
            conn.execute(
                insert(catalogs).values(
                    service=catalog.service, version=catalog.version, document=document
                )
            )

    def list_catalogs(self) -> list[ActionCatalog]:
        with self._read() as conn:
            return [
                ActionCatalog.from_dict(json.loads(document), stored=True)
                for document in conn.scalars(
                    select(catalogs.c.document).order_by(catalogs.c.service)
                )
            ]

    # -- keys -------------------------------------------------------------------------

    def create_key(self, record: KeyRecord) -> KeyRecord:
        with self._change() as conn:
            if (
                conn.execute(
                    select(principals.c.id).where(
                        principals.c.id == record.principal_id
                    )
                ).first()
                is None
            ):
                raise IAMNotFoundError(f"Principal {record.principal_id} not found")
            if conn.execute(
                select(keys.c.key_id).where(keys.c.key_id == record.key_id)
            ).first():
                raise IAMConflictError(f"Key {record.key_id} exists")
            conn.execute(
                insert(keys).values(
                    key_id=record.key_id,
                    principal_id=record.principal_id,
                    kind=record.kind,
                    secret_hash=record.secret_hash,
                    description=record.description,
                    created_at=record.created_at or _now(),
                    expires_at=record.expires_at,
                    last_used_at=None,
                    revoked_at=record.revoked_at,
                )
            )
            if (record.audience, record.resource, record.scope) != (None, None, None):
                conn.execute(
                    insert(key_narrowing).values(
                        key_id=record.key_id,
                        audience=record.audience,
                        resource=record.resource,
                        scope=json.dumps(list(record.scope), sort_keys=True)
                        if record.scope is not None
                        else None,
                    )
                )
        return self.get_key(record.key_id)

    @staticmethod
    def _keys_query() -> Any:
        return select(
            keys,
            key_narrowing.c.audience,
            key_narrowing.c.resource,
            key_narrowing.c.scope,
        ).select_from(
            keys.outerjoin(key_narrowing, key_narrowing.c.key_id == keys.c.key_id)
        )

    def get_key(self, key_id: str) -> KeyRecord:
        with self._read() as conn:
            row = conn.execute(
                self._keys_query().where(keys.c.key_id == key_id)
            ).first()
        if row is None:
            raise IAMNotFoundError(f"Key {key_id} not found")
        return _key(row)

    def list_keys(self, principal_id: str | None = None) -> list[KeyRecord]:
        query = self._keys_query().order_by(keys.c.created_at, keys.c.key_id)
        if principal_id is not None:
            query = query.where(keys.c.principal_id == principal_id)
        with self._read() as conn:
            return [_key(row) for row in conn.execute(query)]

    def revoke_key(self, key_id: str, at: datetime) -> KeyRecord:
        current = self.get_key(key_id)
        if current.revoked_at is None:
            with self._change() as conn:
                conn.execute(
                    update(keys)
                    .where(keys.c.key_id == key_id, keys.c.revoked_at.is_(None))
                    .values(revoked_at=at)
                )
        return self.get_key(key_id)

    def touch_key(self, key_id: str, at: datetime) -> None:
        with self._write() as conn:
            conn.execute(
                update(keys).where(keys.c.key_id == key_id).values(last_used_at=at)
            )

    def delete_keys(self, key_ids: Sequence[str]) -> int:
        ids = list(key_ids)
        if not ids:
            return 0
        with self._write() as conn:
            conn.execute(delete(key_narrowing).where(key_narrowing.c.key_id.in_(ids)))
            result = conn.execute(delete(keys).where(keys.c.key_id.in_(ids)))
        return int(result.rowcount or 0)

    # -- token floors -----------------------------------------------------------------

    def set_token_floor(self, principal_id: str, not_before: datetime) -> None:
        with self._change() as conn:
            if (
                conn.execute(
                    select(principals.c.id).where(principals.c.id == principal_id)
                ).first()
                is None
            ):
                raise IAMNotFoundError(f"Principal {principal_id} not found")
            current = conn.execute(
                select(token_floors.c.not_before).where(
                    token_floors.c.principal_id == principal_id
                )
            ).first()
            if current is None:
                conn.execute(
                    insert(token_floors).values(
                        principal_id=principal_id, not_before=not_before
                    )
                )
            elif (held := _aware(current.not_before)) is not None and held < not_before:
                conn.execute(
                    update(token_floors)
                    .where(token_floors.c.principal_id == principal_id)
                    .values(not_before=not_before)
                )

    def token_floors(self) -> dict[str, datetime]:
        with self._read() as conn:
            return {
                row.principal_id: _aware(row.not_before)  # type: ignore[misc]
                for row in conn.execute(select(token_floors))
            }

    # -- manifests --------------------------------------------------------------------

    def put_manifest(self, record: ManifestRecord) -> ManifestRecord:
        key = (manifests.c.principal_id == record.principal_id) & (
            manifests.c.sha256 == record.sha256
        )
        with self._change() as conn:
            if (
                conn.execute(
                    select(principals.c.id).where(
                        principals.c.id == record.principal_id
                    )
                ).first()
                is None
            ):
                raise IAMNotFoundError(f"Principal {record.principal_id} not found")
            conn.execute(delete(manifests).where(key))
            conn.execute(
                insert(manifests).values(
                    principal_id=record.principal_id,
                    sha256=record.sha256,
                    module_id=record.module_id,
                    project=record.project,
                    document=json.dumps(record.document, sort_keys=True),
                    status=record.status,
                    submitted_at=record.submitted_at or _now(),
                    decided_at=record.decided_at,
                    decided_by=record.decided_by,
                    reason=record.reason,
                )
            )
        return self.get_manifest(record.principal_id, record.sha256)

    def get_manifest(self, principal_id: str, sha256: str) -> ManifestRecord:
        with self._read() as conn:
            row = conn.execute(
                select(manifests).where(
                    manifests.c.principal_id == principal_id,
                    manifests.c.sha256 == sha256,
                )
            ).first()
        if row is None:
            raise IAMNotFoundError(f"Manifest {sha256} of {principal_id} not found")
        return _manifest(row)

    def list_manifests(
        self, principal_id: str | None = None, status: ManifestStatus | None = None
    ) -> list[ManifestRecord]:
        query = select(manifests).order_by(
            manifests.c.submitted_at, manifests.c.principal_id, manifests.c.sha256
        )
        if principal_id is not None:
            query = query.where(manifests.c.principal_id == principal_id)
        if status is not None:
            query = query.where(manifests.c.status == status)
        with self._read() as conn:
            return [_manifest(row) for row in conn.execute(query)]

    # -- signing keys -------------------------------------------------------------------

    def add_signing_key(self, record: SigningKeyRecord) -> None:
        with self._change() as conn:
            if conn.execute(
                select(signing_keys.c.kid).where(signing_keys.c.kid == record.kid)
            ).first():
                raise IAMConflictError(f"Signing key {record.kid} exists")
            conn.execute(
                insert(signing_keys).values(
                    kid=record.kid,
                    public_jwk=json.dumps(record.public_jwk, sort_keys=True),
                    created_at=record.created_at,
                    activates_at=record.activates_at,
                    retires_at=record.retires_at,
                )
            )

    def list_signing_keys(self) -> list[SigningKeyRecord]:
        with self._read() as conn:
            return [
                _signing_key(row)
                for row in conn.execute(
                    select(signing_keys).order_by(
                        signing_keys.c.created_at, signing_keys.c.kid
                    )
                )
            ]

    def retire_signing_key(self, kid: str, retires_at: datetime) -> None:
        with self._write() as conn:
            changed = conn.execute(
                update(signing_keys)
                .where(signing_keys.c.kid == kid, signing_keys.c.retires_at.is_(None))
                .values(retires_at=retires_at)
            ).rowcount
            if changed:
                conn.execute(update(state).values(revision=state.c.revision + 1))

    # -- store ----------------------------------------------------------------------

    def revision(self) -> int:
        with self._read() as conn:
            return int(conn.execute(select(func.max(state.c.revision))).scalar() or 0)

    def install_id(self) -> str:
        with self._read() as conn:
            return str(conn.execute(select(state.c.install_id)).scalar())

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self._engine.dispose()

    def _delete(self, statement: Any) -> bool:
        """Run a delete; the revision goes up only when a row went."""
        with self._write() as conn:
            deleted = conn.execute(statement).rowcount > 0
            if deleted:
                conn.execute(update(state).values(revision=state.c.revision + 1))
        return deleted


def _page(rows: list[Any], limit: int) -> Page:
    if len(rows) > limit:
        return Page(rows[:limit], rows[limit - 1].id)
    return Page(rows, None)
