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
from datetime import UTC, datetime
from typing import Any

from naas_abi_core.services.iam.catalog import ActionCatalog
from naas_abi_core.services.iam.IAMPorts import (
    Attachment,
    GroupMapping,
    IAMConflictError,
    IAMNotFoundError,
    IAMStore,
    KeyRecord,
    ManifestRecord,
    ManifestStatus,
    Page,
    Placement,
    Policy,
    PrincipalKind,
    PrincipalRecord,
    RevisionConflictError,
    ScopeRecord,
    SigningKeyRecord,
)
from naas_abi_core.services.iam.policy import PolicyDocument
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    and_,
    delete,
    func,
    insert,
    select,
    update,
)
from sqlalchemy.engine import Connection, Engine, Row
from sqlalchemy.exc import IntegrityError

SCHEMA_VERSION = 1

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
    Column("org", Text),
    Column("owner_id", String(64)),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("issuer", "subject", name="iam_principals_user_identity"),
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

placements = Table(
    "iam_placements",
    metadata,
    Column("service", String(64), primary_key=True),
    Column("id_key", Text, primary_key=True),
    Column("org", String(64), nullable=False),
    Column("workspace", String(64), nullable=False),
)

scopes = Table(
    "iam_scopes",
    metadata,
    Column("org", String(64), primary_key=True),
    Column("workspace", String(64), primary_key=True),
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
    # sha256(secret), hex: the secret has 256 bits of entropy (RFC §8.1).
    Column("secret_hash", String(64), nullable=False),
    Column("description", Text, nullable=False, default=""),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("expires_at", DateTime(timezone=True)),
    Column("last_used_at", DateTime(timezone=True)),
    Column("revoked_at", DateTime(timezone=True)),
)

# What narrows a personal or grant key (RFC §9.3, §9.4). A table of its own, so
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

# Metadata only: the private keys live in the secret service (RFC §9.1).
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
        org=row.org,
        owner_id=row.owner_id,
        created_at=_aware(row.created_at),
        updated_at=_aware(row.updated_at),
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
        "org": record.org,
        "owner_id": record.owner_id,
    }


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
    )


def _attachment(row: Row) -> Attachment:
    return Attachment(
        id=row.id,
        policy_id=row.policy_id,
        principal_id=row.principal_id,
        scope=row.scope or None,
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


def _check_limit(limit: int) -> None:
    if not 1 <= limit <= 1000:
        raise ValueError("limit must be between 1 and 1000")


class IAMStoreSQL(IAMStore):
    """Subclasses pass an engine; ``_write_options`` selects the write transaction."""

    _write_options: dict[str, Any] = {}

    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self._closed = False
        metadata.create_all(engine)
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
        """A write that bumps the revision; unique violations become conflicts."""
        try:
            with self._write() as conn:
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
                select(principals).where(
                    principals.c.kind == "user",
                    principals.c.issuer == issuer,
                    principals.c.subject == subject,
                )
            ).first()
        return _principal(row) if row is not None else None

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
    ) -> Page:
        _check_limit(limit)
        query = select(principals).order_by(principals.c.id).limit(limit + 1)
        if kind is not None:
            query = query.where(principals.c.kind == kind)
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
            conn.execute(
                insert(policies).values(
                    id=policy.id,
                    name=policy.name,
                    description=policy.description,
                    document=policy.document.to_json(),
                    managed=policy.managed,
                    revision=1,
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

    def list_policies(self, *, limit: int = 100, after: str | None = None) -> Page:
        _check_limit(limit)
        query = select(policies).order_by(policies.c.id).limit(limit + 1)
        if after is not None:
            query = query.where(policies.c.id > after)
        with self._read() as conn:
            rows = [_policy(row) for row in conn.execute(query)]
        return _page(rows, limit)

    def update_policy(self, policy: Policy, expected_revision: int) -> Policy:
        with self._change() as conn:
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
            result = conn.execute(delete(policies).where(policies.c.id == policy_id))
            if result.rowcount == 0:
                raise IAMNotFoundError(f"Policy {policy_id} not found")

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

    # -- placements and scopes ----------------------------------------------------

    def put_placement(self, placement: Placement) -> None:
        key = (placements.c.service == placement.service) & (
            placements.c.id_key == placement.id_key
        )
        with self._read() as conn:
            row = conn.execute(select(placements).where(key)).first()
        if row is not None and (row.org, row.workspace) == (
            placement.org,
            placement.workspace,
        ):
            return
        with self._change() as conn:
            conn.execute(delete(placements).where(key))
            conn.execute(
                insert(placements).values(
                    service=placement.service,
                    id_key=placement.id_key,
                    org=placement.org,
                    workspace=placement.workspace,
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
                Placement(row.service, row.id_key, row.org, row.workspace)
                for row in conn.execute(query)
            ]

    def put_scope(self, scope: ScopeRecord) -> None:
        with self._read() as conn:
            if conn.execute(
                select(scopes.c.org).where(
                    scopes.c.org == scope.org, scopes.c.workspace == scope.workspace
                )
            ).first():
                return
        with self._change() as conn:
            if scope.workspace != "-":
                other = conn.execute(
                    select(scopes.c.org).where(
                        scopes.c.workspace == scope.workspace, scopes.c.org != scope.org
                    )
                ).scalar()
                if other is not None:
                    raise IAMConflictError(
                        f"Workspace {scope.workspace} is in org {other}"
                    )
            conn.execute(
                insert(scopes).values(org=scope.org, workspace=scope.workspace)
            )

    def delete_scope(self, org: str, workspace: str = "-") -> bool:
        return self._delete(
            delete(scopes).where(scopes.c.org == org, scopes.c.workspace == workspace)
        )

    def list_scopes(self, org: str | None = None) -> list[ScopeRecord]:
        query = select(scopes).order_by(scopes.c.org, scopes.c.workspace)
        if org is not None:
            query = query.where(scopes.c.org == org)
        with self._read() as conn:
            return [ScopeRecord(row.org, row.workspace) for row in conn.execute(query)]

    # -- catalogs -----------------------------------------------------------------

    def put_catalog(self, catalog: ActionCatalog) -> None:
        document = json.dumps(catalog.to_dict(), sort_keys=True)
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
                ActionCatalog.from_dict(json.loads(document))
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
