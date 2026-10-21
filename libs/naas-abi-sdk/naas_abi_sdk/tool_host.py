"""Serves a module's tools on instance-addressed NATS subjects.

``abi.mod.<project>.<instance>.tool.<name>.invoke`` takes one unary
``InvokeToolRequest`` (``abi.tool.v1``). A call goes through, in this order:
size limits, discovery's check of the caller's token (bound to this instance),
the module's ``authorize_tool`` hook, validation of the arguments against the
tool's input schema and of the configuration against its descriptor, and only
then the handler, under a deadline. Failures carry a stable code and a message
that holds nothing of the handler's internals. Needs the optional ``jsonschema``
(extra ``tools``).
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
from collections.abc import Callable
from functools import partial
from typing import Any

from google.protobuf.message import DecodeError
from naas_abi_proto.discovery.v1 import discovery_pb2 as discovery_pb
from naas_abi_proto.tool.v1 import tool_pb2 as pb

from naas_abi_sdk import overflow
from naas_abi_sdk.broker_flush import flush_to_broker
from naas_abi_sdk.concurrency import DEFAULT_LIMIT, ConcurrentCalls
from naas_abi_sdk.messages import reply
from naas_abi_sdk.tools import (
    DEFAULT_DEADLINE_SECONDS,
    MAX_ARGUMENTS_BYTES,
    MAX_CONFIG_BYTES,
    MAX_DEADLINE_SECONDS,
    MAX_ERROR_CHARACTERS,
    MAX_REQUEST_BYTES,
    MAX_RESULT_BYTES,
    USER_CALLERS,
    ToolCall,
    ToolCaller,
    ToolDescriptor,
    ToolError,
    tool_subject,
)
from naas_abi_sdk.transport import RPCError

logger = logging.getLogger(__name__)

Authorize = Callable[[str, ToolCaller], Any]


def _validator(schema: dict[str, Any]) -> Any:
    try:
        from jsonschema import Draft202012Validator
    except ImportError as exc:  # pragma: no cover - depends on the install
        raise ImportError(
            "Serving tools needs jsonschema: install naas-abi-sdk[tools]"
        ) from exc
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _message(error: Any) -> str:
    where = "/".join(str(part) for part in error.absolute_path)
    return f"{where or 'arguments'}: {error.message}"[:200]


def _json_object(raw: bytes, what: str, limit: int) -> dict[str, Any]:
    if len(raw) > limit:
        raise RPCError("PAYLOAD_TOO_LARGE", f"Tool {what} exceed {limit // 1024} KiB")
    if not raw:
        return {}

    def refuse(constant: str) -> None:
        raise ValueError(constant)

    try:
        value = json.loads(raw, parse_constant=refuse)
    except (ValueError, RecursionError) as exc:
        raise RPCError("INVALID_ARGUMENT", f"Tool {what} are not JSON") from exc
    if not isinstance(value, dict):
        raise RPCError("INVALID_ARGUMENT", f"Tool {what} are a JSON object")
    return value


class ToolHost:
    def __init__(
        self,
        session: Any,
        tools: dict[str, tuple[ToolDescriptor, Any]],
        authorize: Authorize,
        *,
        max_concurrency: int = DEFAULT_LIMIT,
        user_callers: frozenset[str] = USER_CALLERS,
    ) -> None:
        self.session, self.tools = session, tools
        self.authorize, self.user_callers = authorize, user_callers
        self.subscriptions: list[Any] = []
        self.closing = False
        # A bad schema fails here, before the module is ready, not on a call.
        self._validators = {
            name: _validator(dict(descriptor.input_schema))
            for name, (descriptor, _) in tools.items()
        }
        self._output_validators = {
            name: _validator(dict(descriptor.output_schema))
            for name, (descriptor, _) in tools.items()
            if descriptor.output_schema is not None
        }
        self.calls = ConcurrentCalls(max_concurrency)

    async def start(self) -> None:
        nc = await self.session.client.transport.connect()
        try:
            for name in self.tools:
                self.subscriptions.append(
                    await nc.subscribe(
                        tool_subject(
                            self.session.client.project, self.session.instance_id, name
                        ),
                        cb=self.calls.callback(partial(self._handle, name)),
                    )
                )
            await flush_to_broker(nc)
        except BaseException:
            await self.close()
            raise

    async def drain(self, timeout: float) -> None:
        """Take no new call and let those received finish, for up to ``timeout``."""
        self.closing = True
        subscriptions, self.subscriptions = self.subscriptions, []
        for subscription in subscriptions:
            try:
                await subscription.unsubscribe()
            except Exception:
                logger.debug("Tool subscription already closed", exc_info=True)
        try:
            await asyncio.wait_for(self.calls.idle(), timeout)
        except asyncio.TimeoutError:
            logger.warning("Tool calls still running after %.0fs", timeout)

    async def close(self) -> None:
        self.closing = True
        subscriptions, self.subscriptions = self.subscriptions, []
        for subscription in subscriptions:
            try:
                await subscription.unsubscribe()
            except Exception:
                logger.debug("Tool subscription already closed", exc_info=True)
        await self.calls.cancel()

    async def _handle(self, name: str, msg: Any) -> None:
        response = await self.respond(
            name,
            msg.data,
            msg.headers or {},
            uploaded=overflow.REQUEST_HEADER in (msg.headers or {}),
        )
        if msg.reply:
            await reply(msg, response.SerializeToString())

    async def respond(
        self,
        name: str,
        data: bytes,
        headers: dict[str, str],
        *,
        uploaded: bool = False,
    ) -> pb.InvokeToolResponse:
        """One call, as the reply the caller gets. Never raises."""
        response = pb.InvokeToolResponse()
        try:
            response.result_json = await self._invoke(name, data, headers, uploaded)
        except RPCError as exc:
            response.error.code = exc.code
            response.error.message = str(exc).removeprefix(f"{exc.code}: ")
        except Exception:
            logger.exception("Module tool %s failed", name)
            response.error.code = "TOOL_ERROR"
            response.error.message = "Tool execution failed"
        return response

    async def _invoke(
        self, name: str, data: bytes, headers: dict[str, str], uploaded: bool
    ) -> bytes:
        if uploaded or len(data) > MAX_REQUEST_BYTES:
            raise RPCError("PAYLOAD_TOO_LARGE", "Tool request exceeds 512 KiB")
        try:
            request = pb.InvokeToolRequest.FromString(data)
        except DecodeError as exc:
            raise RPCError("INVALID_ARGUMENT", "Malformed tool request") from exc
        descriptor, handler = self.tools[name]
        caller = await self._authorized(name, request, headers)
        if self.closing:
            raise RPCError("MODULE_UNAVAILABLE", "Tool is draining")
        if request.tool not in ("", name):
            raise RPCError("INVALID_ARGUMENT", "Tool request names another tool")
        if request.version not in ("", descriptor.version):
            raise RPCError("TOOL_NOT_FOUND", f"{name}@{request.version}")
        arguments = _json_object(
            request.arguments_json, "arguments", MAX_ARGUMENTS_BYTES
        )
        errors = sorted(self._validators[name].iter_errors(arguments), key=str)
        if errors:
            raise RPCError("INVALID_ARGUMENT", _message(errors[0]))
        config = _json_object(request.config_json, "configuration", MAX_CONFIG_BYTES)
        declared = {c.key: c for c in descriptor.config}
        unknown = sorted(set(config) - set(declared))
        if unknown:
            raise RPCError(
                "INVALID_ARGUMENT", f"Unknown configuration: {unknown}"[:200]
            )
        missing = [
            key
            for key, c in declared.items()
            if c.required and config.get(key) in (None, "")
        ]
        if missing:
            raise RPCError(
                "INVALID_ARGUMENT", f"Missing configuration: {missing}"[:200]
            )
        call = ToolCall(
            tool=name,
            caller=caller,
            config=config,
            trace_id=request.context.trace_id,
        )
        result = await self._run(handler, arguments, call, request.context.timeout_ms)
        return self._encode(name, result)

    async def _authorized(
        self, name: str, request: pb.InvokeToolRequest, headers: dict[str, str]
    ) -> ToolCaller:
        # Discovery verifies the token is bound to this instance and says who sent it.
        answer = await self.session.client._call(
            "authorize_tool",
            discovery_pb.AuthorizeToolRequest(
                instance_id=self.session.instance_id,
                lease_token=self.session.lease_token,
                tool_name=name,
                caller_token=headers.get("Nats-Auth-Token", ""),
            ),
            discovery_pb.AuthorizeToolResponse,
        )
        user_id = request.context.principal_id
        if user_id and answer.caller_identity not in self.user_callers:
            # Only the engine's own processes authenticate users.
            raise RPCError("PERMISSION_DENIED", "This caller cannot act for a user")
        caller = ToolCaller(
            answer.caller_identity,
            answer.caller_admin,
            user_id or None,
            request.context.workspace_id or None,
        )
        allowed = self.authorize(name, caller)
        if inspect.isawaitable(allowed):
            allowed = await allowed
        if allowed is not True:
            raise RPCError("PERMISSION_DENIED", "Caller may not run this tool")
        return caller

    async def _run(
        self, handler: Any, arguments: dict[str, Any], call: ToolCall, timeout_ms: int
    ) -> Any:
        seconds = (
            min(timeout_ms / 1000, MAX_DEADLINE_SECONDS)
            if timeout_ms > 0
            else DEFAULT_DEADLINE_SECONDS
        )
        kwargs = {"call": call} if _takes_call(handler) else {}

        # A TimeoutError the handler raises itself (a socket, an HTTP client) is a
        # failure of the tool, not the deadline: only wait_for's own ends the wait.
        async def run_async() -> Any:
            try:
                return await handler(arguments, **kwargs)
            except (TimeoutError, asyncio.TimeoutError) as exc:
                raise _HandlerTimeout() from exc

        def run_sync() -> Any:
            try:
                return handler(arguments, **kwargs)
            except (TimeoutError, asyncio.TimeoutError) as exc:
                raise _HandlerTimeout() from exc

        try:
            if inspect.iscoroutinefunction(handler):
                return await asyncio.wait_for(run_async(), seconds)
            # A synchronous handler runs on a thread; its deadline stops the wait,
            # not the thread.
            return await asyncio.wait_for(asyncio.to_thread(run_sync), seconds)
        except asyncio.TimeoutError as exc:
            raise RPCError(
                "DEADLINE_EXCEEDED", f"Tool exceeded its {seconds:g}s deadline"
            ) from exc
        except ToolError as exc:
            raise RPCError("TOOL_ERROR", str(exc)[:MAX_ERROR_CHARACTERS]) from exc
        except Exception as exc:
            # Whatever the handler raised, including an RPCError of its own, stays
            # in this process: the caller gets a code, not the handler's internals.
            logger.exception("Module tool %s failed", call.tool)
            raise RPCError("TOOL_ERROR", "Tool execution failed") from exc

    def _encode(self, name: str, result: Any) -> bytes:
        try:
            raw = json.dumps(result, allow_nan=False).encode()
        except (TypeError, ValueError) as exc:
            raise RPCError("TOOL_ERROR", "Tool result is not JSON") from exc
        if len(raw) > MAX_RESULT_BYTES:
            raise RPCError("PAYLOAD_TOO_LARGE", "Tool result exceeds 512 KiB")
        validator = self._output_validators.get(name)
        if validator is not None and not validator.is_valid(result):
            raise RPCError("TOOL_ERROR", "Tool result does not match its output schema")
        return raw


class _HandlerTimeout(Exception):
    """The handler itself raised ``TimeoutError``: a tool failure, not the deadline."""


def _takes_call(handler: Any) -> bool:
    parameters = inspect.signature(handler).parameters
    return "call" in parameters or any(
        p.kind is inspect.Parameter.VAR_KEYWORD for p in parameters.values()
    )
