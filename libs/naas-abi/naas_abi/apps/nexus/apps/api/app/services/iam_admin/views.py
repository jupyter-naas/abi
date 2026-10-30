"""IAM's records as the JSON the admin pages read.

Never a key's secret: a key is shown by its id and prefix, and its value only in
the answer that made it (``created_key``).
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.iam.names import org_of
from naas_abi_core.services.iam.catalog import ActionCatalog
from naas_abi_core.services.iam.IAMPorts import (
    Attachment,
    CreatedKey,
    Explanation,
    GrantableAction,
    GrantableCatalog,
    KeyRecord,
    ManifestRecord,
    Policy,
    PrincipalRecord,
)
from naas_abi_core.services.iam.keys import PREFIXES
from naas_abi_core.services.iam.listing import ResourcePage
from naas_abi_core.services.iam.modules import split_manifest
from naas_abi_core.services.iam.policy import POLICY_VARIABLES, Statement
from naas_abi_core.services.iam.publishers import Publisher

# The service accounts the engine itself holds (``roles.SERVICE_ACCOUNTS``) and the
# jobs of its modules.
_BUILTIN_PREFIXES = ("job/",)


def iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return (value if value.tzinfo else value.replace(tzinfo=UTC)).isoformat()


def principal_view(record: PrincipalRecord) -> dict[str, Any]:
    return {
        "id": record.id,
        "kind": record.kind,
        "status": record.status,
        "name": record.name,
        "email": record.email,
        "display_name": record.display_name,
        "provider": record.provider,
        # The organization its owner is or sits in (a group's), from its owner.
        "org": org_of(record.owner_scope) if record.owner_scope else None,
        "owner_id": record.owner_id,
        "owner_scope": record.owner_scope,
        "created_at": iso(record.created_at),
    }


def account_kind(record: PrincipalRecord, builtin_names: frozenset[str]) -> str:
    name = record.name or ""
    if name.startswith("module/"):
        return "module"
    if name in builtin_names or name.startswith(_BUILTIN_PREFIXES):
        return "builtin"
    return "custom"


def statement_view(statement: Statement) -> dict[str, Any]:
    return statement.to_dict()


def policy_view(policy: Policy) -> dict[str, Any]:
    return {
        "id": policy.id,
        "name": policy.name,
        "description": policy.description,
        "managed": policy.managed,
        "revision": policy.revision,
        "owner_scope": policy.owner_scope,
        "parent_id": policy.parent_id,
        "document": policy.document.to_dict(),
        "created_at": iso(policy.created_at),
        "updated_at": iso(policy.updated_at),
    }


def policy_ref(policy_id: str | None, policy: Policy | None) -> dict[str, Any] | None:
    """A policy named by its id: its name and owner when they can be read."""
    if policy_id is None:
        return None
    return {
        "id": policy_id,
        "name": policy.name if policy is not None else None,
        "owner_scope": policy.owner_scope if policy is not None else None,
        "managed": policy.managed if policy is not None else None,
    }


def attachment_view(
    attachment: Attachment,
    policy_name: str | None,
    principal: PrincipalRecord | None,
) -> dict[str, Any]:
    return {
        "id": attachment.id,
        "policy_id": attachment.policy_id,
        "policy_name": policy_name,
        "principal_id": attachment.principal_id,
        "principal": principal_view(principal) if principal is not None else None,
        "scope": attachment.scope,
        "created_at": iso(attachment.created_at),
    }


def key_view(record: KeyRecord, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    status = "active"
    if record.revoked_at is not None:
        status = "revoked"
    elif record.expires_at is not None and record.expires_at <= now:
        status = "expired"
    return {
        "id": record.key_id,
        "principal_id": record.principal_id,
        "kind": record.kind,
        "description": record.description,
        "prefix": f"{PREFIXES[record.kind]}{record.key_id}",
        "created_at": iso(record.created_at),
        "expires_at": iso(record.expires_at),
        "last_used_at": iso(record.last_used_at),
        "revoked_at": iso(record.revoked_at),
        "status": status,
    }


def created_key(created: CreatedKey) -> dict[str, Any]:
    """The one answer that carries a key's value."""
    return {"key": key_view(created.record), "value": created.value}


def manifest_view(record: ManifestRecord, account_name: str | None) -> dict[str, Any]:
    """A manifest version: its policy ``document`` (what an admin may narrow) and
    the ``catalog`` it declares (approved as submitted, or None)."""
    policy, catalog = split_manifest(record.document)
    return {
        "principal_id": record.principal_id,
        "account_name": account_name,
        "sha256": record.sha256,
        "module_id": record.module_id,
        "project": record.project,
        "status": record.status,
        "document": dict(policy) if isinstance(policy, Mapping) else policy.to_dict(),
        "catalog": dict(catalog) if catalog is not None else None,
        "submitted_at": iso(record.submitted_at),
        "decided_at": iso(record.decided_at),
        "decided_by": record.decided_by,
        "reason": record.reason,
    }


def catalog_view(
    catalog: ActionCatalog, granted: Mapping[str, GrantableAction] | None = None
) -> dict[str, Any]:
    """A catalog as the editor reads it; with ``granted``, only those actions and
    the resource types they name."""
    data = catalog.to_dict()
    data["publisher"] = catalog.publisher
    data["actions"] = [
        {**action, "qualified": catalog.qualified(action["name"])}
        for action in data["actions"]
        if granted is None or catalog.qualified(action["name"]) in granted
    ]
    if granted is not None:
        named = {t for action in data["actions"] for t in action["resource_types"]}
        data["resource_types"] = [t for t in data["resource_types"] if t["name"] in named]
    return data


def catalogs_view(
    catalogs: list[ActionCatalog], granted: list[GrantableCatalog] | None = None
) -> dict[str, Any]:
    """The catalogs; with ``granted`` (what the caller may grant), only what is in
    it: a catalog with nothing granted is left out."""
    held = (
        {a.action: a for found in granted for a in found.actions} if granted is not None else None
    )
    views = [catalog_view(c, held) for c in catalogs]
    return {
        "catalogs": [v for v in views if held is None or v["actions"]],
        "variables": sorted(POLICY_VARIABLES),
    }


def publisher_view(publisher: Publisher) -> dict[str, Any]:
    return {
        "id": publisher.id,
        "kind": publisher.kind,
        "types": [
            {
                "service": t.service,
                "type": t.type.name,
                "description": t.type.description,
                "id": t.type.id,
                "placement": t.type.placement,
                "container": t.type.container,
                "listed": t.listed,
                "module": t.module or None,
                "actions": [
                    {
                        "action": f"{t.service}:{a.spec.name}",
                        "name": a.spec.name,
                        "level": a.spec.level,
                        "description": a.spec.description,
                        "resources": list(a.grantable.resources),
                        "excluded": list(a.grantable.excluded),
                    }
                    for a in t.actions
                ],
            }
            for t in publisher.types
        ],
    }


def resource_page_view(page: ResourcePage) -> dict[str, Any]:
    return {
        "items": [
            {
                "name": item.name,
                "id": item.id,
                "label": item.label or item.id,
                "description": item.description,
            }
            for item in page.items
        ],
        "next_cursor": page.next_cursor,
        "listed": page.listed,
    }


def grantable_view(
    catalog: GrantableCatalog, declared: ActionCatalog | None = None
) -> dict[str, Any]:
    """What the caller may grant of one catalog; with ``declared`` (the registered
    catalog), its publisher and the types each action acts on."""

    def types(action: str) -> list[str]:
        spec = declared.action(action.partition(":")[2]) if declared is not None else None
        return list(spec.resource_types) if spec is not None else []

    return {
        "service": catalog.service,
        "publisher": declared.publisher if declared is not None else None,
        "actions": [
            {
                "action": a.action,
                "resource_types": types(a.action),
                "resources": list(a.resources),
                "excluded": list(a.excluded),
            }
            for a in catalog.actions
        ],
    }


def simulation_view(
    explanation: Explanation,
    principal: PrincipalRecord,
    policy: Policy | None,
) -> dict[str, Any]:
    deciding = explanation.statement
    statement = None
    if deciding is not None:
        written = None
        if policy is not None and 0 <= deciding.statement_index < len(policy.document.statements):
            written = statement_view(policy.document.statements[deciding.statement_index])
        statement = {
            "side": deciding.side,
            "principal_id": deciding.principal_id,
            "effect": deciding.effect,
            "policy_id": deciding.policy_id,
            "policy_name": policy.name if policy is not None else None,
            "statement_index": deciding.statement_index,
            "sid": deciding.sid,
            "attachment_id": deciding.attachment_id,
            "scope": deciding.scope,
            "via_group": deciding.via_group,
            "statement": written,
            # The chain: the parents that allowed it too, or the sub-policies a
            # parent's statement was reached through.
            "bounded_by": [
                {"policy_id": b.policy_id, "statement_index": b.statement_index, "sid": b.sid}
                for b in deciding.bounded_by
            ],
            "through": list(deciding.through),
        }
    return {
        "allowed": explanation.allowed,
        "reason": explanation.reason,
        "action": explanation.action,
        "resource": explanation.resource,
        "principal": principal_view(principal),
        "statement": statement,
    }
