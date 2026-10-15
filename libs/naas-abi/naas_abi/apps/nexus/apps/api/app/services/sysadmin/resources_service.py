"""Use cases over kernel service data: browse, read, and audited changes.

Reads (list, stat, read, download) are plain. Changes (create, replace, delete)
and reveals are audited: a ``requested`` record is written before the call and
nothing happens if it cannot be (``AuditUnavailable``); ``succeeded`` or
``failed`` follows. Replacing or deleting needs the resource id typed back as
``confirm``.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from typing import TypeVar, cast

from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import SourceUnavailable
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.resources import (
    AdminAction,
    AdminAuditLog,
    AuditEntry,
    AuditRecord,
    AuditUnavailable,
    ConfirmationRequired,
    ExpiringResources,
    InvalidResource,
    ResourceDetail,
    ResourceEntry,
    ResourceNotFound,
    ResourcePage,
    ResourceServiceInfo,
    ResourceTooLarge,
    ServiceResources,
    UnknownService,
    UnsupportedOperation,
)
from naas_abi_core import logger

T = TypeVar("T")
# ``list`` is also a method name below.
AuditEntries = list[AuditEntry]

UPLOAD_LIMIT = 25 * 1024 * 1024
DOWNLOAD_LIMIT = 100 * 1024 * 1024


class ResourceAdminService:
    def __init__(
        self,
        sources: Mapping[str, ServiceResources | SourceUnavailable],
        audit: AdminAuditLog,
        *,
        upload_limit: int = UPLOAD_LIMIT,
        download_limit: int = DOWNLOAD_LIMIT,
    ) -> None:
        self._sources = dict(sources)
        self._audit = audit
        self.upload_limit = upload_limit
        self.download_limit = download_limit

    def services(self) -> list[ResourceServiceInfo]:
        infos = []
        for name, source in sorted(self._sources.items()):
            if isinstance(source, SourceUnavailable):
                infos.append(ResourceServiceInfo(name, False, source.reason))
            else:
                infos.append(ResourceServiceInfo(name, True, capabilities=source.capabilities))
        return infos

    def _source(self, service: str) -> ServiceResources:
        if service not in self._sources:
            raise UnknownService(service)
        source = self._sources[service]
        if isinstance(source, SourceUnavailable):
            raise source
        return source

    # --- reads -----------------------------------------------------------------------

    async def list(
        self,
        service: str,
        parent: str = "",
        *,
        cursor: str | None = None,
        limit: int = 100,
        query: str | None = None,
    ) -> ResourcePage:
        source = self._source(service)
        if not (source.capabilities.browse or source.capabilities.lookup):
            raise UnsupportedOperation(service, "list")
        if query and source.capabilities.search:
            return await source.list(parent, cursor=cursor, limit=limit, query=query)
        return await source.list(parent, cursor=cursor, limit=limit)

    async def history(
        self, service: str | None = None, resource_id: str | None = None, *, limit: int = 50
    ) -> AuditEntries:
        """What super admins changed or revealed, newest first."""
        if service is not None and service not in self._sources:
            raise UnknownService(service)
        try:
            return await self._audit.history(service=service, resource_id=resource_id, limit=limit)
        except AuditUnavailable as exc:
            raise SourceUnavailable("audit", exc.reason) from exc

    async def read(self, service: str, resource_id: str) -> ResourceDetail:
        return await self._source(service).read(resource_id)

    async def download(self, service: str, resource_id: str) -> tuple[ResourceEntry, bytes]:
        source = self._source(service)
        entry = await source.stat(resource_id)
        if "download" not in entry.actions:
            raise UnsupportedOperation(service, "download")
        if entry.size is not None and entry.size > self.download_limit:
            raise ResourceTooLarge(service, resource_id, entry.size, self.download_limit)
        return entry, await source.download(resource_id, max_bytes=self.download_limit)

    # --- audited ---------------------------------------------------------------------

    async def reveal(self, actor_id: str, service: str, resource_id: str) -> ResourceDetail:
        source = self._source(service)
        if not source.capabilities.reveal:
            raise UnsupportedOperation(service, "reveal")
        await source.stat(resource_id)
        action = AdminAction(actor_id, service, "reveal", resource_id)
        return await self._audited(action, lambda: source.read(resource_id, reveal=True))

    async def write(
        self,
        actor_id: str,
        service: str,
        resource_id: str,
        content: bytes,
        *,
        confirm: str | None = None,
        ttl_seconds: int | None = None,
    ) -> ResourceEntry:
        source = self._source(service)
        if ttl_seconds is not None and not source.capabilities.expiry:
            raise UnsupportedOperation(service, "expiry")
        if len(content) > self.upload_limit:
            raise ResourceTooLarge(service, resource_id, len(content), self.upload_limit)
        try:
            existing: ResourceEntry | None = await source.stat(resource_id)
        except ResourceNotFound:
            existing = None
        if existing is None:
            if not source.capabilities.create:
                raise UnsupportedOperation(service, "create")
            action = AdminAction(actor_id, service, "create", resource_id)
        else:
            if existing.kind != "item":
                raise InvalidResource(service, f"{resource_id!r} is a container")
            if "write" not in existing.actions:
                raise UnsupportedOperation(service, "write")
            if confirm != resource_id:
                raise ConfirmationRequired(service, resource_id, "replace")
            action = AdminAction(actor_id, service, "replace", resource_id)
        if ttl_seconds is None:
            return await self._audited(action, lambda: source.write(resource_id, content))
        expiring = cast(ExpiringResources, source)  # capabilities.expiry was checked
        return await self._audited(
            action, lambda: expiring.write(resource_id, content, ttl_seconds=ttl_seconds)
        )

    async def delete(
        self, actor_id: str, service: str, resource_id: str, *, confirm: str | None
    ) -> None:
        source = self._source(service)
        entry = await source.stat(resource_id)
        if "delete" not in entry.actions:
            raise UnsupportedOperation(service, "delete")
        if confirm != resource_id:
            raise ConfirmationRequired(service, resource_id, "delete")
        action = AdminAction(actor_id, service, "delete", resource_id)
        await self._audited(action, lambda: source.delete(resource_id))

    async def _audited(self, action: AdminAction, call: Callable[[], Awaitable[T]]) -> T:
        return await run_audited(self._audit, action, call)


async def run_audited(
    audit: AdminAuditLog, action: AdminAction, call: Callable[[], Awaitable[T]]
) -> T:
    """A ``requested`` record first (nothing runs without it), then the outcome."""
    await audit.record(AuditRecord(action, "requested"))
    try:
        result = await call()
    except BaseException as exc:
        # The type only: messages can echo values.
        await _record_outcome(audit, AuditRecord(action, "failed", error=type(exc).__name__))
        raise
    await _record_outcome(audit, AuditRecord(action, "succeeded"))
    return result


async def _record_outcome(audit: AdminAuditLog, record: AuditRecord) -> None:
    try:
        await audit.record(record)
    except AuditUnavailable as exc:
        # The change already happened and its request is on record.
        logger.warning(f"sysadmin audit: could not record {record.phase}: {exc.reason}")
