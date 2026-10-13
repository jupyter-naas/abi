"""Coding environments as two containers: ``environments`` and ``templates``.

``environments/<workspace id>`` is one workspace of any user: read shows its
status as JSON (owner, template, phase, created), delete deletes it.
``templates/<template id>`` is read-only. Wraps the engine's
``CodingEnvironmentService`` (sync, so calls run in a worker thread). A backend
that cannot list every user's workspaces still opens one by its id.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from typing import Any, TypeVar

from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import SourceUnavailable
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.resources import (
    Action,
    InvalidResource,
    ResourceCapabilities,
    ResourceDetail,
    ResourceEntry,
    ResourceNotFound,
    ResourcePage,
    UnsupportedOperation,
    paginate,
    text_preview,
)
from naas_abi_core.services.coding_environment.CodingEnvironmentPorts import (
    AccessDeniedError,
    CodingEnvironmentError,
    TemplateNotFoundError,
    WorkspaceNotFoundError,
    WorkspaceStatus,
    WorkspaceTemplate,
)

SERVICE = "coding_environment"
ENVIRONMENTS = "environments"
TEMPLATES = "templates"
LABELS = {ENVIRONMENTS: "Environments", TEMPLATES: "Templates"}
ENVIRONMENT_ACTIONS: tuple[Action, ...] = ("read", "delete")
TEMPLATE_ACTIONS: tuple[Action, ...] = ("read",)

T = TypeVar("T")


def _matches(name: str, query: str | None) -> bool:
    return not query or query.lower() in name.lower()


def _environment(status: WorkspaceStatus) -> ResourceEntry:
    attributes = {"phase": status.phase, "ready": "yes" if status.agent_ready else "no"}
    if status.owner:
        attributes["owner"] = status.owner
    if status.template:
        attributes["template"] = status.template
    summary = " · ".join(p for p in (status.owner, status.template) if p)
    if summary:
        attributes["summary"] = summary
    return ResourceEntry(
        f"{ENVIRONMENTS}/{status.id}",
        status.name,
        "item",
        ENVIRONMENT_ACTIONS,
        modified=status.created_at,
        attributes=attributes,
    )


def _template(template: WorkspaceTemplate) -> ResourceEntry:
    return ResourceEntry(
        f"{TEMPLATES}/{template.id}",
        template.name,
        "item",
        TEMPLATE_ACTIONS,
        attributes={
            "active_version": template.active_version_id,
            "summary": f"Version {template.active_version_id}",
        },
    )


def _json(body: dict[str, Any]) -> bytes:
    return json.dumps(body, indent=2, sort_keys=True).encode()


class CodingEnvironmentResources:
    service = SERVICE
    # Search filters the listing the orchestrator already returned: no extra calls.
    capabilities = ResourceCapabilities(browse=True, lookup=True, search=True)

    def __init__(self, coding_environment: Any) -> None:
        self._ce = coding_environment

    def _guard(self, resource_id: str, call: Callable[[], T]) -> T:
        try:
            return call()
        except (WorkspaceNotFoundError, TemplateNotFoundError):
            raise ResourceNotFound(SERVICE, resource_id) from None
        except NotImplementedError as exc:
            raise UnsupportedOperation(SERVICE, str(exc) or "this operation") from exc
        except AccessDeniedError as exc:
            raise SourceUnavailable(SERVICE, f"access denied by the orchestrator: {exc}") from exc
        except CodingEnvironmentError as exc:
            raise SourceUnavailable(SERVICE, str(exc) or type(exc).__name__) from exc

    # --- sync helpers, run in a worker thread -------------------------------------------

    @staticmethod
    def _split(resource_id: str) -> tuple[str, str]:
        kind, _, key = resource_id.partition("/")
        if kind not in (ENVIRONMENTS, TEMPLATES) or "/" in key:
            raise ResourceNotFound(SERVICE, resource_id)
        return kind, key

    def _templates(self) -> list[WorkspaceTemplate]:
        return sorted(self._ce.list_templates(), key=lambda t: (t.name, t.id))

    def _template_by_id(self, resource_id: str, template_id: str) -> WorkspaceTemplate:
        for template in self._templates():
            if template.id == template_id:
                return template
        raise ResourceNotFound(SERVICE, resource_id)

    def _stat(self, resource_id: str) -> ResourceEntry:
        if resource_id == "":
            return ResourceEntry("", "", "container")
        kind, key = self._split(resource_id)
        if not key:
            return ResourceEntry(kind, LABELS[kind], "container")
        if kind == TEMPLATES:
            return _template(self._template_by_id(resource_id, key))
        return _environment(self._ce.get_status(workspace_id=key))

    def _roots(self) -> list[ResourceEntry]:
        """The two containers, counted (one orchestrator call each, root only)."""
        environments: dict[str, str]
        try:
            count = len(self._ce.list_all_environments())
            plural = "workspace" if count == 1 else "workspaces"
            environments = {"count": str(count), "summary": f"{count} {plural} across every user"}
        except NotImplementedError:
            environments = {"summary": "Open a workspace by its id"}
        templates = len(self._templates())
        return [
            ResourceEntry(ENVIRONMENTS, LABELS[ENVIRONMENTS], "container", attributes=environments),
            ResourceEntry(
                TEMPLATES,
                LABELS[TEMPLATES],
                "container",
                attributes={
                    "count": str(templates),
                    "summary": f"{templates} template{'' if templates == 1 else 's'}",
                },
            ),
        ]

    def _list(
        self, parent: str, cursor: str | None, limit: int, query: str | None = None
    ) -> ResourcePage:
        if parent == "":
            return paginate(parent, self._roots(), cursor, limit)
        if self._stat(parent).kind != "container":
            raise InvalidResource(SERVICE, f"{parent!r} is not a container")
        if parent == TEMPLATES:
            templates = [_template(t) for t in self._templates() if _matches(t.name, query)]
            return paginate(parent, templates, cursor, limit)
        try:
            statuses = self._ce.list_all_environments()
        except NotImplementedError:
            # This backend cannot list every user's workspaces: open one by id.
            return ResourcePage(parent, (), listable=False)
        ordered = sorted(
            (s for s in statuses if _matches(s.name, query)), key=lambda s: (s.name, s.owner, s.id)
        )
        return paginate(parent, [_environment(s) for s in ordered], cursor, limit)

    def _read(self, resource_id: str) -> ResourceDetail:
        entry = self._stat(resource_id)
        if entry.kind != "item":
            raise InvalidResource(SERVICE, f"{resource_id!r} is a container")
        kind, key = self._split(resource_id)
        body: dict[str, Any]
        view: dict[str, Any]
        if kind == TEMPLATES:
            template = self._template_by_id(resource_id, key)
            body = {
                "id": template.id,
                "name": template.name,
                "active_version_id": template.active_version_id,
            }
            view = {
                "type": "status",
                "phase": "template",
                "fields": {
                    "Template": template.name,
                    "Id": template.id,
                    "Active version": template.active_version_id,
                },
            }
        else:
            status = self._ce.get_status(workspace_id=key)
            body = {
                "id": status.id,
                "name": status.name,
                "owner": status.owner or None,
                "template": status.template or None,
                "phase": status.phase,
                "agent_ready": status.agent_ready,
                "created_at": status.created_at,
            }
            view = {
                "type": "status",
                "phase": status.phase,
                "fields": {
                    "Owner": status.owner or None,
                    "Template": status.template or None,
                    "Agent": "Ready" if status.agent_ready else "Not ready",
                    "Workspace id": status.id,
                },
                "created_at": status.created_at,
            }
        return ResourceDetail(entry, text_preview(_json(body)), view=view)

    def _delete(self, resource_id: str) -> None:
        kind, key = self._split(resource_id)
        if kind != ENVIRONMENTS or not key:
            raise UnsupportedOperation(SERVICE, "delete templates")
        self._ce.get_status(workspace_id=key)
        self._ce.delete(workspace_id=key)

    # --- ServiceResources --------------------------------------------------------------

    async def _run(self, resource_id: str, call: Callable[[], T]) -> T:
        return await asyncio.to_thread(self._guard, resource_id, call)

    async def list(
        self, parent: str = "", *, cursor: str | None = None, limit: int = 100, **options: Any
    ) -> ResourcePage:
        query = options.get("query")
        return await self._run(parent, lambda: self._list(parent, cursor, limit, query))

    async def stat(self, resource_id: str) -> ResourceEntry:
        return await self._run(resource_id, lambda: self._stat(resource_id))

    async def read(self, resource_id: str, *, reveal: bool = False) -> ResourceDetail:
        return await self._run(resource_id, lambda: self._read(resource_id))

    async def download(self, resource_id: str, *, max_bytes: int) -> bytes:
        raise UnsupportedOperation(SERVICE, "download")

    async def write(self, resource_id: str, content: bytes) -> ResourceEntry:
        raise UnsupportedOperation(SERVICE, "write")

    async def delete(self, resource_id: str) -> None:
        await self._run(resource_id, lambda: self._delete(resource_id))
