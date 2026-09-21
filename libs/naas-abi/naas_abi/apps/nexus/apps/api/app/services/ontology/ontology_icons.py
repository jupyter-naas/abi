"""Workspace-shared presentation icons, independent of OWL declarations."""
from __future__ import annotations

import re
from typing import Protocol
from urllib.parse import urlparse

KINDS = frozenset({"entity", "relationship", "attribute", "annotation", "individual", "file"})
EDIT_ROLES = frozenset({"owner", "admin", "member"})
ICON_NAME = re.compile(r"material-symbols-light:[a-z0-9]+(?:-[a-z0-9]+)*")
MAX_ICON_VALUE = 2048


def valid_resource_iri(value: str) -> bool:
    return 1 <= len(value) <= 8192 and "://" in value and "\n" not in value and "\r" not in value


def valid_icon_value(icon: str) -> bool:
    if ICON_NAME.fullmatch(icon):
        return True
    if len(icon) > MAX_ICON_VALUE or "\n" in icon or "\r" in icon:
        return False
    if icon.startswith("/uploads/") and ".." not in icon and "//" not in icon[1:]:
        return True
    parsed = urlparse(icon)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc) and parsed.username is None


class OntologyIconsPort(Protocol):
    async def list_icons(self, workspace_id: str) -> list[dict]: ...

    async def save_icon(
        self, workspace_id: str, kind: str, resource_id: str,
        icon: str | None, user_id: str,
    ) -> None: ...


class OntologyIconsService:
    def __init__(self, repository: OntologyIconsPort):
        self.repository = repository

    async def list_icons(self, workspace_id: str, allowed: set[tuple[str, str]] | None) -> list[dict]:
        items = await self.repository.list_icons(workspace_id)
        if allowed is None:
            return items
        return [item for item in items
                if (item["kind"], item["resource_id"]) in allowed
                or (item["kind"] != "file" and valid_resource_iri(item["resource_id"]))]

    async def save_icon(
        self, workspace_id: str, role: str, user_id: str,
        allowed: set[tuple[str, str]], kind: str, resource_id: str, icon: str | None,
    ) -> None:
        if role not in EDIT_ROLES:
            raise PermissionError("Only workspace members can change object icons.")
        catalogued = kind in KINDS and (kind, resource_id) in allowed
        iri_keyed = kind in KINDS and kind != "file" and valid_resource_iri(resource_id)
        if not catalogued and not iri_keyed:
            raise LookupError("This object is not available in the workspace ontologies.")
        if icon is not None and not valid_icon_value(icon):
            raise ValueError("Choose an icon from Material Symbols Light or provide an image URL.")
        await self.repository.save_icon(workspace_id, kind, resource_id, icon, user_id)
