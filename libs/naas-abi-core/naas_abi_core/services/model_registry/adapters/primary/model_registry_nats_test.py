import asyncio
from unittest.mock import Mock

from naas_abi_core.services.model_registry.adapters.primary.model_registry_nats import (
    ModelRegistryNATS,
    _Stream,
)
from naas_abi_proto.model_registry.v1 import model_registry_pb2 as pb


def test_waiting_stream_wakes_on_producer_completion():
    async def scenario():
        primary = ModelRegistryNATS(Mock(), "test")
        stream = _Stream("caller")
        finished = asyncio.Event()

        async def producer():
            await finished.wait()

        stream.task = asyncio.create_task(producer())
        primary.streams["id"] = stream
        waiting = asyncio.create_task(
            primary._execute(
                "stream_next", pb.StreamNextRequest(stream_id="id"), "caller"
            )
        )
        await asyncio.sleep(0)
        assert not waiting.done()
        finished.set()
        assert (await asyncio.wait_for(waiting, 1)).done
        assert not stream.reading
        await primary._close("id")

    asyncio.run(scenario())


def test_provider_errors_are_sanitized_and_mapped():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from naas_abi_core.engine.nats_auth import issue_service_token
    from naas_abi_core.services.model_registry.ModelRegistryPort import (
        ModelNotFoundError,
    )

    async def scenario():
        secret = "model-unit-test-secret-at-least-32-bytes"
        primary = ModelRegistryNATS(Mock(), secret)
        for error, code in [
            (RuntimeError("private provider details"), "MODEL_ERROR"),
            (ModelNotFoundError(), "MODEL_NOT_FOUND"),
            (NotImplementedError(), "NOT_SUPPORTED"),
            (ValueError(), "INVALID_ARGUMENT"),
            (TimeoutError(), "DEADLINE_EXCEEDED"),
        ]:
            primary._execute = AsyncMock(side_effect=error)
            request = pb.ChatRequest()
            request.context.timeout_ms = 1000
            msg = SimpleNamespace(
                data=request.SerializeToString(),
                headers={"Nats-Auth-Token": issue_service_token("caller", secret)},
                reply="reply",
                respond=AsyncMock(),
            )
            await primary._handle("chat", msg)
            response = pb.ChatResponse.FromString(msg.respond.call_args.args[0])
            assert response.error.code == code
            assert "private provider details" not in response.error.message

    asyncio.run(scenario())


def test_model_upload_budgets_apply_without_engine_configuration():
    import pytest

    primary = ModelRegistryNATS(Mock(), "test")
    assert primary.transfer.max_upload_bytes == 16 * 1024 * 1024
    assert primary.transfer.max_buffered_upload_bytes == 64 * 1024 * 1024
    with pytest.raises(ValueError, match="finite"):
        ModelRegistryNATS(Mock(), "test", transfer_options={"max_upload_bytes": None})
