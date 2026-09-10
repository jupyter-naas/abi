"""Turn committed identity changes into identity and access events.

One capture point for every path that changes a user, an organization, a
workspace, a membership or a workspace configuration: FastAPI endpoints,
invites, magic-link signup, config seeds at boot, admin agent tools. It listens
to SQLAlchemy ORM sessions rather than instrumenting each endpoint:

- ``after_flush``: the changes are read while attribute history still holds the
  old values, and turned into events (ids and IRIs only).
- ``after_commit``: the events are published to the EventService.
- ``after_rollback``: they are dropped, so nothing that did not happen is logged.

The actor (``created_by``) comes from the request-scoped identity ContextVars;
``EventService.publish()`` stamps ``actor_user_id`` / ``actor_workspace_id`` /
``triggered_via`` from the same ContextVars.

Bulk ``update()`` / ``delete()`` statements bypass the ORM and are not seen.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from naas_abi.apps.nexus.apps.api.app.models import (
    AgentConfigModel,
    AppConfigModel,
    OrganizationMemberModel,
    OrganizationModel,
    OrganizationRoleFeaturesModel,
    UserModel,
    WorkspaceMemberModel,
    WorkspaceModel,
)
from naas_abi.apps.nexus.apps.api.app.services.identity_events.events import (
    EVENT_CLASSES,
    NexusIdentityEvent,
)
from naas_abi.apps.nexus.apps.api.app.services.identity_graph import iris
from naas_abi_core import logger
from naas_abi_core.services.event.context import event_actor_user_id
from sqlalchemy import event as sa_event
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Session

# Order events of one flush the way the records depend on each other.
_KINDS: dict[type, str] = {
    UserModel: "user",
    OrganizationModel: "organization",
    OrganizationMemberModel: "organization_member",
    OrganizationRoleFeaturesModel: "role_features",
    WorkspaceModel: "workspace",
    WorkspaceMemberModel: "workspace_member",
    AppConfigModel: "app",
    AgentConfigModel: "agent",
}
_KIND_ORDER = {kind: index for index, kind in enumerate(_KINDS.values())}
_OP_ORDER = {"create": 0, "update": 1, "delete": 2}

_BOOKKEEPING = {"id", "created_at", "updated_at"}
# Named in changed_fields, value never logged.
_PERSONAL: dict[str, set[str]] = {
    "user": {"name", "email", "avatar", "company", "role", "bio", "hashed_password"},
    "agent": {"system_prompt"},
}
_FIELD_ALIASES: dict[str, dict[str, str]] = {
    "user": {"hashed_password": "password", "role": "job_title"},
}

Change = dict[str, tuple[Any, Any]]


def _values(obj: Any) -> dict[str, Any]:
    state = sa_inspect(obj)
    return {attr.key: state.dict.get(attr.key) for attr in state.mapper.column_attrs}


def _changes(obj: Any, op: str) -> Change:
    state = sa_inspect(obj)
    changes: Change = {}
    for attr in state.mapper.column_attrs:
        key = attr.key
        if key in _BOOKKEEPING:
            continue
        if op == "create":
            value = state.dict.get(key)
            if value is not None:
                changes[key] = (None, value)
            continue
        history = state.attrs[key].history
        if not history.has_changes():
            continue
        old = history.deleted[0] if history.deleted else None
        new = history.added[0] if history.added else None
        if old != new:
            changes[key] = (old, new)
    return changes


def _describe(kind: str, changes: Change) -> tuple[list[str] | None, str | None]:
    if not changes:
        return None, None
    personal = _PERSONAL.get(kind, set())
    aliases = _FIELD_ALIASES.get(kind, {})
    fields = sorted(aliases.get(k, k) for k in changes)
    public = {
        aliases.get(k, k): {"from": old, "to": new}
        for k, (old, new) in changes.items()
        if k not in personal
    }
    return fields, (json.dumps(public, sort_keys=True, default=str) if public else None)


def build_identity_event(
    kind: str,
    op: str,
    values: dict[str, Any],
    changes: Change,
    actor_user_id: str | None,
    site_iri: str | None,
) -> NexusIdentityEvent | None:
    """Map one committed row change to its identity and access event, or None."""
    common: dict[str, Any] = {}
    if site_iri:
        common["occurs_in"] = [site_iri]
    if actor_user_id:
        common["created_by"] = [str(iris.person_iri(actor_user_id))]
    fields, changes_json = _describe(kind, changes)
    common["changed_fields"] = fields
    common["changes_json"] = changes_json

    def verb(names: tuple[str, str, str]) -> str:
        return names[_OP_ORDER[op]]

    def write(key: str, iri_list: list[Any]) -> dict[str, list[str]]:
        return {key: [str(i) for i in iri_list]}

    record_key = verb(("creates", "updates", "deletes"))

    if kind == "user":
        user_id = values["id"]
        name = verb(("CreateUser", "UpdateUser", "DeleteUser"))
        return EVENT_CLASSES[name](
            label=EVENT_CLASSES[name]._name,
            target_user_id=user_id,
            created_for=[str(iris.person_iri(user_id))],
            **write(record_key, [iris.user_account_iri(user_id)]),
            **common,
        )

    if kind == "organization":
        name = verb(("CreateOrganization", "UpdateOrganization", "DeleteOrganization"))
        return EVENT_CLASSES[name](
            label=EVENT_CLASSES[name]._name,
            target_organization_id=values["id"],
            **write(record_key, [iris.organization_profile_iri(values["id"])]),
            **common,
        )

    if kind in ("organization_member", "workspace_member"):
        user_id = values["user_id"]
        scope_key = "organization_id" if kind == "organization_member" else "workspace_id"
        scope_id = values[scope_key]
        if kind == "organization_member":
            membership = iris.organization_membership_iri(scope_id, user_id)
            names = (
                "AddUserToOrganization",
                "ChangeOrganizationMemberRole",
                "RemoveUserFromOrganization",
            )
            target = {"target_organization_id": scope_id}
            scope_record = iris.organization_iri(scope_id)
        else:
            membership = iris.workspace_membership_iri(scope_id, user_id)
            names = ("AddUserToWorkspace", "ChangeWorkspaceMemberRole", "RemoveUserFromWorkspace")
            target = {"target_workspace_id": scope_id}
            scope_record = iris.workspace_iri(scope_id)
        role = values.get("role")
        extra: dict[str, Any] = {}
        if op == "update":
            if "role" not in changes:
                return None
            extra["previous_membership_role"] = changes["role"][0]
        if op == "create":
            extra.update(write("updates", [iris.user_account_iri(user_id), scope_record]))
        name = verb(names)
        return EVENT_CLASSES[name](
            label=EVENT_CLASSES[name]._name,
            target_user_id=user_id,
            membership_role=role,
            created_for=[str(iris.person_iri(user_id))],
            **target,
            **write(record_key, [membership]),
            **extra,
            **common,
        )

    if kind == "workspace":
        name = verb(("CreateWorkspace", "UpdateWorkspace", "DeleteWorkspace"))
        organization = (
            {"target_organization_id": values["organization_id"]}
            if values.get("organization_id")
            else {}
        )
        return EVENT_CLASSES[name](
            label=EVENT_CLASSES[name]._name,
            target_workspace_id=values["id"],
            **organization,
            **write(record_key, [iris.workspace_iri(values["id"])]),
            **common,
        )

    if kind in ("app", "agent"):
        workspace_id = values["workspace_id"]
        if kind == "app":
            name, record = (
                "ConfigureWorkspaceApp",
                iris.workspace_app_iri(workspace_id, values["app_id"]),
            )
        else:
            name, record = "ConfigureWorkspaceAgent", iris.workspace_agent_iri(values["id"])
        links = write(record_key, [record])
        if record_key != "updates":
            links.update(write("updates", [iris.workspace_iri(workspace_id)]))
        else:
            links["updates"].append(str(iris.workspace_iri(workspace_id)))
        return EVENT_CLASSES[name](
            label=EVENT_CLASSES[name]._name,
            target_workspace_id=workspace_id,
            **links,
            **common,
        )

    if kind == "role_features":
        organization_id = values["organization_id"]
        try:
            roles = sorted(json.loads(values.get("role_baseline") or "{}"))
        except (TypeError, ValueError):
            roles = []
        return EVENT_CLASSES["ConfigureOrganizationRoleFeatures"](
            label=EVENT_CLASSES["ConfigureOrganizationRoleFeatures"]._name,
            target_organization_id=organization_id,
            updates=[str(iris.feature_policy_iri(role, organization_id)) for role in roles]
            or [str(iris.organization_profile_iri(organization_id))],
            **common,
        )

    return None


class IdentityEventCapture:
    """Install/uninstall the ORM listeners. One instance per publisher."""

    def __init__(
        self,
        publish: Callable[[NexusIdentityEvent], Any],
        site_iri: str | None = None,
        on_published: Callable[[int], None] | None = None,
    ):
        self._publish = publish
        self._site_iri = site_iri
        self._on_published = on_published
        self._key = f"nexus_identity_events:{id(self)}"

    def install(self) -> None:
        if not sa_event.contains(Session, "after_flush", self._after_flush):
            sa_event.listen(Session, "after_flush", self._after_flush)
            sa_event.listen(Session, "after_commit", self._after_commit)
            sa_event.listen(Session, "after_rollback", self._after_rollback)

    def uninstall(self) -> None:
        for name, fn in (
            ("after_flush", self._after_flush),
            ("after_commit", self._after_commit),
            ("after_rollback", self._after_rollback),
        ):
            if sa_event.contains(Session, name, fn):
                sa_event.remove(Session, name, fn)

    def _after_flush(self, session: Session, _flush_context: Any) -> None:
        try:
            staged: list[tuple[int, int, NexusIdentityEvent]] = []
            actor = event_actor_user_id.get()
            for op, objects in (
                ("create", session.new),
                ("update", session.dirty),
                ("delete", session.deleted),
            ):
                for obj in objects:
                    kind = _KINDS.get(type(obj))
                    if kind is None:
                        continue
                    changes = _changes(obj, op)
                    if op == "update" and not changes:
                        continue
                    built = build_identity_event(
                        kind, op, _values(obj), changes, actor, self._site_iri
                    )
                    if built is not None:
                        staged.append((_KIND_ORDER[kind], _OP_ORDER[op], built))
            if staged:
                staged.sort(key=lambda item: (item[0], item[1]))
                session.info.setdefault(self._key, []).extend(event for _, _, event in staged)
        except Exception as exc:  # noqa: BLE001
            # Logging identity changes must never break a write.
            logger.warning(f"[identity-events] could not stage events: {exc}")

    def _after_commit(self, session: Session) -> None:
        pending: list[NexusIdentityEvent] = session.info.pop(self._key, [])
        published = 0
        for built in pending:
            try:
                self._publish(built)
                published += 1
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    f"[identity-events] publish failed for {type(built).__name__}: {exc}"
                )
        if published and self._on_published is not None:
            try:
                self._on_published(published)
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"[identity-events] on_published callback failed: {exc}")

    def _after_rollback(self, session: Session) -> None:
        session.info.pop(self._key, None)
