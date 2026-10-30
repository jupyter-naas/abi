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
from naas_abi_core.services.iam.names import UNRESOLVED, as_container, within
from naas_abi_core.services.iam.policy import PolicyDocument


def _now() -> datetime:
    return datetime.now(UTC)


class IAMStoreMemory(IAMStore):
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._principals: dict[str, PrincipalRecord] = {}
        self._links: dict[tuple[str, str], str] = {}
        self._members: set[tuple[str, str]] = set()
        self._mappings: set[GroupMapping] = set()
        self._policies: dict[str, Policy] = {}
        self._attachments: dict[str, Attachment] = {}
        self._pending: dict[str, PendingGrant] = {}
        self._placements: dict[tuple[str, str], Placement] = {}
        self._containers: dict[tuple[str, str, str], ContainerRecord] = {}
        # Tests: placements of the old form, by key, as ``abi:<org>:<ws>``.
        self._legacy_placements: dict[tuple[str, str], str] = {}
        self._legacy_sets: list[LegacyScopeSet] = []
        self._catalogs: dict[str, ActionCatalog] = {}
        self._keys: dict[str, KeyRecord] = {}
        self._token_floors: dict[str, datetime] = {}
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
            linked = self._links.get((issuer, subject))
            if linked is not None:
                return self._principals[linked]
            return self._find_user(issuer, subject)

    def linked_identities(self, principal_id: str) -> list[tuple[str, str]]:
        with self._lock:
            return sorted(k for k, v in self._links.items() if v == principal_id)

    def link_identity(self, issuer: str, subject: str, principal_id: str) -> None:
        with self._lock:
            record = self.get_principal(principal_id)
            if record.kind != "user":
                raise IAMConflictError(f"{principal_id} is not a user")
            held = self._links.get((issuer, subject))
            if held == principal_id:
                return
            if held is not None:
                raise IAMConflictError("This identity is linked to another user")
            self._write()
            self._links[(issuer, subject)] = principal_id

    def find_service_account(self, name: str) -> PrincipalRecord | None:
        with self._lock:
            return self._find_sa(name)

    def list_principals(
        self,
        kind: PrincipalKind | None = None,
        *,
        limit: int = 100,
        after: str | None = None,
        owner_scopes: Sequence[str] | None = None,
    ) -> Page:
        with self._lock:
            ids = sorted(
                p.id
                for p in self._principals.values()
                if (kind is None or p.kind == kind)
                and (after is None or p.id > after)
                and (owner_scopes is None or p.owner_scope in owner_scopes)
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
                owner_scope=current.owner_scope,
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
            self._require_parent(policy.parent_id)
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

    def list_policies(
        self,
        *,
        limit: int = 100,
        after: str | None = None,
        owner_scopes: Sequence[str] | None = None,
    ) -> Page:
        with self._lock:
            ids = sorted(
                i
                for i, p in self._policies.items()
                if (after is None or i > after)
                and (owner_scopes is None or p.owner_scope in owner_scopes)
            )
            return _page([self._policies[i] for i in ids], limit)

    def update_policy(self, policy: Policy, expected_revision: int) -> Policy:
        with self._lock:
            current = self.get_policy(policy.id)
            if current.revision != expected_revision:
                raise RevisionConflictError(
                    f"Policy {policy.id} is at revision {current.revision}, "
                    f"not {expected_revision}"
                )
            self._require_parent(policy.parent_id)
            stored = replace(
                current,
                name=policy.name,
                description=policy.description,
                document=policy.document,
                parent_id=policy.parent_id,
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
                    policy,
                    managed=True,
                    parent_id=None,
                    revision=1,
                    created_at=now,
                    updated_at=now,
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
            if any(g.policy_id == policy_id for g in self._pending.values()):
                raise IAMConflictError(f"Policy {policy_id} is granted to invitees")
            if any(p.parent_id == policy_id for p in self._policies.values()):
                raise IAMConflictError(f"Policy {policy_id} has sub-policies")
            self._write()
            del self._policies[policy_id]

    def list_sub_policies(self, policy_id: str) -> list[Policy]:
        with self._lock:
            return sorted(
                (p for p in self._policies.values() if p.parent_id == policy_id),
                key=lambda p: p.id,
            )

    def _require_parent(self, parent_id: str | None) -> None:
        if parent_id is not None and parent_id not in self._policies:
            raise IAMNotFoundError(f"Policy {parent_id} not found")

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

    def attachments_of(self, policy_ids: Sequence[str]) -> list[Attachment]:
        wanted = set(policy_ids)
        with self._lock:
            return sorted(
                (a for a in self._attachments.values() if a.policy_id in wanted),
                key=lambda a: a.id,
            )

    # -- pending grants -----------------------------------------------------------

    def add_pending_grant(self, grant: PendingGrant) -> PendingGrant:
        with self._lock:
            self.get_policy(grant.policy_id)
            key = (grant.provider, grant.email, grant.policy_id, grant.scope)
            if grant.id in self._pending or any(
                (g.provider, g.email, g.policy_id, g.scope) == key
                for g in self._pending.values()
            ):
                raise IAMConflictError("This pending grant exists")
            stored = replace(grant, created_at=_now())
            self._write()
            self._pending[grant.id] = stored
            return stored

    def list_pending_grants(
        self,
        *,
        provider: str | None = None,
        email: str | None = None,
        policy_id: str | None = None,
    ) -> list[PendingGrant]:
        with self._lock:
            return sorted(
                (
                    g
                    for g in self._pending.values()
                    if provider in (None, g.provider)
                    and email in (None, g.email)
                    and policy_id in (None, g.policy_id)
                ),
                key=lambda g: g.id,
            )

    def get_pending_grant(self, grant_id: str) -> PendingGrant | None:
        with self._lock:
            return self._pending.get(grant_id)

    def remove_pending_grant(self, grant_id: str) -> bool:
        with self._lock:
            if grant_id not in self._pending:
                return False
            self._write()
            del self._pending[grant_id]
            return True

    def claim_pending_grant(
        self, grant_id: str, principal_id: str, attachment_id: str
    ) -> Attachment | None:
        with self._lock:
            grant = self._pending.get(grant_id)
            if grant is None:
                return None
            self._require(principal_id)
            self._write()
            del self._pending[grant_id]
            for existing in self._attachments.values():
                if (existing.policy_id, existing.principal_id, existing.scope) == (
                    grant.policy_id,
                    principal_id,
                    grant.scope,
                ):
                    return existing
            stored = Attachment(
                attachment_id, grant.policy_id, principal_id, grant.scope, _now()
            )
            self._attachments[attachment_id] = stored
            return stored

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

    def put_container(self, record: ContainerRecord) -> None:
        with self._lock:
            key = (record.service, record.type, record.id)
            existing = self._containers.get(key)
            if existing is not None:
                if existing.parent != record.parent:
                    raise IAMConflictError(
                        f"{record.service}:{record.type}/{record.id} is in {existing.parent}"
                    )
                return
            self._write()
            self._containers[key] = record

    def get_container(self, service: str, type: str, id: str) -> ContainerRecord | None:
        with self._lock:
            return self._containers.get((service, type, id))

    def list_containers(self) -> list[ContainerRecord]:
        with self._lock:
            return [self._containers[k] for k in sorted(self._containers)]

    def delete_containers(self, records: Sequence[ContainerRecord]) -> int:
        with self._lock:
            if not records:
                return 0
            self._write()
            names = {record.name for record in records}
            for record in records:
                self._containers.pop((record.service, record.type, record.id), None)
            for key, placement in list(self._placements.items()):
                if any(within(placement.container, name) for name in names):
                    del self._placements[key]
            return len(records)

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
        with self._lock:
            self._write()
            for container in rewriter.containers():
                at = (container.service, container.type, container.id)
                found = self._containers.get(at)
                if found is None:
                    self._containers[at] = container
                    counts["containers"] += 1
                elif found.parent != container.parent:
                    raise IAMConflictError(f"{at} is in {found.parent}")
            for policy_id, policy in list(self._policies.items()):
                before = policy.document.to_dict()
                document = dict(rewriter.document(before))
                owner = rewriter.owner(policy.owner_scope)
                if document == before and owner == policy.owner_scope:
                    continue
                self._policies[policy_id] = replace(
                    policy,
                    document=PolicyDocument.from_dict(document),
                    owner_scope=owner,
                    revision=policy.revision + 1,
                    updated_at=_now(),
                )
                counts["policies"] += 1
            for principal_id, principal in list(self._principals.items()):
                if principal.kind != "group":
                    continue
                owner = rewriter.owner(principal.owner_scope)
                if owner != principal.owner_scope:
                    self._principals[principal_id] = replace(
                        principal, owner_scope=owner
                    )
                    counts["groups"] += 1
            for attachment_id, attachment in list(self._attachments.items()):
                scope = rewriter.scope(attachment.scope)
                if scope != attachment.scope:
                    self._attachments[attachment_id] = replace(attachment, scope=scope)
                    counts["attachments"] += 1
            for grant_id, grant in list(self._pending.items()):
                scope = rewriter.scope(grant.scope)
                if scope != grant.scope:
                    self._pending[grant_id] = replace(grant, scope=scope)
                    counts["pending_grants"] += 1
            for key, placement in list(self._placements.items()):
                if placement.container != UNRESOLVED:
                    continue
                legacy = self._legacy_placements.get(key, "abi:-:-")
                placed_in = rewriter.placement(
                    LegacyPlacement(placement.service, placement.id_key, legacy)
                )
                if as_container(placed_in) == UNRESOLVED:
                    continue  # no container to name: kept, read as UNRESOLVED
                self._placements[key] = replace(placement, container=placed_in)
                self._legacy_placements.pop(key, None)
                counts["placements"] += 1
            for key_id, key_record in list(self._keys.items()):
                narrowing = (
                    [dict(s) for s in key_record.scope]
                    if key_record.scope is not None
                    else None
                )
                rewritten = (
                    [dict(s) for s in rewriter.statements(narrowing)]
                    if narrowing is not None
                    else None
                )
                resource = rewriter.resource(key_record.resource)
                if rewritten == narrowing and resource == key_record.resource:
                    continue
                self._keys[key_id] = replace(
                    key_record,
                    scope=tuple(rewritten) if rewritten is not None else None,
                    resource=resource,
                )
                counts["keys"] += 1
            for manifest_key, manifest in list(self._manifests.items()):
                written = dict(manifest.document)
                declared = {k: v for k, v in written.items() if k != "catalog"}
                document = dict(rewriter.document(declared))
                if "catalog" in written:
                    document["catalog"] = written["catalog"]
                if document != written:
                    self._manifests[manifest_key] = replace(manifest, document=document)
                    counts["manifests"] += 1
        return counts

    def seed_legacy_placement(self, placement: Placement, scope: str) -> None:
        """Tests: a placement of the grammar before container paths."""
        with self._lock:
            key = (placement.service, placement.id_key)
            self._placements[key] = replace(placement, container=UNRESOLVED)
            self._legacy_placements[key] = scope

    # -- what an older version left ------------------------------------------------

    def legacy_scope_sets(self) -> list[LegacyScopeSet]:
        with self._lock:
            return sorted(self._legacy_sets, key=lambda s: (s.org, s.workspace))

    def drop_legacy_scope_sets(self) -> bool:
        with self._lock:
            if not self._legacy_sets:
                return False
            self._write()
            self._legacy_sets = []
            return True

    def seed_legacy_scope_sets(self, found: Iterable[LegacyScopeSet]) -> None:
        """Tests: the rows an older version's store would hold."""
        with self._lock:
            self._legacy_sets = list(found)

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

    def delete_keys(self, key_ids: Sequence[str]) -> int:
        with self._lock:
            found = [key_id for key_id in key_ids if key_id in self._keys]
            for key_id in found:
                del self._keys[key_id]
            return len(found)

    # -- token floors -----------------------------------------------------------------

    def set_token_floor(self, principal_id: str, not_before: datetime) -> None:
        with self._lock:
            if principal_id not in self._principals:
                raise IAMNotFoundError(f"Principal {principal_id} not found")
            current = self._token_floors.get(principal_id)
            if current is None or current < not_before:
                self._write()
                self._token_floors[principal_id] = not_before

    def token_floors(self) -> dict[str, datetime]:
        with self._lock:
            return dict(self._token_floors)

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
