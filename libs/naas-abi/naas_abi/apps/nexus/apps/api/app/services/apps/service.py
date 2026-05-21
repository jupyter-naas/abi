"""AppsService — per-workspace app config (CRUD + enable/disable).

The catalog discovery + HTTP response assembly live in the FastAPI primary
adapter. This service owns persistence of per-workspace app configuration
(currently just the ``enabled`` flag, extensible).
"""

from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.services.apps.port import (
    AppConfigCreateInput,
    AppConfigRecord,
    AppConfigUpdateInput,
    AppPersistencePort,
)


class AppAlreadyConfiguredError(Exception):
    """Raised when creating a config that already exists for (workspace, app)."""


class AppsService:
    """Per-workspace config for marketplace + built-in apps."""

    def __init__(self, adapter: AppPersistencePort | None = None):
        self.adapter = adapter

    def _require_adapter(self) -> AppPersistencePort:
        if self.adapter is None:
            raise RuntimeError("AppsService has no persistence adapter configured")
        return self.adapter

    async def list_app_configs(self, workspace_id: str) -> list[AppConfigRecord]:
        if self.adapter is None:
            return []
        return await self.adapter.list_by_workspace(workspace_id)

    async def get_app_config(
        self, workspace_id: str, app_id: str
    ) -> AppConfigRecord | None:
        if self.adapter is None:
            return None
        return await self.adapter.get(workspace_id, app_id)

    async def create_app_config(self, data: AppConfigCreateInput) -> AppConfigRecord:
        adapter = self._require_adapter()
        existing = await adapter.get(data.workspace_id, data.app_id)
        if existing is not None:
            raise AppAlreadyConfiguredError(
                f"App config for ({data.workspace_id}, {data.app_id}) already exists"
            )
        return await adapter.create(data)

    async def update_app_config(
        self,
        workspace_id: str,
        app_id: str,
        updates: AppConfigUpdateInput,
    ) -> AppConfigRecord | None:
        adapter = self._require_adapter()
        return await adapter.update(workspace_id, app_id, updates)

    async def delete_app_config(self, workspace_id: str, app_id: str) -> bool:
        adapter = self._require_adapter()
        return await adapter.delete(workspace_id, app_id)

    async def get_enabled_states(self, workspace_id: str) -> dict[str, bool]:
        """Return ``{app_id: enabled}`` for every record in ``workspace_id``.

        Apps without a stored record are absent from the result; callers
        should default missing entries to ``True`` (enabled by default).
        """
        records = await self.list_app_configs(workspace_id)
        return {r.app_id: r.enabled for r in records}
