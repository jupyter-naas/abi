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
from naas_abi_sdk.cancellation import (
    ActiveCalls,
    CallIdInUse,
    Registration,
    ToolCancellation,
    ToolCancelled,
    bind_cancellation,
    reset_cancellation,
    valid_call_id,
)
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
    tool_cancel_subject,
    tool_subject,
)
from naas_abi_sdk.transport import RPCError

logger = logging.getLogger(__name__)

Authorize = Callable[[str, ToolCaller], Any]

# How long a stopped async handler may take to unwind before the caller is answered.
CANCEL_GRACE_SECONDS = 5.0
# A cancel is answered at once, but may wait for discovery's check of its token.
MAX_CONCURRENT_CANCELS = 16


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
        # Cancels never queue behind the calls they would stop.
        self.cancels = ConcurrentCalls(MAX_CONCURRENT_CANCELS)
        self.active = ActiveCalls()

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
                self.subscriptions.append(
                    await nc.subscribe(
                        tool_cancel_subject(
                            self.session.client.project, self.session.instance_id, name
                        ),
                        cb=self.cancels.callback(partial(self._handle_cancel, name)),
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
        await self.cancels.cancel()

    async def _handle_cancel(self, name: str, msg: Any) -> None:
        response = await self.respond_cancel(name, msg.data, msg.headers or {})
        if msg.reply:
            await reply(msg, response.SerializeToString())

    async def respond_cancel(
        self, name: str, data: bytes, headers: dict[str, str]
    ) -> pb.CancelToolResponse:
        """Stop the call ``call_id`` that the sender of this message started. Never
        raises. Authenticated like a call (discovery checks the token is bound to this
        instance); the module's ``authorize_tool`` hook is not asked: it decides who
        may *run* a tool, and only the identity that started a call can cancel it."""
        response = pb.CancelToolResponse()
        try:
            try:
                request = pb.CancelToolRequest.FromString(data)
            except DecodeError as exc:
                raise RPCError("INVALID_ARGUMENT", "Malformed cancel request") from exc
            if not valid_call_id(request.call_id):
                raise RPCError("INVALID_ARGUMENT", "A cancel names a valid call_id")
            answer = await self._verified(name, headers)
            response.cancelled = self.active.cancel(
                answer.caller_identity, request.call_id
            )
        except RPCError as exc:
            response.error.code = exc.code
            response.error.message = str(exc).removeprefix(f"{exc.code}: ")
        except Exception:
            logger.exception("Module tool %s cancel failed", name)
            response.error.code = "INTERNAL"
            response.error.message = "Cancel failed"
        return response

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
        if request.call_id and not valid_call_id(request.call_id):
            raise RPCError(
                "INVALID_ARGUMENT", "call_id is 1..128 letters, digits, _ or -"
            )
        caller = await self._authorized(name, request, headers)
        if self.closing:
            raise RPCError("MODULE_UNAVAILABLE", "Tool is draining")
        registration = None
        if request.call_id:
            try:
                registration = self.active.register(caller.identity, request.call_id)
            except CallIdInUse:
                raise RPCError(
                    "INVALID_ARGUMENT", "A call with this call_id is already running"
                ) from None
        try:
            return await self._checked(
                name, descriptor, handler, request, caller, registration
            )
        finally:
            if registration is not None:
                registration.release()

    async def _checked(
        self,
        name: str,
        descriptor: ToolDescriptor,
        handler: Any,
        request: pb.InvokeToolRequest,
        caller: ToolCaller,
        registration: Registration | None,
    ) -> bytes:
        if registration is not None and registration.cancelled:
            raise RPCError("CANCELLED", "The call was cancelled")
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
        result = await self._run(
            handler, arguments, call, request.context.timeout_ms, registration
        )
        return self._encode(name, result)

    async def _verified(
        self, name: str, headers: dict[str, str]
    ) -> discovery_pb.AuthorizeToolResponse:
        # Discovery verifies the token is bound to this instance and says who sent it.
        return await self.session.client._call(
            "authorize_tool",
            discovery_pb.AuthorizeToolRequest(
                instance_id=self.session.instance_id,
                lease_token=self.session.lease_token,
                tool_name=name,
                caller_token=headers.get("Nats-Auth-Token", ""),
            ),
            discovery_pb.AuthorizeToolResponse,
        )

    async def _authorized(
        self, name: str, request: pb.InvokeToolRequest, headers: dict[str, str]
    ) -> ToolCaller:
        answer = await self._verified(name, headers)
        user_id = request.context.principal_id
        workspace_id = request.context.workspace_id
        if (
            user_id or workspace_id
        ) and answer.caller_identity not in self.user_callers:
            # Only the engine's own processes authenticate users and name workspaces.
            raise RPCError(
                "PERMISSION_DENIED", "This caller cannot act for a user or workspace"
            )
        caller = ToolCaller(
            answer.caller_identity,
            answer.caller_admin,
            user_id or None,
            workspace_id or None,
        )
        allowed = self.authorize(name, caller)
        if inspect.isawaitable(allowed):
            allowed = await allowed
        if allowed is not True:
            raise RPCError("PERMISSION_DENIED", "Caller may not run this tool")
        return caller

    async def _run(
        self,
        handler: Any,
        arguments: dict[str, Any],
        call: ToolCall,
        timeout_ms: int,
        registration: Registration | None = None,
    ) -> Any:
        seconds = (
            min(timeout_ms / 1000, MAX_DEADLINE_SECONDS)
            if timeout_ms > 0
            else DEFAULT_DEADLINE_SECONDS
        )
        kwargs = {"call": call} if _takes_call(handler) else {}
        cancellation = call.cancellation

        # A TimeoutError the handler raises itself (a socket, an HTTP client) is a
        # failure of the tool, not the deadline: only the wait's own ends it.
        async def run_async() -> Any:
            reset = bind_cancellation(cancellation)
            try:
                return await handler(arguments, **kwargs)
            except (TimeoutError, asyncio.TimeoutError) as exc:
                raise _HandlerTimeout() from exc
            finally:
                reset_cancellation(reset)

        def run_sync() -> Any:
            # A thread started by to_thread has a copy of this context: the token
            # is visible to the handler through current_cancellation() as well.
            reset = bind_cancellation(cancellation)
            try:
                return handler(arguments, **kwargs)
            except (TimeoutError, asyncio.TimeoutError) as exc:
                raise _HandlerTimeout() from exc
            finally:
                reset_cancellation(reset)

        # The handler runs as a task of its own, so that a deadline, a cancel from
        # the caller and the host closing can each stop it: an async handler is
        # cancelled at its next await, a synchronous one is told through
        # ``call.cancellation`` (its thread cannot be interrupted).
        if inspect.iscoroutinefunction(handler):
            work: asyncio.Future[Any] = asyncio.ensure_future(run_async())
        else:
            work = asyncio.ensure_future(asyncio.to_thread(run_sync))
        if registration is not None:
            registration.on_cancel(lambda: self._stop(work, cancellation))
        try:
            return await asyncio.wait_for(asyncio.shield(work), seconds)
        except asyncio.TimeoutError as exc:
            self._stop(work, cancellation)
            await self._unwound(work)
            raise RPCError(
                "DEADLINE_EXCEEDED", f"Tool exceeded its {seconds:g}s deadline"
            ) from exc
        except asyncio.CancelledError:
            # The caller's cancel stopped the handler (work is cancelled), or this
            # task is being cancelled (the host closes): either way stop it.
            self._stop(work, cancellation)
            if registration is not None and registration.cancelled:
                await self._unwound(work)
                raise RPCError("CANCELLED", "The call was cancelled") from None
            raise
        except ToolCancelled as exc:
            raise RPCError("CANCELLED", "The call was cancelled") from exc
        except ToolError as exc:
            raise RPCError("TOOL_ERROR", str(exc)[:MAX_ERROR_CHARACTERS]) from exc
        except Exception as exc:
            # Whatever the handler raised, including an RPCError of its own, stays
            # in this process: the caller gets a code, not the handler's internals.
            logger.exception("Module tool %s failed", call.tool)
            raise RPCError("TOOL_ERROR", "Tool execution failed") from exc

    @staticmethod
    def _stop(work: asyncio.Future[Any], cancellation: ToolCancellation) -> None:
        cancellation.cancel()
        work.cancel()

    @staticmethod
    async def _unwound(work: asyncio.Future[Any]) -> None:
        """Let a stopped handler run its ``finally`` blocks before the caller is answered."""
        await asyncio.wait({work}, timeout=CANCEL_GRACE_SECONDS)
        if work.done() and not work.cancelled():
            work.exception()  # retrieved: never "exception was never retrieved"

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
