"""Serves a module's workflows and pipelines on instance-addressed NATS subjects.

``abi.mod.<project>.<instance>.process.<kind>.<name>.run`` runs one, and ``.describe``
returns its parameter schema (``abi.process.v1``, docs/adr/20261025_remote-module-processes.md).
Another module reaches them with ``engine.modules[id].get_workflow(name)`` or
``get_pipeline(name)`` (``naas_abi_sdk.process_proxy``).

A call is authorized through discovery before anything else is read: the caller's
token must be bound to this instance, and the process declared on this READY
instance. The host then validates the parameters into the process's model, runs
it for at most the caller's deadline and encodes the result. Parameters and
results above one message travel as body streams (``naas_abi_sdk.app_streams``):
the engine's RPC overflow cannot carry them, since the engine refuses a token
bound to an instance.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import math
import re
import time
from functools import partial
from typing import Any

from google.protobuf.message import DecodeError
from naas_abi_proto.discovery.v1 import discovery_pb2 as discovery_pb
from naas_abi_proto.process.v1 import process_pb2 as pb
from nats.errors import Error as NATSError

from naas_abi_sdk import overflow
from naas_abi_sdk.agent_host import _token_expiry
from naas_abi_sdk.app_host import _drain_subscription
from naas_abi_sdk.app_streams import (
    INLINE_BYTES,
    BodySource,
    BodyTooLarge,
    ReaderGone,
    chunk_bytes,
    pull_body,
)
from naas_abi_sdk.broker_flush import flush_to_broker
from naas_abi_sdk.concurrency import DEFAULT_LIMIT, ConcurrentCalls
from naas_abi_sdk.messages import reply
from naas_abi_sdk.telemetry import server_span
from naas_abi_sdk.transport import RPCError, is_inbox

logger = logging.getLogger(__name__)

KINDS = ("workflow", "pipeline")
# A run lasts at most this long unless the caller asks for another deadline.
DEFAULT_DEADLINE_SECONDS = 300.0
# The longest deadline a caller may ask for, as an agent run's: a longer one would
# hold a call slot (64 of them stop the module serving anyone else) and a drain.
MAX_DEADLINE_SECONDS = 3600.0
# A result stream whose reader stops pulling for this long is dropped. The call keeps
# its slot until then, so a drain waits for the stream: keep the wait short.
STREAM_IDLE_SECONDS = 20.0
# Discovery's answer for a (token, process) is reused this long: never past the
# token's own expiry, and a refusal is never kept.
AUTHORIZATION_SECONDS = 5.0
MAX_AUTHORIZATIONS = 1024
# Parameters and results the same size as any other value an RPC carries.
MAX_BODY_BYTES = overflow.MAX_VALUE_BYTES
# A request's envelope (context, name, headers) around inline parameters.
ENVELOPE_BYTES = 4096
MAX_REQUEST_BYTES = INLINE_BYTES + 64 * 1024
MAX_DESCRIBE_BYTES = 16 * 1024
MAX_ERROR_CHARS = 1000
_INBOX_CHARS = re.compile(r"[A-Za-z0-9_.-]{1,256}")


def process_subject(
    project: str, instance_id: str, kind: str, name: str, operation: str
) -> str:
    return f"abi.mod.{project}.{instance_id}.process.{kind}.{name}.{operation}"


def fits_inline(max_payload: int, size: int) -> bool:
    """Whether ``size`` bytes of parameters or result travel inside the message:
    up to INLINE_BYTES, and one broker message with its envelope. Above it they
    follow from a body inbox."""
    return size <= INLINE_BYTES and size + ENVELOPE_BYTES <= chunk_bytes(max_payload)


def valid_inbox(subject: str) -> bool:
    """An inbox a peer may name for a body: its reply subjects, never a service."""
    return is_inbox(subject) and bool(_INBOX_CHARS.fullmatch(subject))


def encode_result(kind: str, result: Any) -> bytes:
    """A workflow's result as JSON, a pipeline's graph as N-Triples."""
    if kind == "pipeline":
        if not (
            callable(getattr(result, "serialize", None)) and hasattr(result, "triples")
        ):
            raise RPCError("PROCESS_ERROR", "A pipeline must return an rdflib Graph")
        data = result.serialize(format="nt")
        return data if isinstance(data, bytes) else data.encode("utf-8")
    from naas_abi_sdk.processes import serialize_result

    try:
        return json.dumps(
            serialize_result(result), allow_nan=False, separators=(",", ":")
        ).encode("utf-8")
    except (TypeError, ValueError, RecursionError) as exc:
        raise RPCError(
            "PROCESS_ERROR", "A workflow's result must be JSON-serializable"
        ) from exc


def _validation_message(exc: Any) -> str:
    """What a model refused, by field, without the values it was given."""
    problems = [
        f"{'.'.join(str(part) for part in error['loc']) or 'parameters'}: {error['msg']}"
        for error in exc.errors()
    ]
    text = "Invalid parameters: " + "; ".join(problems[:10])
    return text if len(text) <= MAX_ERROR_CHARS else text[: MAX_ERROR_CHARS - 1] + "…"


def parse_parameters(cls: Any, data: Any) -> Any:
    """``data`` (decoded JSON) as the parameters model of the process class
    ``cls``; ``INVALID_ARGUMENT`` names the fields the model refused, never their
    values. A job run validates its payload the same way (``process_jobs``)."""
    from pydantic import ValidationError

    if not isinstance(data, dict):
        raise RPCError("INVALID_ARGUMENT", "Parameters must be a JSON object")
    try:
        return cls.parameters_type().model_validate(data)
    except ValidationError as exc:
        raise RPCError("INVALID_ARGUMENT", _validation_message(exc)) from None


class ProcessHost:
    def __init__(
        self,
        session: Any,
        workflows: dict[str, Any],
        pipelines: dict[str, Any],
        *,
        max_concurrency: int = DEFAULT_LIMIT,
    ) -> None:
        self.session = session
        self.processes: dict[tuple[str, str], Any] = {
            **{("workflow", name): instance for name, instance in workflows.items()},
            **{("pipeline", name): instance for name, instance in pipelines.items()},
        }
        self.subscriptions: list[Any] = []
        self.closing = False
        # Runs side by side, up to max_concurrency at once across the processes;
        # describing one is cheap and never waits behind them.
        self.calls = ConcurrentCalls(max_concurrency)
        self.describes = ConcurrentCalls(DEFAULT_LIMIT)
        self._authorized: dict[tuple[str, str, str], tuple[float, str]] = {}
        # One discovery call per token and process at a time; the others wait for it.
        self._authorizing: dict[tuple[str, str, str], asyncio.Future[str]] = {}
        self._schemas: dict[tuple[str, str], pb.DescribeResponse] = {}
        # Result bodies not over yet, lingering ones included.
        self._sources: set[BodySource] = set()

    async def start(self) -> None:
        nc = await self._nc()
        try:
            for kind, name in self.processes:
                for operation, calls, handler in (
                    ("run", self.calls, self._run),
                    ("describe", self.describes, self._describe),
                ):
                    self.subscriptions.append(
                        await nc.subscribe(
                            process_subject(
                                self.session.client.project,
                                self.session.instance_id,
                                kind,
                                name,
                                operation,
                            ),
                            cb=calls.callback(partial(handler, kind, name)),
                        )
                    )
            await flush_to_broker(nc)
        except BaseException:
            await self.close()
            raise

    async def drain(self, timeout: float) -> None:
        """Stop taking calls and let those in progress finish, for up to ``timeout``
        seconds in all. A call arriving now finds no responder; ``close`` cancels
        what is still running afterwards. A NATS connection already closed or
        draining does not stop the shutdown."""
        self.closing = True
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        subscriptions, self.subscriptions = self.subscriptions, []
        steps = [
            asyncio.ensure_future(
                asyncio.gather(*(_drain_subscription(s) for s in subscriptions))
            ),
            asyncio.ensure_future(
                asyncio.gather(self.calls.idle(), self.describes.idle())
            ),
        ]
        try:
            for step in steps:
                await asyncio.wait({step}, timeout=max(0.0, deadline - loop.time()))
        finally:
            for step in steps:
                step.cancel()
            await asyncio.gather(*steps, return_exceptions=True)

    async def close(self) -> None:
        self.closing = True
        for subscription in self.subscriptions:
            with contextlib.suppress(Exception):
                await subscription.unsubscribe()
        self.subscriptions.clear()
        # A run cut off tells its caller (see _run); the result streams end with an error.
        await self.calls.cancel()
        await self.describes.cancel()
        for source in list(self._sources):
            source.abort("MODULE_UNAVAILABLE", "The module stopped")
        for source in list(self._sources):
            await source.close()
        self._sources.clear()

    async def _nc(self) -> Any:
        return await self.session.client.transport.connect()

    # -- authorization --------------------------------------------------------

    async def _authorize(self, kind: str, name: str, token: str) -> str:
        key = (token, kind, name)
        cached = self._authorized.get(key)
        if cached is not None and asyncio.get_running_loop().time() < cached[0]:
            return cached[1]
        pending = self._authorizing.get(key)
        if pending is None:
            pending = asyncio.ensure_future(self._ask_discovery(kind, name, token))
            self._authorizing[key] = pending
            pending.add_done_callback(partial(self._authorized_now, key))
        return await asyncio.shield(pending)

    def _authorized_now(
        self, key: tuple[str, str, str], future: asyncio.Future[str]
    ) -> None:
        self._authorizing.pop(key, None)
        if not future.cancelled():
            future.exception()  # retrieved: every waiter may have left

    async def _ask_discovery(self, kind: str, name: str, token: str) -> str:
        loop = asyncio.get_running_loop()
        try:
            response = await self.session.client._call(
                "authorize_process",
                discovery_pb.AuthorizeProcessRequest(
                    instance_id=self.session.instance_id,
                    lease_token=self.session.lease_token,
                    process_name=name,
                    process_kind=kind,
                    caller_token=token,
                ),
                discovery_pb.AuthorizeProcessResponse,
            )
        except (NATSError, asyncio.TimeoutError, OSError) as exc:
            raise RPCError("UNAVAILABLE", "Discovery did not answer") from exc
        lifetime = min(AUTHORIZATION_SECONDS, _token_expiry(token) - time.time())
        if lifetime > 0:
            now = loop.time()
            # Reinserted last, so eviction below is oldest-first.
            self._authorized.pop((token, kind, name), None)
            if len(self._authorized) >= MAX_AUTHORIZATIONS:
                self._authorized = {
                    k: v for k, v in self._authorized.items() if v[0] > now
                }
                while len(self._authorized) >= MAX_AUTHORIZATIONS:  # oldest first
                    del self._authorized[next(iter(self._authorized))]
            self._authorized[(token, kind, name)] = (
                now + lifetime,
                response.caller_identity,
            )
        return response.caller_identity

    # -- run ------------------------------------------------------------------

    async def _run(self, kind: str, name: str, msg: Any) -> None:
        with server_span(
            msg.subject,
            msg.headers,
            attributes={"abi.process.kind": kind, "abi.process.name": name},
        ):
            await self._serve_run(kind, name, msg)

    async def _serve_run(self, kind: str, name: str, msg: Any) -> None:
        response = pb.RunResponse()
        payload = b""
        try:
            payload = await self._execute(kind, name, msg)
        except RPCError as exc:
            response.error.code, response.error.message = exc.code, str(exc)
        except DecodeError:
            response.error.code, response.error.message = (
                "INVALID_ARGUMENT",
                "Malformed run request",
            )
        except asyncio.CancelledError:
            # close() cut this run off: its caller learns that instead of waiting
            # out its deadline.
            if self.closing:
                await self._refuse(msg, "CANCELLED", f"The {kind} was stopped")
            raise
        except Exception:
            logger.exception("Module %s %s failed", kind, name)
            response.error.code, response.error.message = (
                "PROCESS_ERROR",
                f"The {kind} failed",
            )
        source: BodySource | None = None
        if not response.HasField("error"):
            try:
                source = await self._place(kind, payload, response)
            except RPCError as exc:
                response = pb.RunResponse()
                response.error.code, response.error.message = exc.code, str(exc)
        if not msg.reply:
            if source is not None:
                await source.close()
            return
        try:
            await reply(msg, response.SerializeToString())
        except Exception:
            logger.warning(
                "Could not send the %s %s's answer", kind, name, exc_info=True
            )
            if source is not None:
                await source.close()
            return
        if source is not None:
            await self._stream(source, payload)

    async def _refuse(self, msg: Any, code: str, message: str) -> None:
        if not msg.reply:
            return
        response = pb.RunResponse()
        response.error.code, response.error.message = code, message
        with contextlib.suppress(Exception):
            await reply(msg, response.SerializeToString())

    async def _execute(self, kind: str, name: str, msg: Any) -> bytes:
        started = asyncio.get_running_loop().time()
        headers = msg.headers or {}
        if len(msg.data) > MAX_REQUEST_BYTES or overflow.REQUEST_HEADER in headers:
            raise RPCError(
                "PAYLOAD_TOO_LARGE",
                "A run request carries large parameters in a body inbox, "
                "not in the message",
            )
        request = pb.RunRequest.FromString(msg.data)
        if self.closing:
            raise RPCError("MODULE_UNAVAILABLE", f"The {kind} host is draining")
        if request.name not in ("", name):
            raise RPCError("INVALID_ARGUMENT", "The run request names another process")
        # Before the parameters are read, however large: an unauthorized caller
        # makes this process pull nothing and run nothing.
        await self._authorize(kind, name, headers.get("Nats-Auth-Token", ""))
        # Zero asks for the default.
        deadline = request.deadline_seconds or DEFAULT_DEADLINE_SECONDS
        if not math.isfinite(deadline) or not 0 < deadline <= MAX_DEADLINE_SECONDS:
            raise RPCError(
                "INVALID_ARGUMENT",
                f"The deadline must be above 0 and at most {MAX_DEADLINE_SECONDS:g} "
                f"seconds (0 means the default, {DEFAULT_DEADLINE_SECONDS:g})",
            )
        instance = self.processes[(kind, name)]

        async def compute() -> bytes:
            parameters = self._validate(instance, await self._parameters(request))
            try:
                result = await instance.run(parameters)
            except (RPCError, asyncio.CancelledError):
                raise
            except Exception:
                logger.exception("Module %s %s failed", kind, name)
                raise RPCError("PROCESS_ERROR", f"The {kind} failed") from None
            return await asyncio.to_thread(encode_result, kind, result)

        remaining = deadline - (asyncio.get_running_loop().time() - started)
        return await _within(
            compute(),
            remaining,
            f"The {kind} passed its {deadline:g} s deadline",
            cancelled=f"The {kind} was cancelled",
        )

    async def _parameters(self, request: pb.RunRequest) -> bytes:
        if not request.parameters_inbox:
            if request.parameters_bytes:
                raise RPCError(
                    "INVALID_ARGUMENT", "Parameters announced without an inbox"
                )
            return request.parameters_json
        if request.parameters_json:
            raise RPCError(
                "INVALID_ARGUMENT", "Parameters are both inline and in an inbox"
            )
        size = request.parameters_bytes
        if size == 0 or not valid_inbox(request.parameters_inbox):
            raise RPCError("INVALID_ARGUMENT", "Invalid parameters inbox or size")
        if size > MAX_BODY_BYTES:
            raise RPCError(
                "PAYLOAD_TOO_LARGE", f"Parameters exceed {MAX_BODY_BYTES} bytes"
            )
        data = bytearray()
        try:
            async for chunk in pull_body(
                await self._nc(), request.parameters_inbox, max_bytes=size
            ):
                data.extend(chunk)
        except BodyTooLarge:
            raise RPCError(
                "INVALID_ARGUMENT", "Parameters are longer than announced"
            ) from None
        if len(data) != size:
            raise RPCError("INVALID_ARGUMENT", "Parameters are shorter than announced")
        return bytes(data)

    @staticmethod
    def _validate(instance: Any, raw: bytes) -> Any:
        try:
            data = json.loads(raw) if raw else {}
        except (ValueError, RecursionError):
            raise RPCError(
                "INVALID_ARGUMENT", "Parameters are not valid JSON"
            ) from None
        return parse_parameters(type(instance), data)

    async def _place(
        self, kind: str, payload: bytes, response: pb.RunResponse
    ) -> BodySource | None:
        """Put the result in the response, or, above one message, behind a body
        inbox the caller pulls from."""
        nc = await self._nc()
        if fits_inline(nc.max_payload, len(payload)):
            if kind == "pipeline":
                response.graph_nt = payload
            else:
                response.result_json = payload
            return None
        if len(payload) > MAX_BODY_BYTES:
            raise RPCError(
                "PAYLOAD_TOO_LARGE", f"The result exceeds {MAX_BODY_BYTES} bytes"
            )
        self._sources = {s for s in self._sources if not s.gone.is_set()}
        source = BodySource(nc, idle_seconds=STREAM_IDLE_SECONDS)
        await source.start()
        self._sources.add(source)
        response.body_inbox, response.body_bytes = source.inbox, len(payload)
        return source

    async def _stream(self, source: BodySource, payload: bytes) -> None:
        """Hand the result to its reader, one chunk per pull. The call stays
        in flight (a drain waits for it) until the reader took the end, or left;
        the source then lingers for a repeated last pull."""
        try:
            size = chunk_bytes((await self._nc()).max_payload)
            view = memoryview(payload)
            for offset in range(0, len(payload), size):
                await source.put(bytes(view[offset : offset + size]))
            await source.finish()
            await source.settled()
        except ReaderGone:
            pass
        except asyncio.CancelledError:
            await source.close()
            raise

    # -- describe -------------------------------------------------------------

    async def _describe(self, kind: str, name: str, msg: Any) -> None:
        with server_span(
            msg.subject,
            msg.headers,
            attributes={"abi.process.kind": kind, "abi.process.name": name},
        ):
            await self._serve_describe(kind, name, msg)

    async def _serve_describe(self, kind: str, name: str, msg: Any) -> None:
        response = pb.DescribeResponse()
        try:
            if len(msg.data) > MAX_DESCRIBE_BYTES or overflow.REQUEST_HEADER in (
                msg.headers or {}
            ):
                raise RPCError("PAYLOAD_TOO_LARGE", "Describe request exceeds 16 KiB")
            request = pb.DescribeRequest.FromString(msg.data)
            if self.closing:
                raise RPCError("MODULE_UNAVAILABLE", f"The {kind} host is draining")
            if request.name not in ("", name):
                raise RPCError(
                    "INVALID_ARGUMENT", "The describe request names another process"
                )
            await self._authorize(
                kind, name, (msg.headers or {}).get("Nats-Auth-Token", "")
            )
            described = self._schema(kind, name)
            # It must fit one message: the caller would wait out its timeout otherwise.
            nc = await self._nc()
            if described.ByteSize() + ENVELOPE_BYTES > nc.max_payload:
                raise RPCError(
                    "PAYLOAD_TOO_LARGE",
                    f"The {kind}'s parameter schema exceeds the broker's message size",
                )
            response.CopyFrom(described)
        except RPCError as exc:
            response = pb.DescribeResponse()
            response.error.code, response.error.message = exc.code, str(exc)
        except DecodeError:
            response = pb.DescribeResponse()
            response.error.code, response.error.message = (
                "INVALID_ARGUMENT",
                "Malformed describe request",
            )
        except Exception:
            logger.exception("Describing %s %s failed", kind, name)
            response = pb.DescribeResponse()
            response.error.code, response.error.message = (
                "PROCESS_ERROR",
                f"Could not describe the {kind}",
            )
        if not msg.reply:
            return
        try:
            await reply(msg, response.SerializeToString())
        except Exception:
            logger.warning(
                "Could not send the %s %s's description", kind, name, exc_info=True
            )
            failed = pb.DescribeResponse()
            failed.error.code, failed.error.message = (
                "PROCESS_ERROR",
                f"Could not send the {kind}'s description",
            )
            with contextlib.suppress(Exception):
                await reply(msg, failed.SerializeToString())

    def _schema(self, kind: str, name: str) -> pb.DescribeResponse:
        described = self._schemas.get((kind, name))
        if described is None:
            cls = type(self.processes[(kind, name)])
            described = pb.DescribeResponse(
                parameters_schema_json=json.dumps(
                    cls.parameters_type().model_json_schema()
                ).encode("utf-8"),
                description=cls.description(),
                kind=kind,
            )
            self._schemas[(kind, name)] = described
        return described


async def _within(
    coroutine: Any, seconds: float, message: str, *, cancelled: str
) -> Any:
    """``await coroutine`` for at most ``seconds``, then cancel it and raise
    DEADLINE_EXCEEDED. A timeout the coroutine raises itself is its own error, and
    so is a ``CancelledError`` it raises itself (a child task it awaited was
    cancelled, or it cancelled itself): ``PROCESS_ERROR`` with ``cancelled``, never
    a cancellation of this call. However it ends, the coroutine has finished, and
    cleaned up, when this returns or raises."""
    task = asyncio.ensure_future(coroutine)
    try:
        done, _ = await asyncio.wait({task}, timeout=max(0.0, seconds))
        if not done:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            raise RPCError("DEADLINE_EXCEEDED", message)
        if task.cancelled():
            raise RPCError("PROCESS_ERROR", cancelled)
        return task.result()
    finally:
        if not task.done():  # this call was cancelled (the host closes)
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
