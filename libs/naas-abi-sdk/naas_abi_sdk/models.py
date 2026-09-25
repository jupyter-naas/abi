"""Optional LangChain model proxies. Install naas-abi-sdk[models]."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterator, Sequence
from dataclasses import dataclass
from typing import Any

from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from langchain_core.utils.function_calling import convert_to_openai_tool
from naas_abi_proto.model_registry.v1 import model_registry_pb2 as pb
from pydantic import PrivateAttr

from naas_abi_sdk.model_codec import (
    decode_json,
    decode_message,
    encode_json,
    encode_message,
)
from naas_abi_sdk.transfer import model_frames


class ModelConnection:
    """Keep all NATS I/O on the loop that resolved the model."""

    def __init__(self, client):
        self.client = client
        self.loop = asyncio.get_running_loop()

    def sync(self, coroutine):
        try:
            current = asyncio.get_running_loop()
        except RuntimeError:
            current = None
        if current is self.loop or not self.loop.is_running():
            coroutine.close()
            raise RuntimeError(
                "Use async model methods on the SDK loop; its loop must remain running"
            )
        return asyncio.run_coroutine_threadsafe(coroutine, self.loop).result()

    async def on_loop(self, awaitable):
        async def run():
            return await awaitable

        if asyncio.get_running_loop() is self.loop:
            return await awaitable
        if not self.loop.is_running():
            raise RuntimeError("The model's SDK loop is no longer running")
        return await asyncio.wrap_future(
            asyncio.run_coroutine_threadsafe(run(), self.loop)
        )

    async def frames(self, operation, request):
        iterator = model_frames(self.client, operation, request)
        pending = None

        async def advance():
            nonlocal pending
            pending = asyncio.create_task(iterator.__anext__())
            return await pending

        async def close():
            # Cancellation of the concurrent Future does not mean the SDK task
            # has finished its asynchronous generator cleanup.
            if pending is not None and pending is not asyncio.current_task():
                await asyncio.gather(pending, return_exceptions=True)
            await iterator.aclose()

        try:
            while True:
                try:
                    yield await self.on_loop(advance())
                except StopAsyncIteration:
                    break
        finally:
            await self.on_loop(close())

    async def result(self, operation, request, response_type):
        results = [frame async for frame in self.frames(operation, request)]
        if len(results) != 1:
            raise ValueError("Expected one model response")
        return response_type.FromString(results[0])


class ChatModelProxy(BaseChatModel):
    """A chat model whose provider and credentials stay in the owning engine."""

    model_id: str
    provider: str
    _connection: ModelConnection = PrivateAttr()
    _ref: Any = PrivateAttr()

    def __init__(self, *, connection: ModelConnection, ref: pb.ModelRef, **kwargs):
        super().__init__(**kwargs)
        self._connection, self._ref = connection, ref

    @property
    def _llm_type(self) -> str:
        return "abi-nats-chat"

    @property
    def _identifying_params(self) -> dict[str, Any]:
        return {
            "canonical_id": self._ref.canonical_id,
            "provider": self.provider,
            "model_id": self.model_id,
        }

    def bind_tools(self, tools: Sequence, *, tool_choice=None, **kwargs):
        options = dict(kwargs)
        if "ls_structured_output_format" in options:
            value = dict(options["ls_structured_output_format"])
            value["schema"] = convert_to_openai_tool(value["schema"])
            options["ls_structured_output_format"] = value
        if tool_choice is not None:
            options["tool_choice"] = tool_choice
        return self.bind(
            _abi_tools=[convert_to_openai_tool(tool) for tool in tools],
            _abi_tool_options=options,
        )

    def _request(self, messages, stop, kwargs):
        options = dict(kwargs)
        tools = options.pop("_abi_tools", [])
        tool_options = options.pop("_abi_tool_options", {})
        return pb.ChatRequest(
            ref=self._ref,
            messages=[encode_message(m) for m in messages],
            stop=stop or [],
            options_json=encode_json(options),
            tools_json=[encode_json(tool) for tool in tools],
            tool_options_json=encode_json(tool_options),
        )

    async def _agenerate(
        self, messages: list[BaseMessage], stop=None, run_manager=None, **kwargs
    ) -> ChatResult:
        result = await self._connection.result(
            "chat", self._request(messages, stop, kwargs), pb.ChatResponse
        )
        message = decode_message(result.message)
        if not isinstance(message, AIMessage):
            raise TypeError("Remote chat model returned a non-AI message")
        return ChatResult(generations=[ChatGeneration(message=message)])

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        return self._connection.sync(self._agenerate(messages, stop, **kwargs))

    async def _astream(
        self, messages, stop=None, run_manager=None, **kwargs
    ) -> AsyncIterator[ChatGenerationChunk]:
        iterator = self._connection.frames(
            "stream", self._request(messages, stop, kwargs)
        )
        try:
            async for frame in iterator:
                message = decode_message(pb.ChatMessage.FromString(frame))
                if not isinstance(message, AIMessageChunk):
                    raise TypeError("Remote model returned a non-AI chunk")
                chunk = ChatGenerationChunk(message=message)
                if run_manager:
                    await run_manager.on_llm_new_token(chunk.text, chunk=chunk)
                yield chunk
        finally:
            await iterator.aclose()

    def _stream(
        self, messages, stop=None, run_manager=None, **kwargs
    ) -> Iterator[ChatGenerationChunk]:
        stream = self._astream(messages, stop, **kwargs)

        async def advance():
            try:
                return await stream.__anext__()
            except StopAsyncIteration:
                return None

        try:
            while (chunk := self._connection.sync(advance())) is not None:
                if run_manager:
                    run_manager.on_llm_new_token(chunk.text, chunk=chunk)
                yield chunk
        finally:
            self._connection.sync(stream.aclose())


class EmbeddingModelProxy(Embeddings):
    def __init__(self, connection: ModelConnection, ref: pb.ModelRef):
        self._connection, self._ref = connection, ref

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        result = await self._connection.result(
            "embed", pb.EmbedRequest(ref=self._ref, texts=texts), pb.EmbedResponse
        )
        return [list(vector.values) for vector in result.vectors]

    async def aembed_query(self, text: str) -> list[float]:
        result = await self._connection.result(
            "embed",
            pb.EmbedRequest(ref=self._ref, texts=[text], query=True),
            pb.EmbedResponse,
        )
        return list(result.vectors[0].values)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._connection.sync(self.aembed_documents(texts))

    def embed_query(self, text: str) -> list[float]:
        return self._connection.sync(self.aembed_query(text))


@dataclass(frozen=True)
class RemoteModel:
    canonical_id: str
    model_id: str
    provider: str
    model: BaseChatModel | Embeddings
    model_type: str
    name: str | None
    description: str | None
    metadata: dict[str, Any]


def remote_model(client, descriptor: pb.ModelDescriptor) -> RemoteModel:
    connection = ModelConnection(client)
    ref = descriptor.ref
    model = (
        ChatModelProxy(
            connection=connection,
            ref=ref,
            model_id=descriptor.model_id,
            provider=ref.provider,
        )
        if ref.kind == "chat"
        else EmbeddingModelProxy(connection, ref)
    )
    return RemoteModel(
        ref.canonical_id,
        descriptor.model_id,
        ref.provider,
        model,
        ref.kind,
        descriptor.name or None,
        descriptor.description or None,
        decode_json(descriptor.metadata_json, {}),
    )
