from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from naas_abi.apps.nexus.apps.api.app.services.iam.port import RequestContext, TokenData
from naas_abi.apps.nexus.apps.api.app.services.secrets.port import SecretRecord
from naas_abi.apps.nexus.apps.api.app.services.secrets.secrets__schema import (
    SecretBulkImportInput,
    SecretCreateInput,
    SecretNotFoundError,
    SecretUpdateInput,
)
from naas_abi.apps.nexus.apps.api.app.services.secrets.service import SecretsService


def _secret(now: datetime) -> SecretRecord:
    return SecretRecord(
        id="sec-1",
        workspace_id="ws-1",
        key="OPENAI_API_KEY",
        encrypted_value="enc-value",
        description="",
        category="api_keys",
        created_at=now,
        updated_at=now,
    )


def _context() -> RequestContext:
    return RequestContext(
        token_data=TokenData(user_id="user-1", scopes={"*"}, is_authenticated=True)
    )


@pytest.mark.asyncio
async def test_create_secret_raises_on_duplicate_key() -> None:
    now = datetime.now()
    adapter = SimpleNamespace(
        get_by_workspace_key=AsyncMock(return_value=_secret(now)),
    )
    service = SecretsService(adapter=adapter)

    with pytest.raises(ValueError):
        await service.create_secret(
            context=_context(),
            secret=SecretCreateInput(
                workspace_id="ws-1",
                key="OPENAI_API_KEY",
                value="abcd",
            ),
            now=now,
        )


@pytest.mark.asyncio
async def test_update_secret_raises_when_not_found() -> None:
    adapter = SimpleNamespace(
        get_by_id=AsyncMock(return_value=None),
    )
    service = SecretsService(adapter=adapter)

    with pytest.raises(SecretNotFoundError):
        await service.update_secret(
            context=_context(),
            secret_id="missing",
            update=SecretUpdateInput(value="new"),
            now=datetime.now(),
        )


@pytest.mark.asyncio
async def test_bulk_import_counts_imported_and_updated() -> None:
    now = datetime.now()
    existing = _secret(now)
    existing.key = "OPENAI_API_KEY"
    existing.workspace_id = "ws-1"

    async def _get_by_workspace_key(workspace_id: str, key: str):
        if key == "OPENAI_API_KEY":
            return existing
        return None

    adapter = SimpleNamespace(
        get_by_workspace_key=AsyncMock(side_effect=_get_by_workspace_key),
        save=AsyncMock(),
        create=AsyncMock(),
        commit=AsyncMock(),
    )
    service = SecretsService(adapter=adapter)

    result = await service.bulk_import(
        context=_context(),
        data=SecretBulkImportInput(
            workspace_id="ws-1",
            env_content="OPENAI_API_KEY=old\nANTHROPIC_API_KEY=new",
        ),
        now=now,
    )

    assert result.updated == 1
    assert result.imported == 1
    assert adapter.save.await_count == 1
    assert adapter.create.await_count == 1
    adapter.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_resolve_secret_returns_none_when_missing() -> None:
    adapter = SimpleNamespace(
        get_by_workspace_key=AsyncMock(return_value=None),
    )
    service = SecretsService(adapter=adapter)

    value = await service.resolve_secret_value(
        context=_context(),
        workspace_id="ws-1",
        key="MISSING",
    )
    assert value is None
