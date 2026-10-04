import asyncio
import io
from unittest.mock import Mock

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
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
                _client=SimpleNamespace(max_payload=1024 * 1024, publish=AsyncMock()),
            )
            await primary._handle("chat", msg)
            response = pb.ChatResponse.FromString(msg._client.publish.call_args.args[1])
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


@pytest.fixture
def spans(monkeypatch):
    pytest.importorskip("opentelemetry.sdk")
    from naas_abi_sdk import telemetry
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(telemetry, "_tracer", lambda: provider.get_tracer("test"))
    return exporter


class UsageModel(BaseChatModel):
    """Reports token usage like real providers; can fail like one."""

    fail: bool = False

    @property
    def _llm_type(self) -> str:
        return "usage-test"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        if self.fail:
            raise RuntimeError("provider rejected key sk-private")
        usage = {"input_tokens": 7, "output_tokens": 3, "total_tokens": 10}
        message = AIMessage(content="answer text", usage_metadata=usage)
        return ChatResult(generations=[ChatGeneration(message=message)])

    async def _astream(self, messages, stop=None, run_manager=None, **kwargs):
        for content, output in (("ans", 1), ("wer", 2)):
            usage = {
                "input_tokens": 7 if content == "ans" else 0,
                "output_tokens": output,
                "total_tokens": output + (7 if content == "ans" else 0),
            }
            yield ChatGenerationChunk(
                message=AIMessageChunk(content=content, usage_metadata=usage)
            )


def _registry_primary(fail=False):
    from langchain_core.embeddings import DeterministicFakeEmbedding
    from naas_abi_core.models.Model import ChatModel, EmbeddingModel

    models = {
        "gpt-x": ChatModel(
            model_id="gpt-x-2026", provider="openai", model=UsageModel(fail=fail)
        ),
        "embed-x": EmbeddingModel(
            model_id="embed-x-v2",
            provider="openai",
            model=DeterministicFakeEmbedding(size=4),
        ),
    }
    primary = ModelRegistryNATS(Mock(), "test")
    primary._resolve = lambda ref: (ref.canonical_id, models[ref.canonical_id])
    return primary


def _frames(primary, operation, request):
    async def collect():
        source = io.BytesIO(request.SerializeToString())
        return [f async for f in primary._transfer_frames(operation, b"", source)]

    return asyncio.run(collect())


def _chat_request():
    from langchain_core.messages import HumanMessage
    from naas_abi_sdk.model_codec import encode_message

    return pb.ChatRequest(
        ref=pb.ModelRef(canonical_id="gpt-x", kind="chat"),
        messages=[encode_message(HumanMessage("secret prompt"))],
    )


def _assert_no_content(span):
    for value in span.attributes.values():
        assert not any(
            word in str(value) for word in ("secret prompt", "answer", "alpha")
        )


@pytest.mark.parametrize("operation", ["chat", "stream"])
def test_a_transferred_chat_runs_in_a_model_span_without_content(spans, operation):
    from opentelemetry.trace import SpanKind

    assert _frames(_registry_primary(), operation, _chat_request())

    (span,) = spans.get_finished_spans()
    assert span.name == f"model {operation} gpt-x" and span.kind is SpanKind.INTERNAL
    assert span.attributes["abi.model.id"] == "gpt-x"
    assert span.attributes["abi.model.kind"] == "chat"
    assert span.attributes["abi.model.provider"] == "openai"
    assert span.attributes["abi.model.provider_model_id"] == "gpt-x-2026"
    assert span.attributes["abi.model.adapter"] == "UsageModel"
    assert span.attributes["abi.model.inputs"] == 1
    assert span.attributes["abi.model.usage.input_tokens"] == 7
    assert span.attributes["abi.model.usage.output_tokens"] == 3
    assert span.attributes["abi.model.usage.total_tokens"] == 10
    _assert_no_content(span)


def test_a_transferred_embedding_runs_in_a_model_span_without_content(spans):
    request = pb.EmbedRequest(
        ref=pb.ModelRef(canonical_id="embed-x", kind="embedding"),
        texts=["alpha", "beta"],
    )
    assert _frames(_registry_primary(), "embed", request)

    (span,) = spans.get_finished_spans()
    assert span.name == "model embed embed-x"
    assert span.attributes["abi.model.kind"] == "embedding"
    assert span.attributes["abi.model.provider_model_id"] == "embed-x-v2"
    assert span.attributes["abi.model.adapter"] == "DeterministicFakeEmbedding"
    assert span.attributes["abi.model.inputs"] == 2
    assert "abi.model.usage.input_tokens" not in span.attributes
    _assert_no_content(span)


def test_a_failing_model_call_fails_its_span_and_still_raises(spans):
    from opentelemetry.trace import StatusCode

    with pytest.raises(RuntimeError, match="sk-private"):
        _frames(_registry_primary(fail=True), "chat", _chat_request())

    (span,) = spans.get_finished_spans()
    assert span.name == "model chat gpt-x"
    assert span.status.status_code is StatusCode.ERROR
    assert span.events[0].attributes["exception.type"] == "RuntimeError"


def _one_shot(primary, secret, headers):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from naas_abi_core.engine.nats_auth import issue_service_token

    request = _chat_request()
    request.context.timeout_ms = 5000
    msg = SimpleNamespace(
        subject="abi.svc.model_registry.v1.chat",
        data=request.SerializeToString(),
        headers={"Nats-Auth-Token": issue_service_token("caller", secret), **headers},
        reply="reply",
        respond=AsyncMock(),
        _client=SimpleNamespace(max_payload=1024 * 1024, publish=AsyncMock()),
    )
    asyncio.run(primary._handle("chat", msg))
    return pb.ChatResponse.FromString(msg._client.publish.call_args.args[1])


def _caller_headers():
    from opentelemetry import trace
    from opentelemetry.propagate import inject
    from opentelemetry.trace import NonRecordingSpan, SpanContext, TraceFlags

    parent = SpanContext(
        trace_id=0x1234, span_id=0x5678, is_remote=True, trace_flags=TraceFlags(1)
    )
    headers: dict[str, str] = {}
    inject(headers, context=trace.set_span_in_context(NonRecordingSpan(parent)))
    return headers


def test_a_one_shot_model_call_continues_the_callers_trace(spans):
    from opentelemetry.trace import SpanKind

    secret = "model-unit-test-secret-at-least-32-bytes"
    primary = _registry_primary()
    primary.secret = secret

    assert not _one_shot(primary, secret, _caller_headers()).HasField("error")

    by_name = {span.name: span for span in spans.get_finished_spans()}
    server = next(s for s in by_name.values() if s.kind is SpanKind.SERVER)
    model = by_name["model chat gpt-x"]
    assert server.context.trace_id == model.context.trace_id == 0x1234
    assert model.parent.span_id == server.context.span_id


def test_a_failed_one_shot_call_marks_its_server_span(spans):
    from opentelemetry.trace import SpanKind, StatusCode

    secret = "model-unit-test-secret-at-least-32-bytes"
    primary = _registry_primary(fail=True)
    primary.secret = secret

    assert _one_shot(primary, secret, _caller_headers()).error.code == "MODEL_ERROR"

    (server,) = [s for s in spans.get_finished_spans() if s.kind is SpanKind.SERVER]
    assert server.status.status_code is StatusCode.ERROR
    assert "MODEL_ERROR" in server.status.description
    assert "sk-private" not in server.status.description
