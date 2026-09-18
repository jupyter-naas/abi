"""Workspace-shared presentation icons, independent of OWL declarations."""
from __future__ import annotations

import re
from typing import Protocol

KINDS = frozenset({"entity", "relationship", "attribute", "annotation", "individual", "file"})
EDIT_ROLES = frozenset({"owner", "admin", "member"})
ICON_NAME = re.compile(r"material-symbols-light:[a-z0-9]+(?:-[a-z0-9]+)*")


class OntologyIconsPort(Protocol):
    async def list_icons(self, workspace_id: str) -> list[dict]: ...

    async def save_icon(
        self, workspace_id: str, kind: str, resource_id: str,
        icon: str | None, user_id: str,
    ) -> None: ...


class OntologyIconsService:
    def __init__(self, repository: OntologyIconsPort):
        self.repository = repository

    async def list_icons(self, workspace_id: str, allowed: set[tuple[str, str]]) -> list[dict]:
        return [item for item in await self.repository.list_icons(workspace_id)
                if (item["kind"], item["resource_id"]) in allowed]

    async def save_icon(
        self, workspace_id: str, role: str, user_id: str,
        allowed: set[tuple[str, str]], kind: str, resource_id: str, icon: str | None,
    ) -> None:
        if role not in EDIT_ROLES:
            raise PermissionError("Only workspace members can change object icons.")
        if kind not in KINDS or (kind, resource_id) not in allowed:
            raise LookupError("This object is not available in the workspace ontologies.")
        if icon is not None and (len(icon) > 160 or not ICON_NAME.fullmatch(icon)):
            raise ValueError("Choose an icon from Material Symbols Light.")
        await self.repository.save_icon(workspace_id, kind, resource_id, icon, user_id)
