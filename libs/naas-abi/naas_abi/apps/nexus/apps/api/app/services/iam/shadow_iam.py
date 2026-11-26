"""A copy of an IAM, in memory, to try a change on before making it.

The access migration (``access_model``) applies its whole plan to a copy first:
what every person may do afterwards is read from the copy, so its report of who
gains and who loses what is IAM's own decisions, not a guess, and a dry run (``abi
iam migrate-access --dry-run``) writes nothing anywhere. A plan the copy refuses
stops the migration before the real IAM is touched.

The copy is read through the service's own API as the engine (which may list
everything), so it works for an IAM in process and for one reached over NATS:
the catalogs, the containers, every principal (with its group markers), the
group memberships, every policy (managed ones included), every attachment, the
placements and the pending grants. Keys, tokens and manifests decide nothing a
person may do: they are not copied.

What is copied can be kept as JSON (``snapshot``, ``store_of``): the access move
keeps IAM as it was before it, and reads its report from that copy after the
start that moved, a restart in between included.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, fields
from datetime import datetime
from typing import Any

from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.services.iam.adapters.secondary.IAMStoreMemory import IAMStoreMemory
from naas_abi_core.services.iam.catalog import ActionCatalog
from naas_abi_core.services.iam.IAMPorts import (
    Attachment,
    ContainerRecord,
    IAMConflictError,
    PendingGrant,
    Placement,
    Policy,
    PrincipalRecord,
)
from naas_abi_core.services.iam.IAMService import IAMService
from naas_abi_core.services.iam.policy import PolicyDocument

PAGE = 500


def _pages(listing: Callable[..., Any], **kwargs: Any) -> list[Any]:
    found: list[Any] = []
    after: str | None = None
    while True:
        page = listing(limit=PAGE, after=after, **kwargs)
        found += list(page.items)
        after = page.next_after
        if not after:
            return found


def _parents_first(policies: list[Any]) -> list[Any]:
    """Each policy after its parent (a store refuses a sub-policy of none)."""
    by_id = {p.id: p for p in policies}
    done: list[Any] = []
    seen: set[str] = set()

    def visit(policy: Any, depth: int = 0) -> None:
        if policy.id in seen or depth > 16:
            return
        parent = by_id.get(policy.parent_id) if policy.parent_id else None
        if parent is not None:
            visit(parent, depth + 1)
        seen.add(policy.id)
        done.append(policy)

    for policy in policies:
        visit(policy)
    return done


def _containers_first(records: list[Any]) -> list[Any]:
    """Each container after the one it sits in."""
    by_name = {getattr(r, "name", None): r for r in records}
    done: list[Any] = []
    seen: set[int] = set()

    def visit(record: Any, depth: int = 0) -> None:
        if id(record) in seen or depth > 16:
            return
        parent = by_name.get(getattr(record, "parent", None))
        if parent is not None and parent is not record:
            visit(parent, depth + 1)
        seen.add(id(record))
        done.append(record)

    for record in records:
        visit(record)
    return done


def _record(record: Any) -> dict[str, Any]:
    """A flat record (its fields strings, flags, numbers and times) as JSON."""
    return {k: v.isoformat() if isinstance(v, datetime) else v for k, v in asdict(record).items()}


def _policy(policy: Policy) -> dict[str, Any]:
    found = {f.name: getattr(policy, f.name) for f in fields(Policy) if f.name != "document"}
    found = {k: v.isoformat() if isinstance(v, datetime) else v for k, v in found.items()}
    found["document"] = policy.document.to_dict()
    return found


def _read_record(cls: type, data: dict[str, Any]) -> Any:
    """``_record`` read back: a field holding a time is read as one."""
    times = {f.name for f in fields(cls) if "datetime" in str(f.type)}
    return cls(
        **{
            k: datetime.fromisoformat(v) if k in times and isinstance(v, str) else v
            for k, v in data.items()
        }
    )


def _read_policy(data: dict[str, Any]) -> Policy:
    document = PolicyDocument.from_dict(data["document"])
    return _read_record(Policy, {**data, "document": document})


def snapshot(iam: Any) -> dict[str, Any]:
    """What ``iam`` decides with, read as the engine, as JSON (``store_of`` makes a
    store of it again)."""
    with as_service_account("engine"):
        catalogs = list(iam.list_catalogs())
        containers = list(iam.list_containers())
        principals = _pages(iam.list_principals)
        policies = _pages(iam.list_policies)
        attachments = list(iam.list_attachments())
        placements = list(iam.list_placements())
        pending = list(iam.list_pending_grants())
        groups = [p for p in principals if p.kind == "group"]
        members = {g.id: list(iam.list_group_members(g.id)) for g in groups}
    return {
        "catalogs": [c.to_dict(stored=True) for c in catalogs],
        "containers": [_record(c) for c in containers],
        "principals": [_record(p) for p in principals],
        "members": members,
        "policies": [_policy(p) for p in policies],
        "attachments": [_record(a) for a in attachments],
        "placements": [_record(p) for p in placements],
        "pending": [_record(g) for g in pending],
    }


def store_of(kept: dict[str, Any]) -> IAMStoreMemory:
    """A memory store holding what ``snapshot`` read."""
    store = IAMStoreMemory()
    catalogs = [ActionCatalog.from_dict(c, stored=True) for c in kept["catalogs"]]
    containers = [_read_record(ContainerRecord, c) for c in kept["containers"]]
    principals = [_read_record(PrincipalRecord, p) for p in kept["principals"]]
    members: dict[str, list[str]] = kept["members"]
    policies = [_read_policy(p) for p in kept["policies"]]
    attachments = [_read_record(Attachment, a) for a in kept["attachments"]]
    placements = [_read_record(Placement, p) for p in kept["placements"]]
    pending = [_read_record(PendingGrant, g) for g in kept["pending"]]
    for catalog in catalogs:
        store.put_catalog(catalog)
    for record in _containers_first(containers):
        store.put_container(record)
    for principal in principals:
        store.create_principal(principal)
    for group_id, member_ids in members.items():
        for member_id in member_ids:
            store.add_group_member(group_id, member_id)
    for policy in _parents_first(policies):
        if policy.managed:
            store.put_managed_policy(policy)
        else:
            store.create_policy(policy)
    for attachment in attachments:
        store.attach(attachment)
    for placement in placements:
        store.put_placement(placement)
    for grant in pending:
        try:
            store.add_pending_grant(grant)
        except IAMConflictError:
            continue
    return store


def copy_store(iam: Any) -> IAMStoreMemory:
    """A memory store holding what ``iam`` decides with, read as the engine."""
    return store_of(snapshot(iam))


def shadow_of(iam: Any) -> IAMService:
    """An IAM service over a copy of ``iam`` (``copy_store``): what it decides is
    what ``iam`` decides, until one of them changes."""
    return IAMService(copy_store(iam))


__all__ = ["copy_store", "shadow_of", "snapshot", "store_of"]
