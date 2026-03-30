from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from naas_abi.apps.nexus.apps.api.app.services.providers.service import ProviderService


@pytest.mark.asyncio
async def test_list_available_providers_returns_empty_for_user_without_workspaces() -> None:
    adapter = SimpleNamespace(
        list_workspace_ids_for_user=AsyncMock(return_value=[]),
        list_secret_keys_for_workspaces=AsyncMock(return_value=set()),
        list_environment_keys=AsyncMock(return_value=set()),
    )
    service = ProviderService(adapter=adapter)

    providers = await service.list_available_providers(user_id="user-1")

    assert providers == []
    adapter.list_workspace_ids_for_user.assert_awaited_once_with(user_id="user-1")
    adapter.list_secret_keys_for_workspaces.assert_not_called()
    adapter.list_environment_keys.assert_not_called()


@pytest.mark.asyncio
async def test_list_available_providers_includes_ollama_when_workspace_exists() -> None:
    adapter = SimpleNamespace(
        list_workspace_ids_for_user=AsyncMock(return_value=["ws-1"]),
        list_secret_keys_for_workspaces=AsyncMock(return_value=set()),
        list_environment_keys=AsyncMock(return_value=set()),
    )
    service = ProviderService(adapter=adapter)

    providers = await service.list_available_providers(user_id="user-1")

    assert providers[-1].id == "ollama"
    assert providers[-1].has_api_key is False
