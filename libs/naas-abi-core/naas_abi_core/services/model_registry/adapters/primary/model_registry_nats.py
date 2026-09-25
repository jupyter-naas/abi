"""Authenticated model lookup/inference boundary with bounded pull streams."""

from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass, field
from functools import partial
from typing import Any
from uuid import uuid4

from google.protobuf.message import DecodeError
from langchain_core.messages import AIMessage, AIMessageChunk
from naas_abi_core import logger
from naas_abi_core.engine.nats_auth import (
    InvalidServiceTokenError,
    verify_service_token,
)
from naas_abi_core.engine.nats_transfer import TransferHost, stream_thread
from naas_abi_core.models.Model import ChatModel, EmbeddingModel
from naas_abi_core.services.model_registry.ModelRegistryPort import (
    DefaultModelNotResolvedError,
    IModelRegistry,
    ModelNotFoundError,
    ProviderNotConfiguredError,
)
from naas_abi_proto.model_registry.v1 import model_registry_pb2 as pb
from naas_abi_sdk.model_codec import (
    decode_json,
    decode_message,
    encode_json,
    encode_message,
)

OPERATIONS = {
    "list_models": (pb.ListModelsRequest, pb.ListModelsResponse),
    "resolve": (pb.ResolveRequest, pb.ResolveResponse),
    "chat": (pb.ChatRequest, pb.ChatResponse),
    "embed": (pb.EmbedRequest, pb.EmbedResponse),
    "stream_open": (pb.StreamOpenRequest, pb.StreamOpenResponse),
    "stream_next": (pb.StreamNextRequest, pb.StreamNextResponse),
    "stream_close": (pb.StreamCloseRequest, pb.StreamCloseResponse),
}


@dataclass
class _Stream:
    caller: str
    queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=16))
    task: Any = None
    error: Exception | None = None
    sequence: int = 0
    reading: bool = False
    touched: float = 0


class ModelRegistryNATS:
    def __init__(
        self,
        registry: IModelRegistry,
        secret: str,
        *,
        stream_ttl: float = 30,
        deadline: float | None = None,
        transfer_options: dict | None = None,
    ):
        if any(
            not math.isfinite(v) or v <= 0
            for v in (stream_ttl, deadline)
            if v is not None
        ):
            raise ValueError("Model deadlines must be finite and positive")
        self.registry, self.secret = registry, secret
        self.owner = uuid4().hex
        self.stream_ttl, self.deadline = stream_ttl, deadline
        self.subscriptions: list[Any] = []
        self.tasks: set[asyncio.Task] = set()
        self.streams: dict[str, _Stream] = {}
        self.max_payload = 512 * 1024
        self._active = 0
        options = {
            "max_upload_bytes": 16 * 1024 * 1024,
            "max_buffered_upload_bytes": 64 * 1024 * 1024,
            **(transfer_options or {}),
        }
        if (
            options["max_upload_bytes"] is None
            or options["max_buffered_upload_bytes"] is None
        ):
            raise ValueError("Model upload budgets must be finite")
        self.transfer = TransferHost(
            "abi.svc.model_registry.v1.transfer",
            secret,
            self._transfer_frames,
            operations=("chat", "stream", "embed"),
            total_seconds=deadline,
            error_mapper=self._transfer_error,
            **options,
        )
        self._reaper: asyncio.Task | None = None

    async def start(self, nc) -> None:
        self.max_payload = min(nc.max_payload, self.max_payload)
        try:
            for operation in OPERATIONS:
                self.subscriptions.append(
                    await nc.subscribe(
                        f"abi.svc.model_registry.v1.{operation}",
                        queue="abi.model_registry.owners"
                        if operation not in {"stream_next", "stream_close"}
                        else "",
                        cb=partial(self._dispatch, operation),
                    )
                )
            for operation in ("stream_next", "stream_close"):
                self.subscriptions.append(
                    await nc.subscribe(
                        f"abi.svc.model_registry.v1.{self.owner}.{operation}",
                        cb=partial(self._dispatch, operation),
                    )
                )
            await nc.flush()
            self._reaper = asyncio.create_task(self._expire())
            await self.transfer.start(nc)
        except BaseException:
            await self.stop()
            raise

    async def stop(self) -> None:
        await self.transfer.stop()
        for sub in self.subscriptions:
            await sub.unsubscribe()
        self.subscriptions.clear()
        if self._reaper:
            self._reaper.cancel()
            await asyncio.gather(self._reaper, return_exceptions=True)
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        for stream_id in list(self.streams):
            await self._close(stream_id)

    async def _expire(self):
        while True:
            await asyncio.sleep(min(1, self.stream_ttl))
            now = asyncio.get_running_loop().time()
            for stream_id, stream in list(self.streams.items()):
                if not stream.reading and now - stream.touched > self.stream_ttl:
                    await self._close(stream_id)

    async def _dispatch(self, operation, msg):
        if operation in {"stream_next", "stream_close"}:
            try:
                stream_id = OPERATIONS[operation][0].FromString(msg.data).stream_id
            except DecodeError:
                stream_id = ""
            if ":" in stream_id and stream_id.split(":", 1)[0] != self.owner:
                return
        if len(self.tasks) >= 64:
            response = OPERATIONS[operation][1]()
            response.error.code = "RESOURCE_EXHAUSTED"
            response.error.message = "Model request capacity reached"
            await msg.respond(response.SerializeToString())
            return
        task = asyncio.create_task(self._handle(operation, msg))
        self.tasks.add(task)
        task.add_done_callback(self._finished)

    def _finished(self, task):
        self.tasks.discard(task)
        if not task.cancelled() and task.exception():
            logger.error(
                "Model RPC delivery failed: {}", type(task.exception()).__name__
            )

    async def _handle(self, operation, msg):
        request_type, response_type = OPERATIONS[operation]
        response = response_type()
        try:
            caller = verify_service_token(
                (msg.headers or {}).get("Nats-Auth-Token", ""), self.secret
            )
            if len(msg.data) > self.max_payload:
                raise ValueError("Model request exceeds 512 KiB limit")
            request = request_type.FromString(msg.data)
            timeout = min(
                self.deadline or float("inf"),
                max(0.001, request.context.timeout_ms / 1000),
            )
            response = await asyncio.wait_for(
                self._execute(operation, request, caller), timeout
            )
        except InvalidServiceTokenError:
            response.error.code, response.error.message = (
                "UNAUTHENTICATED",
                "Invalid service token",
            )
        except (
            ModelNotFoundError,
            ProviderNotConfiguredError,
            DefaultModelNotResolvedError,
        ):
            response.error.code, response.error.message = (
                "MODEL_NOT_FOUND",
                "Model or default is not configured",
            )
        except (ValueError, TypeError, DecodeError):
            response.error.code, response.error.message = (
                "INVALID_ARGUMENT",
                "Invalid model request or provider options",
            )
        except NotImplementedError:
            response.error.code, response.error.message = (
                "NOT_SUPPORTED",
                "Provider does not support this operation",
            )
        except TimeoutError:
            response.error.code, response.error.message = (
                "DEADLINE_EXCEEDED",
                "Model request timed out; it was not replayed",
            )
        except PermissionError:
            response.error.code, response.error.message = (
                "PERMISSION_DENIED",
                "Stream belongs to another caller",
            )
        except KeyError:
            response.error.code, response.error.message = (
                "NOT_FOUND",
                "Model stream expired or closed",
            )
        except Exception:  # noqa: BLE001 - sanitize provider failures at RPC boundary
            # Provider exceptions can include credentials or prompt contents.
            response.error.code, response.error.message = (
                "MODEL_ERROR",
                "Remote model inference failed",
            )
        payload = response.SerializeToString()
        if len(payload) > self.max_payload:
            response = response_type()
            response.error.code, response.error.message = (
                "PAYLOAD_TOO_LARGE",
                "Model response exceeds limit",
            )
            payload = response.SerializeToString()
        if msg.reply:
            await msg.respond(payload)

    def _resolve(self, ref):
        if ref.kind not in ("", "chat", "embedding"):
            raise ValueError("Model kind must be chat or embedding")
        if len(ref.canonical_id) > 512 or len(ref.provider) > 128:
            raise ValueError("Model identifier is too long")
        canonical = ref.canonical_id
        if not canonical:
            if ref.kind == "chat":
                canonical = self.registry.default_chat_model_id
            elif ref.kind == "embedding":
                canonical = self.registry.default_embedding_model_id
            if not canonical:
                raise DefaultModelNotResolvedError()
        lookup = {
            "chat": self.registry.get_chat_model,
            "embedding": self.registry.get_embedding_model,
            "": self.registry.get,
        }[ref.kind]
        if ref.model_id:
            for cid, candidate in self.registry.list_registered_models():
                if (
                    cid == canonical
                    and candidate.provider == ref.provider
                    and candidate.model_id == ref.model_id
                ):
                    if (
                        ref.kind == "chat" and not isinstance(candidate, ChatModel)
                    ) or (
                        ref.kind == "embedding"
                        and not isinstance(candidate, EmbeddingModel)
                    ):
                        raise ModelNotFoundError()
                    return canonical, candidate
        model = lookup(canonical, ref.provider or None)
        if ref.model_id and (
            model.model_id != ref.model_id or str(model.provider) != ref.provider
        ):
            raise ModelNotFoundError()
        return canonical, model

    def _descriptor(self, canonical, model):
        metadata = {
            key: getattr(model, key, None)
            for key in (
                "context_window",
                "dimensions",
                "pricing",
                "supported_parameters",
            )
        }
        return pb.ModelDescriptor(
            ref=pb.ModelRef(
                canonical_id=canonical,
                provider=str(model.provider),
                model_id=model.model_id,
                kind="embedding" if isinstance(model, EmbeddingModel) else "chat",
            ),
            model_id=model.model_id,
            name=model.name or "",
            description=model.description or "",
            metadata_json=encode_json(metadata),
        )

    async def _chat(self, request):
        if request.ref.kind != "chat" or not request.messages:
            raise ValueError("Chat requires a chat reference and messages")
        messages = [decode_message(message) for message in request.messages]
        options = decode_json(request.options_json, {})
        tool_options = decode_json(request.tool_options_json, {})
        if not isinstance(options, dict) or not isinstance(tool_options, dict):
            raise TypeError("Model options must be JSON objects")
        # Configuration/credentials and executable runtime objects are never caller options.
        forbidden = {
            "config",
            "callbacks",
            "run_manager",
            "api_key",
            "base_url",
            "client",
            "http_client",
            "messages",
            "input",
            "stop",
            "tools",
        }
        if (
            forbidden.intersection(options)
            or forbidden.intersection(tool_options)
            or any(k.startswith("_") for k in (*options, *tool_options))
        ):
            raise ValueError("Runtime configuration is not a generation option")
        _, wrapper = await asyncio.to_thread(self._resolve, request.ref)
        model = wrapper.model
        if request.tools_json:
            tools = [decode_json(tool) for tool in request.tools_json]
            if any(not isinstance(tool, dict) for tool in tools):
                raise ValueError("Tools must be JSON definitions")
            model = model.bind_tools(tools, **tool_options)
        elif tool_options:
            raise ValueError("Tool options require tool definitions")
        return model, messages, {**options, "stop": list(request.stop) or None}

    async def _produce(self, stream, model, messages, options):
        iterator = model.astream(messages, **options)
        try:

            async def consume():
                async for chunk in iterator:
                    if not isinstance(chunk, AIMessageChunk):
                        raise TypeError("Provider returned a non-AI chunk")
                    encoded = encode_message(chunk)
                    if encoded.ByteSize() > self.max_payload - 128:
                        raise ValueError("Model chunk exceeds payload limit")
                    await stream.queue.put(encoded)

            if self.deadline is None:
                await consume()
            else:
                await asyncio.wait_for(consume(), self.deadline)
        except Exception as exc:  # noqa: BLE001 - deliver stream failure to caller
            stream.error = exc
        finally:
            await iterator.aclose()

    async def _close(self, stream_id):
        stream = self.streams.pop(stream_id, None)
        if stream:
            stream.task.cancel()
            await asyncio.gather(stream.task, return_exceptions=True)

    @staticmethod
    def _transfer_error(exc):
        if isinstance(
            exc,
            (
                ModelNotFoundError,
                ProviderNotConfiguredError,
                DefaultModelNotResolvedError,
            ),
        ):
            return "MODEL_NOT_FOUND", "Model or default is not configured"
        if isinstance(exc, (ValueError, TypeError, DecodeError)):
            return "INVALID_ARGUMENT", "Invalid model request or provider options"
        if isinstance(exc, NotImplementedError):
            return "NOT_SUPPORTED", "Provider does not support this operation"
        logger.opt(exception=exc).error("Model transfer failed")
        return "MODEL_ERROR", "Remote model inference failed"

    async def _transfer_frames(self, operation, metadata, source):
        request_type = pb.EmbedRequest if operation == "embed" else pb.ChatRequest
        request = request_type.FromString(
            await stream_thread(source.read) if source else b""
        )
        if operation != "stream":
            response = await self._execute(operation, request, "")
            yield response.SerializeToString()
            return
        model, messages, options = await self._chat(request)
        iterator = model.astream(messages, **options)
        try:
            async for chunk in iterator:
                if not isinstance(chunk, AIMessageChunk):
                    raise TypeError("Provider returned a non-AI chunk")
                yield encode_message(chunk).SerializeToString()
        finally:
            await iterator.aclose()

    async def _execute(self, operation, request, caller):
        if operation == "list_models":
            entries = await asyncio.to_thread(self.registry.list_registered_models)
            return pb.ListModelsResponse(
                models=[self._descriptor(cid, model) for cid, model in entries],
                default_chat_model_id=self.registry.default_chat_model_id or "",
                default_embedding_model_id=self.registry.default_embedding_model_id
                or "",
            )
        if operation == "resolve":
            cid, model = await asyncio.to_thread(self._resolve, request.ref)
            return pb.ResolveResponse(model=self._descriptor(cid, model))
        if operation == "stream_close":
            stream = self.streams.get(request.stream_id)
            if stream and stream.caller != caller:
                raise PermissionError()
            await self._close(request.stream_id)
            return pb.StreamCloseResponse()
        if operation == "stream_next":
            stream = self.streams[request.stream_id]
            if stream.caller != caller:
                raise PermissionError()
            if stream.reading or request.sequence != stream.sequence:
                raise ValueError("Concurrent or out-of-order stream read")
            stream.reading = True
            stream.touched = asyncio.get_running_loop().time()
            try:
                if stream.queue.empty() and not stream.task.done():
                    waiting = asyncio.create_task(stream.queue.get())
                    try:
                        await asyncio.wait(
                            (waiting, stream.task), return_when=asyncio.FIRST_COMPLETED
                        )
                        if waiting.done():
                            chunk = waiting.result()
                            sequence = stream.sequence
                            stream.sequence += 1
                            return pb.StreamNextResponse(chunk=chunk, sequence=sequence)
                    finally:
                        waiting.cancel()
                        await asyncio.gather(waiting, return_exceptions=True)
                if stream.queue.empty():
                    if stream.error:
                        raise stream.error
                    return pb.StreamNextResponse(done=True, sequence=stream.sequence)
                chunk = stream.queue.get_nowait()
                response = pb.StreamNextResponse(chunk=chunk, sequence=stream.sequence)
                stream.sequence += 1
                return response
            finally:
                stream.reading = False
                stream.touched = asyncio.get_running_loop().time()
        if self._active + len(self.streams) >= 32:
            raise ValueError("Model inference capacity reached")
        self._active += 1
        try:
            if operation == "embed":
                if (
                    request.ref.kind != "embedding"
                    or not 1 <= len(request.texts) <= 1024
                    or (request.query and len(request.texts) != 1)
                ):
                    raise ValueError("Embedding requires 1..1024 texts (one for query)")
                _, wrapper = await asyncio.to_thread(self._resolve, request.ref)
                vectors = (
                    [await wrapper.model.aembed_query(request.texts[0])]
                    if request.query
                    else await wrapper.model.aembed_documents(list(request.texts))
                )
                if len(vectors) != len(request.texts) or any(
                    not math.isfinite(v) for vector in vectors for v in vector
                ):
                    raise ValueError("Provider returned invalid embeddings")
                return pb.EmbedResponse(
                    vectors=[pb.Vector(values=vector) for vector in vectors]
                )
            model, messages, options = await self._chat(
                request.chat if operation == "stream_open" else request
            )
            if operation == "chat":
                message = await model.ainvoke(messages, **options)
                if not isinstance(message, AIMessage):
                    raise TypeError("Provider returned a non-AI message")
                return pb.ChatResponse(message=encode_message(message))
            stream_id = f"{self.owner}:{uuid4().hex}"
            stream = _Stream(caller, touched=asyncio.get_running_loop().time())
            self.streams[stream_id] = stream
            stream.task = asyncio.create_task(
                self._produce(stream, model, messages, options)
            )

            def finished(task):
                if not task.cancelled() and task.exception():
                    stream.error = task.exception()

            stream.task.add_done_callback(finished)
            return pb.StreamOpenResponse(stream_id=stream_id)
        finally:
            self._active -= 1
