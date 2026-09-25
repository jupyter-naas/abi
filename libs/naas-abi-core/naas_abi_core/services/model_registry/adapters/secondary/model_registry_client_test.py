import asyncio
from unittest.mock import AsyncMock, Mock

import pytest
from naas_abi_core.services.model_registry.adapters.secondary.model_registry_client import (
    ModelRegistryNATSClient,
)
from naas_abi_core.services.model_registry.ModelRegistryPort import ModelNotFoundError
from naas_abi_sdk.transport import RPCError


def test_local_bootstrap_and_remote_error_translation(monkeypatch):
    owner = Mock()
    client = ModelRegistryNATSClient(owner, "nats://unused:4222", "test")
    model = Mock()
    client.register("id", model)
    owner.register.assert_called_once_with("id", model)
    monkeypatch.setattr(
        "naas_abi_core.engine.nats_runtime.run_coro",
        lambda coroutine, timeout: asyncio.run(coroutine),
    )
    client.remote.get_chat_model = AsyncMock(
        side_effect=RPCError("MODEL_NOT_FOUND", "missing")
    )
    with pytest.raises(ModelNotFoundError):
        client.get_chat_model("id")
    client.remote.get_chat_model.assert_awaited_once_with("id", None)
