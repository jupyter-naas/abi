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
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.services.iam.adapters.secondary.IAMStoreMemory import IAMStoreMemory
from naas_abi_core.services.iam.IAMPorts import IAMConflictError
from naas_abi_core.services.iam.IAMService import IAMService

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


def copy_store(iam: Any) -> IAMStoreMemory:
    """A memory store holding what ``iam`` decides with, read as the engine."""
    store = IAMStoreMemory()
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


def shadow_of(iam: Any) -> IAMService:
    """An IAM service over a copy of ``iam`` (``copy_store``): what it decides is
    what ``iam`` decides, until one of them changes."""
    return IAMService(copy_store(iam))


__all__ = ["copy_store", "shadow_of"]
