"""Serves a module's chat models on instance-addressed NATS subjects.

Inference stays in this process. Callers resolve a ready instance through
discovery and send a unary ``ChatRequest``. Tool schemas travel with that
request, and the reply may contain tool calls. The caller's agent executes
the tools. Streaming is not part of this contract.
"""

from __future__ import annotations

import inspect
import json
import logging
from functools import partial
from typing import Any

from naas_abi_proto.discovery.v1 import discovery_pb2 as discovery_pb
from naas_abi_proto.model_registry.v1 import model_registry_pb2 as pb

from naas_abi_sdk import overflow
from naas_abi_sdk.messages import reply
from naas_abi_sdk.model_codec import decode_json, decode_message, encode_message
from naas_abi_sdk.transport import RPCError

logger = logging.getLogger(__name__)

MAX_MESSAGES = 1024
MAX_TOOLS = 128
MAX_REQUEST_BYTES = 512 * 1024


def model_subject(project: str, instance_id: str, name: str) -> str:
    return f"abi.mod.{project}.{instance_id}.model.{name}.chat"


class ModuleModelClient:
    """Unary chat client for one model on one module instance."""

    def __init__(self, transport: Any, subject: str) -> None:
        self._transport, self.subject = transport, subject

    async def chat(self, request: pb.ChatRequest) -> pb.ChatResponse:
        return await self._transport.call(self.subject, request, pb.ChatResponse)


class ModelHost:
    def __init__(self, session: Any, handlers: dict[str, Any]) -> None:
        self.session, self.handlers = session, handlers
        self.subscriptions: list[Any] = []
        self.closing = False

    async def start(self) -> None:
        nc = await self.session.client.transport.connect()
        try:
            for name in self.handlers:
                self.subscriptions.append(
                    await nc.subscribe(
                        model_subject(
                            self.session.client.project,
                            self.session.instance_id,
                            name,
                        ),
                        cb=partial(self._handle, name),
                    )
                )
            await nc.flush()
        except BaseException:
            await self.close()
            raise

    async def close(self) -> None:
        for subscription in self.subscriptions:
            await subscription.unsubscribe()
        self.subscriptions.clear()

    async def _handle(self, name: str, msg: Any) -> None:
        response = pb.ChatResponse()
        try:
            if len(msg.data) > MAX_REQUEST_BYTES or overflow.REQUEST_HEADER in (
                msg.headers or {}
            ):
                raise RPCError("PAYLOAD_TOO_LARGE", "Model request exceeds 512 KiB")
            request = pb.ChatRequest.FromString(msg.data)
            await self.session.client._call(
                "authorize_model",
                discovery_pb.AuthorizeModelRequest(
                    instance_id=self.session.instance_id,
                    lease_token=self.session.lease_token,
                    model_name=name,
                    caller_token=(msg.headers or {}).get("Nats-Auth-Token", ""),
                ),
                discovery_pb.AuthorizeModelResponse,
            )
            response.message.CopyFrom(await self._invoke(name, request))
        except RPCError as exc:
            response.error.code = exc.code
            response.error.message = str(exc)
        except Exception:
            logger.exception("Module model %s failed", name)
            response.error.code = "MODEL_ERROR"
            response.error.message = "Model execution failed"
        if msg.reply:
            await reply(msg, response.SerializeToString())

    async def _invoke(self, name: str, request: pb.ChatRequest) -> pb.ChatMessage:
        if self.closing:
            raise RPCError("MODULE_UNAVAILABLE", "Model is draining")
        if request.ref.canonical_id not in ("", name):
            raise RPCError("INVALID_ARGUMENT", "Model request names another model")
        if not request.messages or len(request.messages) > MAX_MESSAGES:
            raise RPCError("INVALID_ARGUMENT", "Model request needs 1 to 1024 messages")
        if len(request.tools_json) > MAX_TOOLS:
            raise RPCError("INVALID_ARGUMENT", "Model request allows at most 128 tools")
        try:
            messages = [decode_message(message) for message in request.messages]
            tools = [decode_json(tool) for tool in request.tools_json]
            tool_options = decode_json(request.tool_options_json, {})
        except (ValueError, json.JSONDecodeError) as exc:
            raise RPCError(
                "INVALID_ARGUMENT", "Invalid model message or tools"
            ) from exc
        if any(not isinstance(tool, dict) for tool in tools) or not isinstance(
            tool_options, dict
        ):
            raise RPCError("INVALID_ARGUMENT", "Tools must be JSON definitions")
        if tool_options and not tools:
            raise RPCError("INVALID_ARGUMENT", "Tool options require tool definitions")
        handler = self.handlers[name]
        kwargs = _handler_kwargs(handler, tools, tool_options)
        result = await handler.invoke(messages, **kwargs)
        from langchain_core.messages import AIMessage

        if isinstance(result, str):
            result = AIMessage(content=result)
        if not isinstance(result, AIMessage):
            raise RPCError("MODEL_ERROR", "Model result must be text or an AIMessage")
        return encode_message(result)


def _handler_kwargs(handler: Any, tools: list[dict], tool_options: dict) -> dict:
    """Pass tool schemas only to a handler that declares them.

    A text-only ``invoke(messages)`` stays valid. A handler that receives tools
    can return an ``AIMessage`` with tool calls; it does not run the tools.
    """
    if not tools and not tool_options:
        return {}
    params = inspect.signature(handler.invoke).parameters
    accepts_any = any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values())
    if not accepts_any and "tools" not in params:
        raise RPCError("UNIMPLEMENTED", "This model handler does not accept tools")
    kwargs: dict[str, Any] = {"tools": tools}
    if tool_options and (accepts_any or "tool_options" in params):
        kwargs["tool_options"] = tool_options
    return kwargs
