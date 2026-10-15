"""In-memory ``IAMStore``, for tests: same contract, nothing persists."""

from __future__ import annotations

import threading
import uuid
from collections.abc import Iterable, Sequence
from dataclasses import replace
from datetime import UTC, datetime

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


def _now() -> datetime:
    return datetime.now(UTC)


class IAMStoreMemory(IAMStore):
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._principals: dict[str, PrincipalRecord] = {}
        self._members: set[tuple[str, str]] = set()
        self._mappings: set[GroupMapping] = set()
        self._policies: dict[str, Policy] = {}
        self._attachments: dict[str, Attachment] = {}
        self._placements: dict[tuple[str, str], Placement] = {}
        self._scopes: dict[tuple[str, str], ScopeRecord] = {}
        self._catalogs: dict[str, ActionCatalog] = {}
        self._keys: dict[str, KeyRecord] = {}
        self._manifests: dict[tuple[str, str], ManifestRecord] = {}
        self._signing_keys: dict[str, SigningKeyRecord] = {}
        self._revision = 0
        self._install_id: str | None = None
        self._closed = False

    def _write(self) -> None:
        if self._closed:
            raise RuntimeError("IAM store is closed")
        self._revision += 1

    # -- principals -------------------------------------------------------------

    def create_principal(self, record: PrincipalRecord) -> PrincipalRecord:
        with self._lock:
            if record.id in self._principals:
                raise IAMConflictError(f"Principal {record.id} exists")
            if record.kind == "user" and self._find_user(record.issuer, record.subject):
                raise IAMConflictError("A user with this issuer and subject exists")
            if record.kind == "service_account" and self._find_sa(record.name):
                raise IAMConflictError(f"Service account {record.name!r} exists")
            now = _now()
            stored = replace(record, created_at=now, updated_at=now)
            self._write()
            self._principals[record.id] = stored
            return stored

    def get_principal(self, principal_id: str) -> PrincipalRecord:
        with self._lock:
            try:
                return self._principals[principal_id]
            except KeyError:
                raise IAMNotFoundError(f"Principal {principal_id} not found") from None

    def _find_user(self, issuer, subject) -> PrincipalRecord | None:
        return next(
            (
                p
                for p in self._principals.values()
                if p.kind == "user" and p.issuer == issuer and p.subject == subject
            ),
            None,
        )

    def _find_sa(self, name) -> PrincipalRecord | None:
        return next(
            (
                p
                for p in self._principals.values()
                if p.kind == "service_account" and p.name == name
            ),
            None,
        )

    def find_user(self, issuer: str, subject: str) -> PrincipalRecord | None:
        with self._lock:
            return self._find_user(issuer, subject)

    def find_service_account(self, name: str) -> PrincipalRecord | None:
        with self._lock:
            return self._find_sa(name)

    def list_principals(
        self,
        kind: PrincipalKind | None = None,
        *,
        limit: int = 100,
        after: str | None = None,
    ) -> Page:
        with self._lock:
            ids = sorted(
                p.id
                for p in self._principals.values()
                if (kind is None or p.kind == kind) and (after is None or p.id > after)
            )
            return _page([self._principals[i] for i in ids], limit)

    def update_principal(self, record: PrincipalRecord) -> PrincipalRecord:
        with self._lock:
            current = self.get_principal(record.id)
            if record.kind == "service_account" and record.name != current.name:
                other = self._find_sa(record.name)
                if other is not None and other.id != record.id:
                    raise IAMConflictError(f"Service account {record.name!r} exists")
            stored = replace(
                record,
                kind=current.kind,
                issuer=current.issuer,
                subject=current.subject,
                created_at=current.created_at,
                updated_at=_now(),
            )
            self._write()
            self._principals[record.id] = stored
            return stored

    # -- groups -------------------------------------------------------------------

    def add_group_member(self, group_id: str, member_id: str) -> None:
        with self._lock:
            self._require(group_id, member_id)
            if (group_id, member_id) not in self._members:
                self._write()
                self._members.add((group_id, member_id))

    def remove_group_member(self, group_id: str, member_id: str) -> bool:
        with self._lock:
            if (group_id, member_id) not in self._members:
                return False
            self._write()
            self._members.discard((group_id, member_id))
            return True

    def list_group_members(self, group_id: str) -> list[str]:
        with self._lock:
            return sorted(m for g, m in self._members if g == group_id)

    def groups_of(self, member_id: str) -> list[str]:
        with self._lock:
            return sorted(g for g, m in self._members if m == member_id)

    def map_idp_group(self, mapping: GroupMapping) -> None:
        with self._lock:
            self._require(mapping.group_id)
            if mapping not in self._mappings:
                self._write()
                self._mappings.add(mapping)

    def unmap_idp_group(self, mapping: GroupMapping) -> bool:
        with self._lock:
            if mapping not in self._mappings:
                return False
            self._write()
            self._mappings.discard(mapping)
            return True

    def list_idp_group_mappings(
        self, group_id: str | None = None
    ) -> list[GroupMapping]:
        with self._lock:
            return sorted(
                (
                    m
                    for m in self._mappings
                    if group_id is None or m.group_id == group_id
                ),
                key=lambda m: (m.provider, m.claim_value, m.group_id),
            )

    def resolve_idp_groups(
        self, provider: str, claim_values: Iterable[str]
    ) -> list[str]:
        values = set(claim_values)
        with self._lock:
            return sorted(
                {
                    m.group_id
                    for m in self._mappings
                    if m.provider == provider and m.claim_value in values
                }
            )

    def _require(self, *principal_ids: str) -> None:
        for principal_id in principal_ids:
            if principal_id not in self._principals:
                raise IAMNotFoundError(f"Principal {principal_id} not found")

    # -- policies -----------------------------------------------------------------

    def create_policy(self, policy: Policy) -> Policy:
        with self._lock:
            if policy.id in self._policies:
                raise IAMConflictError(f"Policy {policy.id} exists")
            now = _now()
            stored = replace(policy, revision=1, created_at=now, updated_at=now)
            self._write()
            self._policies[policy.id] = stored
            return stored

    def get_policy(self, policy_id: str) -> Policy:
        with self._lock:
            try:
                return self._policies[policy_id]
            except KeyError:
                raise IAMNotFoundError(f"Policy {policy_id} not found") from None

    def list_policies(self, *, limit: int = 100, after: str | None = None) -> Page:
        with self._lock:
            ids = sorted(i for i in self._policies if after is None or i > after)
            return _page([self._policies[i] for i in ids], limit)

    def update_policy(self, policy: Policy, expected_revision: int) -> Policy:
        with self._lock:
            current = self.get_policy(policy.id)
            if current.revision != expected_revision:
                raise RevisionConflictError(
                    f"Policy {policy.id} is at revision {current.revision}, "
                    f"not {expected_revision}"
                )
            stored = replace(
                current,
                name=policy.name,
                description=policy.description,
                document=policy.document,
                revision=current.revision + 1,
                updated_at=_now(),
            )
            self._write()
            self._policies[policy.id] = stored
            return stored

    def put_managed_policy(self, policy: Policy) -> Policy:
        with self._lock:
            current = self._policies.get(policy.id)
            if current is None:
                now = _now()
                stored = replace(
                    policy, managed=True, revision=1, created_at=now, updated_at=now
                )
            elif (current.name, current.description, current.document) == (
                policy.name,
                policy.description,
                policy.document,
            ):
                return current
            else:
                stored = replace(
                    current,
                    name=policy.name,
                    description=policy.description,
                    document=policy.document,
                    managed=True,
                    revision=current.revision + 1,
                    updated_at=_now(),
                )
            self._write()
            self._policies[policy.id] = stored
            return stored

    def delete_policy(self, policy_id: str) -> None:
        with self._lock:
            self.get_policy(policy_id)
            if any(a.policy_id == policy_id for a in self._attachments.values()):
                raise IAMConflictError(f"Policy {policy_id} is attached")
            self._write()
            del self._policies[policy_id]

    # -- attachments --------------------------------------------------------------

    def attach(self, attachment: Attachment) -> Attachment:
        with self._lock:
            self.get_policy(attachment.policy_id)
            self._require(attachment.principal_id)
            for existing in self._attachments.values():
                if (existing.policy_id, existing.principal_id, existing.scope) == (
                    attachment.policy_id,
                    attachment.principal_id,
                    attachment.scope,
                ):
                    raise IAMConflictError("This attachment exists")
            if attachment.id in self._attachments:
                raise IAMConflictError(f"Attachment {attachment.id} exists")
            stored = replace(attachment, created_at=_now())
            self._write()
            self._attachments[attachment.id] = stored
            return stored

    def detach(self, policy_id: str, principal_id: str, scope: str | None) -> bool:
        with self._lock:
            for key, existing in self._attachments.items():
                if (existing.policy_id, existing.principal_id, existing.scope) == (
                    policy_id,
                    principal_id,
                    scope,
                ):
                    self._write()
                    del self._attachments[key]
                    return True
            return False

    def list_attachments(
        self, *, principal_id: str | None = None, policy_id: str | None = None
    ) -> list[Attachment]:
        with self._lock:
            return sorted(
                (
                    a
                    for a in self._attachments.values()
                    if (principal_id is None or a.principal_id == principal_id)
                    and (policy_id is None or a.policy_id == policy_id)
                ),
                key=lambda a: a.id,
            )

    def attachments_for(self, principal_ids: Sequence[str]) -> list[Attachment]:
        wanted = set(principal_ids)
        with self._lock:
            return sorted(
                (a for a in self._attachments.values() if a.principal_id in wanted),
                key=lambda a: a.id,
            )

    # -- placements and scopes ----------------------------------------------------

    def put_placement(self, placement: Placement) -> None:
        with self._lock:
            if self._placements.get((placement.service, placement.id_key)) == placement:
                return
            self._write()
            self._placements[(placement.service, placement.id_key)] = placement

    def delete_placement(self, service: str, id_key: str) -> bool:
        with self._lock:
            if (service, id_key) not in self._placements:
                return False
            self._write()
            del self._placements[(service, id_key)]
            return True

    def list_placements(self, service: str | None = None) -> list[Placement]:
        with self._lock:
            return sorted(
                (p for p in self._placements.values() if service in (None, p.service)),
                key=lambda p: (p.service, p.id_key),
            )

    def put_scope(self, scope: ScopeRecord) -> None:
        with self._lock:
            if scope.workspace != "-":
                for existing in self._scopes.values():
                    if (
                        existing.workspace == scope.workspace
                        and existing.org != scope.org
                    ):
                        raise IAMConflictError(
                            f"Workspace {scope.workspace} is in org {existing.org}"
                        )
            key = (scope.org, scope.workspace)
            if key in self._scopes:
                return
            self._write()
            self._scopes[key] = scope

    def delete_scope(self, org: str, workspace: str = "-") -> bool:
        with self._lock:
            if (org, workspace) not in self._scopes:
                return False
            self._write()
            del self._scopes[(org, workspace)]
            return True

    def list_scopes(self, org: str | None = None) -> list[ScopeRecord]:
        with self._lock:
            return sorted(
                (s for s in self._scopes.values() if org in (None, s.org)),
                key=lambda s: (s.org, s.workspace),
            )

    # -- catalogs -----------------------------------------------------------------

    def put_catalog(self, catalog: ActionCatalog) -> None:
        with self._lock:
            if self._catalogs.get(catalog.service) == catalog:
                return
            self._write()
            self._catalogs[catalog.service] = catalog

    def list_catalogs(self) -> list[ActionCatalog]:
        with self._lock:
            return sorted(self._catalogs.values(), key=lambda c: c.service)

    # -- keys -------------------------------------------------------------------------

    def create_key(self, record: KeyRecord) -> KeyRecord:
        with self._lock:
            if record.principal_id not in self._principals:
                raise IAMNotFoundError(f"Principal {record.principal_id} not found")
            if record.key_id in self._keys:
                raise IAMConflictError(f"Key {record.key_id} exists")
            stored = replace(
                record, created_at=record.created_at or _now(), last_used_at=None
            )
            self._write()
            self._keys[record.key_id] = stored
            return stored

    def get_key(self, key_id: str) -> KeyRecord:
        with self._lock:
            try:
                return self._keys[key_id]
            except KeyError:
                raise IAMNotFoundError(f"Key {key_id} not found") from None

    def list_keys(self, principal_id: str | None = None) -> list[KeyRecord]:
        with self._lock:
            return sorted(
                (
                    k
                    for k in self._keys.values()
                    if principal_id in (None, k.principal_id)
                ),
                key=lambda k: (k.created_at, k.key_id),
            )

    def revoke_key(self, key_id: str, at: datetime) -> KeyRecord:
        with self._lock:
            current = self.get_key(key_id)
            if current.revoked_at is None:
                self._write()
                current = self._keys[key_id] = replace(current, revoked_at=at)
            return current

    def touch_key(self, key_id: str, at: datetime) -> None:
        with self._lock:
            if key_id in self._keys:
                self._keys[key_id] = replace(self._keys[key_id], last_used_at=at)

    # -- manifests --------------------------------------------------------------------

    def put_manifest(self, record: ManifestRecord) -> ManifestRecord:
        with self._lock:
            if record.principal_id not in self._principals:
                raise IAMNotFoundError(f"Principal {record.principal_id} not found")
            stored = replace(record, submitted_at=record.submitted_at or _now())
            self._write()
            self._manifests[(record.principal_id, record.sha256)] = stored
            return stored

    def get_manifest(self, principal_id: str, sha256: str) -> ManifestRecord:
        with self._lock:
            try:
                return self._manifests[(principal_id, sha256)]
            except KeyError:
                raise IAMNotFoundError(
                    f"Manifest {sha256} of {principal_id} not found"
                ) from None

    def list_manifests(
        self, principal_id: str | None = None, status: ManifestStatus | None = None
    ) -> list[ManifestRecord]:
        with self._lock:
            return sorted(
                (
                    m
                    for m in self._manifests.values()
                    if principal_id in (None, m.principal_id)
                    and status in (None, m.status)
                ),
                key=lambda m: (m.submitted_at, m.principal_id, m.sha256),
            )

    # -- signing keys -------------------------------------------------------------------

    def add_signing_key(self, record: SigningKeyRecord) -> None:
        with self._lock:
            if record.kid in self._signing_keys:
                raise IAMConflictError(f"Signing key {record.kid} exists")
            self._write()
            self._signing_keys[record.kid] = record

    def list_signing_keys(self) -> list[SigningKeyRecord]:
        with self._lock:
            return sorted(
                self._signing_keys.values(), key=lambda k: (k.created_at, k.kid)
            )

    def retire_signing_key(self, kid: str, retires_at: datetime) -> None:
        with self._lock:
            current = self._signing_keys.get(kid)
            if current is not None and current.retires_at is None:
                self._write()
                self._signing_keys[kid] = replace(current, retires_at=retires_at)

    # -- store ----------------------------------------------------------------------

    def revision(self) -> int:
        with self._lock:
            return self._revision

    def install_id(self) -> str:
        with self._lock:
            if self._install_id is None:
                self._install_id = uuid.uuid4().hex
            return self._install_id

    def close(self) -> None:
        self._closed = True


def _page(items: list, limit: int) -> Page:
    if not 1 <= limit <= 1000:
        raise ValueError("limit must be between 1 and 1000")
    if len(items) > limit:
        return Page(items[:limit], items[limit - 1].id)
    return Page(items, None)
