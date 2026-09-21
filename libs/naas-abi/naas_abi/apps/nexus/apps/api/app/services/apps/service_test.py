from __future__ import annotations

from datetime import UTC, datetime

import pytest
from naas_abi.apps.nexus.apps.api.app.services.apps.port import (
    AppConfigCreateInput,
    AppConfigRecord,
    AppConfigUpdateInput,
    AppPersistencePort,
)
from naas_abi.apps.nexus.apps.api.app.services.apps.service import AppsService


class _MemoryAdapter(AppPersistencePort):
    def __init__(self) -> None:
        self.rows: dict[tuple[str, str], AppConfigRecord] = {}

    async def list_by_workspace(self, workspace_id: str) -> list[AppConfigRecord]:
        return [r for (ws, _), r in self.rows.items() if ws == workspace_id]

    async def get(self, workspace_id: str, app_id: str) -> AppConfigRecord | None:
        return self.rows.get((workspace_id, app_id))

    async def create(self, data: AppConfigCreateInput) -> AppConfigRecord:
        now = datetime(2026, 9, 10, tzinfo=UTC)
        record = AppConfigRecord(
            id=f"cfg-{len(self.rows)}",
            workspace_id=data.workspace_id,
            app_id=data.app_id,
            enabled=data.enabled,
            created_at=now,
            updated_at=now,
        )
        self.rows[(data.workspace_id, data.app_id)] = record
        return record

    async def update(
        self, workspace_id: str, app_id: str, updates: AppConfigUpdateInput
    ) -> AppConfigRecord | None:
        record = self.rows.get((workspace_id, app_id))
        if record is None:
            return None
        if updates.enabled is not None:
            record.enabled = updates.enabled
        return record

    async def delete(self, workspace_id: str, app_id: str) -> bool:
        return self.rows.pop((workspace_id, app_id), None) is not None


@pytest.mark.asyncio
async def test_upsert_creates_a_missing_row_with_the_requested_state() -> None:
    service = AppsService(adapter=_MemoryAdapter())
    record = await service.upsert_app_config("ws", "m:app", AppConfigUpdateInput(enabled=True))
    assert record.enabled is True


@pytest.mark.asyncio
async def test_upsert_creates_off_when_enabled_is_omitted() -> None:
    service = AppsService(adapter=_MemoryAdapter())
    record = await service.upsert_app_config("ws", "m:app", AppConfigUpdateInput())
    assert record.enabled is False


@pytest.mark.asyncio
async def test_upsert_updates_an_existing_row() -> None:
    adapter = _MemoryAdapter()
    service = AppsService(adapter=adapter)
    await service.create_app_config(AppConfigCreateInput("ws", "m:app", enabled=True))

    record = await service.upsert_app_config("ws", "m:app", AppConfigUpdateInput(enabled=False))

    assert record.enabled is False
    assert len(adapter.rows) == 1
