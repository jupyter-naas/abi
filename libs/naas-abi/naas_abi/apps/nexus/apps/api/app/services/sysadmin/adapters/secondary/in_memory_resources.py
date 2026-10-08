"""In-memory service data and audit log: test doubles for the resources ports."""

from __future__ import annotations

from datetime import UTC, datetime

from naas_abi.apps.nexus.apps.api.app.services.sysadmin.resources import (
    Action,
    AuditEntry,
    AuditRecord,
    AuditUnavailable,
    InvalidResource,
    ResourceCapabilities,
    ResourceContent,
    ResourceDetail,
    ResourceEntry,
    ResourceNotFound,
    ResourcePage,
    ResourceTooLarge,
    paginate,
    text_preview,
)


class InMemoryResources:
    """Items keyed by ``/``-separated ids; a container is any shared id prefix."""

    def __init__(
        self, service: str, items: dict[str, bytes] | None = None, *, masked: bool = False
    ) -> None:
        self.service = service
        self.items = dict(items or {})
        self.masked = masked
        self.capabilities = ResourceCapabilities(browse=True, create=True, reveal=masked)

    def _is_container(self, resource_id: str) -> bool:
        return any(key.startswith(resource_id + "/") for key in self.items)

    def _entry(self, resource_id: str) -> ResourceEntry:
        name = resource_id.rsplit("/", 1)[-1]
        if resource_id in self.items:
            extra: tuple[Action, ...] = ("reveal",) if self.masked else ("download",)
            actions: tuple[Action, ...] = ("read", "write", "delete", *extra)
            size = None if self.masked else len(self.items[resource_id])
            return ResourceEntry(resource_id, name, "item", actions, size=size)
        if self._is_container(resource_id):
            return ResourceEntry(resource_id, name, "container")
        raise ResourceNotFound(self.service, resource_id)

    def _item(self, resource_id: str) -> bytes:
        if resource_id in self.items:
            return self.items[resource_id]
        if self._is_container(resource_id):
            raise InvalidResource(self.service, f"{resource_id!r} is a container")
        raise ResourceNotFound(self.service, resource_id)

    async def list(
        self, parent: str = "", *, cursor: str | None = None, limit: int = 100
    ) -> ResourcePage:
        if parent and parent in self.items:
            raise InvalidResource(self.service, f"{parent!r} is an item")
        if parent and not self._is_container(parent):
            raise ResourceNotFound(self.service, parent)
        prefix = f"{parent}/" if parent else ""
        children = {
            prefix + key[len(prefix) :].split("/", 1)[0]
            for key in self.items
            if key.startswith(prefix)
        }
        entries = [self._entry(child) for child in sorted(children)]
        return paginate(parent, entries, cursor, limit)

    async def stat(self, resource_id: str) -> ResourceEntry:
        return self._entry(resource_id)

    async def read(self, resource_id: str, *, reveal: bool = False) -> ResourceDetail:
        raw = self._item(resource_id)
        if self.masked and not reveal:
            content = ResourceContent("masked")
        else:
            content = text_preview(raw)
        return ResourceDetail(self._entry(resource_id), content)

    async def download(self, resource_id: str, *, max_bytes: int) -> bytes:
        raw = self._item(resource_id)
        if len(raw) > max_bytes:
            raise ResourceTooLarge(self.service, resource_id, len(raw), max_bytes)
        return raw

    async def write(self, resource_id: str, content: bytes) -> ResourceEntry:
        if not resource_id or self._is_container(resource_id):
            raise InvalidResource(self.service, f"cannot write {resource_id!r}")
        self.items[resource_id] = content
        return self._entry(resource_id)

    async def delete(self, resource_id: str) -> None:
        self._item(resource_id)
        del self.items[resource_id]


class InMemoryAuditLog:
    def __init__(self, *, fail: str = "", actors: dict[str, str] | None = None) -> None:
        self.records: list[AuditRecord] = []
        self._stamped: list[tuple[str, AuditRecord]] = []
        self.fail = fail
        self.actors = actors or {}

    async def record(self, record: AuditRecord) -> None:
        if self.fail:
            raise AuditUnavailable(self.fail)
        self.records.append(record)
        self._stamped.append((datetime.now(UTC).isoformat(), record))

    async def history(
        self, *, service: str | None = None, resource_id: str | None = None, limit: int = 50
    ) -> list[AuditEntry]:
        if self.fail:
            raise AuditUnavailable(self.fail)
        entries = [
            AuditEntry(
                at=at,
                actor_id=r.action.actor_id,
                actor=self.actors.get(r.action.actor_id, r.action.actor_id),
                service=r.action.service,
                operation=r.action.operation,
                resource_id=r.action.resource_id,
                phase=r.phase,
                error=r.error,
            )
            for at, r in self._stamped
            if (service is None or r.action.service == service)
            and (resource_id is None or r.action.resource_id == resource_id)
        ]
        return list(reversed(entries))[:limit]
